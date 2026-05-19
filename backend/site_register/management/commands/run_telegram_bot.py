"""
Management command: python manage.py run_telegram_bot

Long-polls Telegram getUpdates and routes messages through conversation flows.

States
------
idle
rly_select_loa
rly_select_category
rly_select_item
rly_type_text          ← also accepts photo/document; /done to finish
rly_confirm
ss_select_thread
ss_thread_action
ss_type_reply          ← also accepts photo/document; /done to finish
ss_confirm_reply
"""

import logging
import time

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from site_register.models import (
    BotSession, TelegramLinkOTP, TelegramUserLink,
    WorkContractorTelegram, SiteRegisterThread, SiteRegisterMessage,
    SiteRegisterAttachment, SupervisorInvite,
)
from telegram_settings.models import TelegramBotConfig
from works.models import WorkItem

logger = logging.getLogger(__name__)

POLL_TIMEOUT = 30
RETRY_SLEEP  = 5
PAGE_SIZE    = 8

ONBOARD_SS_STATES  = {'ss_onboard_name', 'ss_onboard_desig', 'ss_onboard_mobile'}
ONBOARD_RLY_STATES = {'rly_onboard_hrms'}

CATEGORIES = [
    ('order',               '📋 Rly Official Order'),
    ('progress',            '📈 Progress Update'),
    ('hindrance',           '🚧 Hindrance'),
    ('inspection_request',  '🔍 Inspection Request'),
    ('document_submission', '📎 Document Submission'),
    ('general_remark',      '💬 General Remark'),
]
ITEM_CATEGORIES    = {'order', 'progress', 'hindrance', 'inspection_request'}
CATEGORY_LABELS    = dict(CATEGORIES)
REMOVE_KEYBOARD    = {"remove_keyboard": True}
TEXT_INPUT_STATES  = {'rly_type_text', 'ss_type_reply'}


# ── Telegram API helpers ─────────────────────────────────────────────────────

def _api(token: str, method: str, **kwargs) -> dict:
    url  = f"https://api.telegram.org/bot{token}/{method}"
    resp = requests.post(url, json=kwargs, timeout=POLL_TIMEOUT + 5)
    resp.raise_for_status()
    return resp.json()


def send(token: str, chat_id: int, text: str, keyboard=None, remove_kb=False):
    kwargs = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        kwargs["reply_markup"] = {
            "keyboard": keyboard,
            "one_time_keyboard": True,
            "resize_keyboard": True,
        }
    elif remove_kb:
        kwargs["reply_markup"] = REMOVE_KEYBOARD
    try:
        _api(token, "sendMessage", **kwargs)
    except Exception as exc:
        logger.warning("sendMessage failed chat=%s: %s", chat_id, exc)


def copy_message(token: str, to_chat_id: int, from_chat_id: int, message_id: int) -> int | None:
    """Copy a message to the archive group. Returns new message_id or None on failure."""
    try:
        data = _api(token, "copyMessage",
                    chat_id=to_chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id)
        return data["result"]["message_id"]
    except Exception as exc:
        logger.warning("copyMessage failed: %s", exc)
        return None


def number_keyboard(n: int, per_row: int = 4, extras: list | None = None) -> list:
    nums = [str(i) for i in range(1, n + 1)]
    rows = [nums[i:i + per_row] for i in range(0, len(nums), per_row)]
    if extras:
        rows.append(extras)
    return rows


# ── Attachment extraction ────────────────────────────────────────────────────

def extract_attachment(message: dict) -> dict | None:
    """
    Pull attachment metadata from a Telegram message.
    Returns dict with keys: tg_file_id, tg_file_unique_id, original_filename,
    file_type, from_chat_id, from_message_id.
    Returns None if message has no attachment.
    """
    chat_id    = message["chat"]["id"]
    message_id = message["message_id"]

    if message.get("photo"):
        # Telegram sends multiple sizes; last is largest
        largest = message["photo"][-1]
        return {
            "tg_file_id":        largest["file_id"],
            "tg_file_unique_id": largest["file_unique_id"],
            "original_filename": "",
            "file_type":         "photo",
            "from_chat_id":      chat_id,
            "from_message_id":   message_id,
        }

    doc = message.get("document")
    if doc:
        fname     = doc.get("file_name", "")
        file_type = "pdf" if fname.lower().endswith(".pdf") else "document"
        return {
            "tg_file_id":        doc["file_id"],
            "tg_file_unique_id": doc.get("file_unique_id", ""),
            "original_filename": fname,
            "file_type":         file_type,
            "from_chat_id":      chat_id,
            "from_message_id":   message_id,
        }

    return None


# ── Session helpers ───────────────────────────────────────────────────────────

def get_session(chat_id: int) -> BotSession:
    session, _ = BotSession.objects.get_or_create(
        telegram_chat_id=chat_id,
        defaults={"state": "idle", "context": {}},
    )
    return session


def reset_session(session: BotSession):
    session.state   = "idle"
    session.context = {}
    session.save(update_fields=["state", "context", "updated_at"])


# ── User identity ─────────────────────────────────────────────────────────────

def resolve_user(tg_user_id: int):
    """Return (user, role_str) or (None, None) if not linked."""
    try:
        link = TelegramUserLink.objects.select_related(
            'user', 'user__profile'
        ).get(telegram_user_id=tg_user_id, is_verified=True)
    except TelegramUserLink.DoesNotExist:
        return None, None
    profile = getattr(link.user, 'profile', None)
    role    = profile.role if profile else ('admin' if link.user.is_staff else 'consignee')
    return link.user, role


def _time_ago(dt) -> str:
    now   = timezone.now()
    delta = now - dt
    secs  = int(delta.total_seconds())
    if secs < 60:   return "just now"
    if secs < 3600: return f"{secs // 60}m ago"
    if secs < 86400:return f"{secs // 3600}h ago"
    return f"{delta.days}d ago"


# ── Attachment persistence helper ────────────────────────────────────────────

def _save_attachments(token: str, upload_chat_id: str,
                      message_obj: SiteRegisterMessage,
                      attachments: list[dict]):
    """
    Forward each pending attachment to archive group and create DB records.
    attachments = list of dicts from extract_attachment() stored in session context.
    """
    if not upload_chat_id or not attachments:
        return

    for att in attachments:
        archive_msg_id = copy_message(
            token,
            to_chat_id   = int(upload_chat_id),
            from_chat_id = att["from_chat_id"],
            message_id   = att["from_message_id"],
        )
        SiteRegisterAttachment.objects.create(
            message                  = message_obj,
            tg_file_id               = att["tg_file_id"],
            tg_file_unique_id        = att.get("tg_file_unique_id", ""),
            original_filename        = att.get("original_filename", ""),
            file_type                = att["file_type"],
            archive_group_message_id = archive_msg_id,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RLY OFFICIAL FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def rly_works_page(page: int):
    from works.models import Work
    all_works = list(Work.objects.order_by('loa_number'))
    start = page * PAGE_SIZE
    end   = start + PAGE_SIZE
    return all_works[start:end], len(all_works), len(all_works) > end


def show_loa_list(token: str, session: BotSession, user, page: int = 0):
    works, total, has_next = rly_works_page(page)
    if not works:
        send(token, session.telegram_chat_id,
             "⚠️ No LOAs found in the system.",
             remove_kb=True)
        reset_session(session)
        return

    lines = [f"<b>📋 New Entry</b> (page {page+1}) — Select LOA:\n"]
    for i, w in enumerate(works, 1):
        lines.append(f"{i}. {w.loa_number} — {w.contractor_name or '—'}")

    extras = []
    if has_next: extras.append("Next ▶")
    if page > 0: extras.append("◀ Prev")
    extras.append("❌ Cancel")

    session.context = {"loa_page": page, "loa_choices": [w.id for w in works]}
    session.state   = "rly_select_loa"
    session.save(update_fields=["state", "context", "updated_at"])
    send(token, session.telegram_chat_id, "\n".join(lines),
         keyboard=number_keyboard(len(works), extras=extras))


def show_categories(token: str, session: BotSession):
    lines = ["<b>Select entry type:</b>\n"]
    for i, (_, label) in enumerate(CATEGORIES, 1):
        lines.append(f"{i}. {label}")
    send(token, session.telegram_chat_id, "\n".join(lines),
         keyboard=number_keyboard(len(CATEGORIES), extras=["❌ Cancel"]))


def show_items(token: str, session: BotSession, work_id: int, page: int = 0):
    items      = list(WorkItem.objects.filter(work_id=work_id).order_by('schedule', 'serial_number'))
    start      = page * PAGE_SIZE
    end        = start + PAGE_SIZE
    page_items = items[start:end]
    has_next   = len(items) > end

    lines = [f"<b>Select work item</b> (page {page+1}):\n0. ⏭ Skip\n"]
    for i, item in enumerate(page_items, 1):
        desc = (item.item_desc or '').strip()[:50]
        lines.append(f"{i}. {item.schedule}/{item.serial_number} — {desc}")

    extras = ["0"]
    if has_next: extras.append("Next ▶")
    if page > 0: extras.append("◀ Prev")
    extras.append("❌ Cancel")

    session.context.update({"item_page": page, "item_choices": [item.id for item in page_items]})
    session.state = "rly_select_item"
    session.save(update_fields=["state", "context", "updated_at"])
    send(token, session.telegram_chat_id, "\n".join(lines),
         keyboard=number_keyboard(len(page_items), extras=extras))


def show_text_prompt(token: str, session: BotSession):
    ctx       = session.context
    item_line = f"\n<b>Item:</b> {ctx['work_item_desc']}" if ctx.get('work_item_id') else ""
    send(token, session.telegram_chat_id,
         f"<b>LOA:</b> {ctx['loa_number']}\n"
         f"<b>Type:</b> {ctx['category_label']}{item_line}\n\n"
         "✏️ <b>Type your message</b> (you can also send photos/documents).\n"
         "Send <code>/done</code> after attachments to finish without text.",
         remove_kb=True)
    session.state = "rly_type_text"
    session.save(update_fields=["state", "updated_at"])


def _att_line(ctx: dict) -> str:
    n = len(ctx.get("attachments", []))
    return f"\n📎 <b>Attachments:</b> {n}" if n else ""


def show_rly_confirm(token: str, session: BotSession):
    ctx       = session.context
    item_line = f"\n<b>Item:</b> {ctx['work_item_desc']}" if ctx.get('work_item_id') else ""
    send(token, session.telegram_chat_id,
         "📋 <b>Review your entry:</b>\n\n"
         f"<b>LOA:</b> {ctx['loa_number']}\n"
         f"<b>Contractor:</b> {ctx['contractor_name']}\n"
         f"<b>Type:</b> {ctx['category_label']}{item_line}\n"
         f"<b>Message:</b>\n{ctx.get('text', '—')}"
         f"{_att_line(ctx)}\n\n"
         "Send this to the site supervisor?",
         keyboard=[["1. ✅ Confirm"], ["2. ❌ Cancel"]])
    session.state = "rly_confirm"
    session.save(update_fields=["state", "updated_at"])


def do_create_thread(token: str, upload_chat_id: str, session: BotSession, user):
    ctx = session.context

    with transaction.atomic():
        thread = SiteRegisterThread.objects.create(
            work_id           = ctx['work_id'],
            work_item_id      = ctx.get('work_item_id'),
            initiated_by_role = 'rly_official',
            category          = ctx['category'],
            initial_text      = ctx.get('text', ''),
            status            = 'open',
            created_by        = user,
        )
        # Create initial message so attachments have a FK target
        attachments = ctx.get("attachments", [])
        if attachments:
            msg = SiteRegisterMessage.objects.create(
                thread       = thread,
                sender       = user,
                sender_role  = 'rly_official',
                message_text = ctx.get('text', ''),
            )
            _save_attachments(token, upload_chat_id, msg, attachments)

    # Notify site supervisors
    ss_links = (
        WorkContractorTelegram.objects
        .filter(work_id=ctx['work_id'], role='site_supervisor', is_active=True)
        .select_related('telegram_link')
    )
    item_line  = f"\n📦 <b>Item:</b> {ctx['work_item_desc']}" if ctx.get('work_item_id') else ""
    att_note   = f"\n📎 {len(attachments)} attachment(s) included." if attachments else ""
    notify_text = (
        f"📋 <b>New Rly Official Entry — SR-{thread.pk:06d}</b>\n\n"
        f"<b>LOA:</b> {ctx['loa_number']}\n"
        f"<b>Type:</b> {ctx['category_label']}{item_line}\n\n"
        f"{ctx.get('text', '')}{att_note}\n\n"
        f"— <i>{user.first_name or user.username}</i>\n\n"
        "Reply via bot menu."
    )
    notified = 0
    for m in ss_links:
        send(token, m.telegram_link.telegram_chat_id, notify_text)
        notified += 1

    send(token, session.telegram_chat_id,
         f"✅ <b>SR-{thread.pk:06d} created.</b> Notified {notified} site supervisor(s).",
         remove_kb=True)
    logger.info("SR-%06d created by %s, notified %d", thread.pk, user.username, notified)
    reset_session(session)


# ── Rly Official state handlers ───────────────────────────────────────────────

def handle_rly_select_loa(token: str, session: BotSession, user, text: str):
    ctx = session.context
    if text == "Next ▶":
        show_loa_list(token, session, user, page=ctx.get("loa_page", 0) + 1); return
    if text == "◀ Prev":
        show_loa_list(token, session, user, page=max(0, ctx.get("loa_page", 0) - 1)); return
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send the LOA number."); return
    choices = ctx.get("loa_choices", [])
    if not (0 <= idx < len(choices)):
        send(token, session.telegram_chat_id, f"⚠️ Enter 1–{len(choices)}."); return

    from works.models import Work
    work = Work.objects.get(pk=choices[idx])
    session.context.update({
        "work_id": work.id, "loa_number": work.loa_number,
        "contractor_name": work.contractor_name or "—",
    })
    session.state = "rly_select_category"
    session.save(update_fields=["state", "context", "updated_at"])
    show_categories(token, session)


def handle_rly_select_category(token: str, session: BotSession, text: str):
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send the category number."); return
    if not (0 <= idx < len(CATEGORIES)):
        send(token, session.telegram_chat_id, f"⚠️ Enter 1–{len(CATEGORIES)}."); return
    cat_key, cat_label = CATEGORIES[idx]
    session.context.update({"category": cat_key, "category_label": cat_label})
    session.save(update_fields=["context", "updated_at"])
    if cat_key in ITEM_CATEGORIES:
        show_items(token, session, session.context["work_id"], page=0)
    else:
        show_text_prompt(token, session)


def handle_rly_select_item(token: str, session: BotSession, text: str):
    ctx = session.context
    if text == "Next ▶":
        show_items(token, session, ctx["work_id"], page=ctx.get("item_page", 0) + 1); return
    if text == "◀ Prev":
        show_items(token, session, ctx["work_id"], page=max(0, ctx.get("item_page", 0) - 1)); return
    if text.strip() == "0":
        session.context.pop("work_item_id", None)
        session.context.pop("work_item_desc", None)
        session.save(update_fields=["context", "updated_at"])
        show_text_prompt(token, session); return
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send item number or 0 to skip."); return
    choices = ctx.get("item_choices", [])
    if not (0 <= idx < len(choices)):
        send(token, session.telegram_chat_id, f"⚠️ Enter 1–{len(choices)} or 0."); return
    item = WorkItem.objects.get(pk=choices[idx])
    desc = f"{item.schedule}/{item.serial_number} — {(item.item_desc or '').strip()[:60]}"
    session.context.update({"work_item_id": item.id, "work_item_desc": desc})
    session.save(update_fields=["context", "updated_at"])
    show_text_prompt(token, session)


def handle_rly_type_text(token: str, session: BotSession,
                         text: str | None, attachment: dict | None):
    if attachment:
        atts = session.context.setdefault("attachments", [])
        atts.append(attachment)
        n = len(atts)
        caption = text or ""
        if caption:
            session.context["text"] = caption
        session.save(update_fields=["context", "updated_at"])
        send(token, session.telegram_chat_id,
             f"📎 Attachment {n} saved."
             + (f" Caption: <i>{caption[:60]}</i>" if caption else "")
             + "\n\nSend more files, type your message, or <code>/done</code> to continue.")
        return

    # Text (or /done with no text yet)
    if text:
        session.context["text"] = text
        session.save(update_fields=["context", "updated_at"])
    elif not session.context.get("text") and not session.context.get("attachments"):
        send(token, session.telegram_chat_id,
             "⚠️ Send your message text or at least one attachment first.")
        return

    show_rly_confirm(token, session)


def handle_rly_confirm(token: str, upload_chat_id: str,
                       session: BotSession, user, text: str):
    if text.strip().startswith("1"):
        do_create_thread(token, upload_chat_id, session, user)
    elif text.strip().startswith("2"):
        send(token, session.telegram_chat_id, "❌ Entry cancelled.", remove_kb=True)
        reset_session(session)
    else:
        send(token, session.telegram_chat_id, "⚠️ Reply 1 to confirm or 2 to cancel.")


# ═══════════════════════════════════════════════════════════════════════════════
# SITE SUPERVISOR FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def ss_threads_page(user, page: int):
    work_ids = list(
        WorkContractorTelegram.objects
        .filter(telegram_link__user=user, role='site_supervisor', is_active=True)
        .values_list('work_id', flat=True)
    )
    if not work_ids:
        return [], 0, False
    qs = (
        SiteRegisterThread.objects
        .filter(work_id__in=work_ids, status__in=('open', 'replied'))
        .select_related('work', 'work_item')
        .order_by('-created_at')
    )
    total = qs.count()
    start = page * PAGE_SIZE
    end   = start + PAGE_SIZE
    return list(qs[start:end]), total, total > end


def _thread_short(t: SiteRegisterThread) -> str:
    preview = t.initial_text[:60].replace('\n', ' ')
    return (f"SR-{t.pk:06d} | {t.work.loa_number} | "
            f"{CATEGORY_LABELS.get(t.category, t.category)} | {_time_ago(t.created_at)}\n{preview}…")


def _thread_full(t: SiteRegisterThread) -> str:
    item_line = ""
    if t.work_item:
        wi = t.work_item
        item_line = f"\n<b>Item:</b> {wi.schedule}/{wi.serial_number} — {(wi.item_desc or '').strip()[:60]}"

    msgs = list(
        SiteRegisterMessage.objects
        .filter(thread=t).select_related('sender').order_by('-created_at')[:3]
    )
    msgs.reverse()
    replies = ""
    if msgs:
        parts = [f"  [{m.sender_role.upper()}] {m.sender.first_name if m.sender else '?'}: {m.message_text[:80]}"
                 for m in msgs]
        replies = "\n\n<b>Recent replies:</b>\n" + "\n".join(parts)

    return (
        f"<b>SR-{t.pk:06d}</b> — {CATEGORY_LABELS.get(t.category, t.category)}\n"
        f"<b>LOA:</b> {t.work.loa_number} | <b>Status:</b> {t.status.upper()}{item_line}\n"
        f"<b>Created:</b> {_time_ago(t.created_at)}\n\n{t.initial_text}{replies}"
    )


def show_ss_threads(token: str, session: BotSession, user, page: int = 0):
    threads, total, has_next = ss_threads_page(user, page)
    if not threads and page == 0:
        send(token, session.telegram_chat_id,
             "✅ No open entries for your LOAs.", remove_kb=True)
        reset_session(session); return

    lines = [f"<b>📬 Open Entries</b> ({total} total, page {page+1}):\n"]
    for i, t in enumerate(threads, 1):
        lines.append(f"{i}. {_thread_short(t)}\n")

    extras = []
    if has_next: extras.append("Next ▶")
    if page > 0: extras.append("◀ Prev")
    extras.append("❌ Cancel")

    session.context = {"thread_page": page, "thread_choices": [t.pk for t in threads]}
    session.state   = "ss_select_thread"
    session.save(update_fields=["state", "context", "updated_at"])
    send(token, session.telegram_chat_id, "\n".join(lines),
         keyboard=number_keyboard(len(threads), extras=extras))


def show_thread_actions(token: str, session: BotSession, thread: SiteRegisterThread):
    send(token, session.telegram_chat_id,
         _thread_full(thread) + "\n\nWhat would you like to do?",
         keyboard=[["1. ✉️ Reply"], ["2. ✅ Mark Resolved"], ["3. ◀ Back"], ["❌ Cancel"]])
    session.context["thread_id"] = thread.pk
    session.state = "ss_thread_action"
    session.save(update_fields=["state", "context", "updated_at"])


def show_ss_reply_prompt(token: str, session: BotSession):
    send(token, session.telegram_chat_id,
         "✏️ <b>Type your reply</b> (you can also send photos/documents).\n"
         "Send <code>/done</code> after attachments to finish without text.",
         remove_kb=True)
    session.state = "ss_type_reply"
    session.save(update_fields=["state", "updated_at"])


def show_ss_confirm(token: str, session: BotSession):
    ctx = session.context
    send(token, session.telegram_chat_id,
         f"<b>Reply to SR-{ctx['thread_id']:06d}:</b>\n\n"
         f"{ctx.get('reply_text', '—')}"
         f"{_att_line(ctx)}\n\n"
         "Send this reply?",
         keyboard=[["1. ✅ Send"], ["2. ❌ Cancel"]])
    session.state = "ss_confirm_reply"
    session.save(update_fields=["state", "updated_at"])


def do_send_reply(token: str, upload_chat_id: str, session: BotSession, user):
    ctx = session.context
    try:
        thread = SiteRegisterThread.objects.select_related('work').get(pk=ctx['thread_id'])
    except SiteRegisterThread.DoesNotExist:
        send(token, session.telegram_chat_id, "⚠️ Entry not found.", remove_kb=True)
        reset_session(session); return

    attachments = ctx.get("attachments", [])
    with transaction.atomic():
        msg = SiteRegisterMessage.objects.create(
            thread       = thread,
            sender       = user,
            sender_role  = 'site_supervisor',
            message_text = ctx.get('reply_text', ''),
        )
        _save_attachments(token, upload_chat_id, msg, attachments)
        thread.status = 'replied'
        thread.save(update_fields=['status'])

    # Notify all Rly Officials (no LOA mapping — they see everything)
    rly_links = (
        TelegramUserLink.objects
        .filter(is_verified=True, user__profile__role='rly_official')
        .select_related('user')
    )
    att_note    = f"\n📎 {len(attachments)} attachment(s) included." if attachments else ""
    notify_text = (
        f"💬 <b>Site Supervisor Reply — SR-{thread.pk:06d}</b>\n\n"
        f"<b>LOA:</b> {thread.work.loa_number}\n"
        f"<b>Type:</b> {CATEGORY_LABELS.get(thread.category, thread.category)}\n\n"
        f"{ctx.get('reply_text', '')}{att_note}\n\n"
        f"— <i>{user.first_name or user.username}</i>"
    )
    notified = 0
    for lnk in rly_links:
        send(token, lnk.telegram_chat_id, notify_text)
        notified += 1

    send(token, session.telegram_chat_id,
         f"✅ Reply sent. Notified {notified} Rly Official(s).", remove_kb=True)
    logger.info("SR-%06d reply by %s, notified %d rly officials", thread.pk, user.username, notified)
    reset_session(session)


def do_mark_resolved(token: str, session: BotSession, user):
    ctx = session.context
    try:
        thread = SiteRegisterThread.objects.select_related('work').get(pk=ctx['thread_id'])
    except SiteRegisterThread.DoesNotExist:
        send(token, session.telegram_chat_id, "⚠️ Entry not found.", remove_kb=True)
        reset_session(session); return

    with transaction.atomic():
        SiteRegisterMessage.objects.create(
            thread=thread, sender=user, sender_role='site_supervisor',
            message_text='✅ Marked as resolved by site supervisor.',
        )
        thread.status = 'verified'
        thread.save(update_fields=['status'])

    # Notify all Rly Officials
    rly_links = (
        TelegramUserLink.objects
        .filter(is_verified=True, user__profile__role='rly_official')
        .select_related('user')
    )
    notify = (
        f"✅ <b>SR-{thread.pk:06d} Resolved</b>\n\n"
        f"<b>LOA:</b> {thread.work.loa_number}\n"
        f"<b>Type:</b> {CATEGORY_LABELS.get(thread.category, thread.category)}\n\n"
        f"Resolved by <i>{user.first_name or user.username}</i>."
    )
    for lnk in rly_links:
        send(token, lnk.telegram_chat_id, notify)

    send(token, session.telegram_chat_id,
         f"✅ SR-{thread.pk:06d} marked resolved.", remove_kb=True)
    logger.info("SR-%06d resolved by %s", thread.pk, user.username)
    reset_session(session)


# ── Site Supervisor state handlers ───────────────────────────────────────────

def handle_ss_select_thread(token: str, session: BotSession, user, text: str):
    ctx = session.context
    if text == "Next ▶":
        show_ss_threads(token, session, user, page=ctx.get("thread_page", 0) + 1); return
    if text == "◀ Prev":
        show_ss_threads(token, session, user, page=max(0, ctx.get("thread_page", 0) - 1)); return
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send entry number."); return
    choices = ctx.get("thread_choices", [])
    if not (0 <= idx < len(choices)):
        send(token, session.telegram_chat_id, f"⚠️ Enter 1–{len(choices)}."); return
    try:
        thread = SiteRegisterThread.objects.select_related('work', 'work_item').get(pk=choices[idx])
    except SiteRegisterThread.DoesNotExist:
        send(token, session.telegram_chat_id, "⚠️ Entry no longer available.", remove_kb=True)
        reset_session(session); return
    show_thread_actions(token, session, thread)


def handle_ss_thread_action(token: str, session: BotSession, user, text: str):
    t = text.strip()
    if t.startswith("1"):   show_ss_reply_prompt(token, session)
    elif t.startswith("2"): do_mark_resolved(token, session, user)
    elif t.startswith("3"): show_ss_threads(token, session, user,
                                                     page=session.context.get("thread_page", 0))
    else: send(token, session.telegram_chat_id, "⚠️ Send 1, 2, or 3.")


def handle_ss_type_reply(token: str, session: BotSession,
                                 text: str | None, attachment: dict | None):
    if attachment:
        atts    = session.context.setdefault("attachments", [])
        atts.append(attachment)
        n       = len(atts)
        caption = text or ""
        if caption:
            session.context["reply_text"] = caption
        session.save(update_fields=["context", "updated_at"])
        send(token, session.telegram_chat_id,
             f"📎 Attachment {n} saved."
             + (f" Caption: <i>{caption[:60]}</i>" if caption else "")
             + "\n\nSend more files, type reply, or <code>/done</code> to continue.")
        return

    if text:
        session.context["reply_text"] = text
        session.save(update_fields=["context", "updated_at"])
    elif not session.context.get("reply_text") and not session.context.get("attachments"):
        send(token, session.telegram_chat_id,
             "⚠️ Send reply text or at least one attachment first.")
        return

    show_ss_confirm(token, session)


def handle_ss_confirm_reply(token: str, upload_chat_id: str,
                                    session: BotSession, user, text: str):
    if text.strip().startswith("1"):
        do_send_reply(token, upload_chat_id, session, user)
    elif text.strip().startswith("2"):
        send(token, session.telegram_chat_id, "❌ Reply cancelled.", remove_kb=True)
        reset_session(session)
    else:
        send(token, session.telegram_chat_id, "⚠️ Reply 1 to send or 2 to cancel.")


# ═══════════════════════════════════════════════════════════════════════════════
# OTP LINKING
# ═══════════════════════════════════════════════════════════════════════════════

def handle_start(token: str, chat_id: int):
    send(token, chat_id,
         "👋 <b>Welcome to ManageWorks Site Register Bot.</b>\n\n"
         "<b>Railway Officials:</b>\n"
         "Go to <b>Settings → Link Rly Official Telegram</b> in the web app, "
         "generate a 6-digit code, then type it here.\n\n"
         "<b>Site Supervisors (Contractor Staff):</b>\n"
         "Ask your admin to share a 6-digit invite code from "
         "<b>Settings → Site Supervisors → Add Supervisor</b>, "
         "then type the code here.")


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING FLOWS
# ═══════════════════════════════════════════════════════════════════════════════

def handle_ss_onboard(token: str, session: BotSession,
                      tg_user_id: int, chat_id: int, text: str):
    """Multi-step onboarding for contractor site supervisors."""
    if not text:
        return

    if session.state == 'ss_onboard_name':
        session.context['onboard_name'] = text.strip()
        session.state = 'ss_onboard_desig'
        session.save(update_fields=['state', 'context', 'updated_at'])
        send(token, chat_id,
             f"👍 Got it, <b>{text.strip()}</b>.\n\n"
             "What is your <b>designation / role in the firm</b>?\n"
             "<i>(e.g. Site Engineer, Foreman, Project Manager)</i>")

    elif session.state == 'ss_onboard_desig':
        session.context['onboard_desig'] = text.strip()
        session.state = 'ss_onboard_mobile'
        session.save(update_fields=['state', 'context', 'updated_at'])
        send(token, chat_id,
             "What is your <b>mobile number</b>?")

    elif session.state == 'ss_onboard_mobile':
        mobile = text.strip()
        ctx    = session.context

        from django.contrib.auth.models import User as DjUser
        from works.models import Work

        with transaction.atomic():
            invite_code = ctx['pending_invite_code']
            try:
                invite = SupervisorInvite.objects.select_for_update().get(
                    code=invite_code, used=False)
            except SupervisorInvite.DoesNotExist:
                send(token, chat_id, "❌ Invite expired or already used. Ask admin to generate a new code.")
                reset_session(session)
                return

            if invite.is_expired:
                send(token, chat_id, "❌ Invite expired. Ask admin for a new code.")
                reset_session(session)
                return

            name  = ctx.get('onboard_name', '')
            desig = ctx.get('onboard_desig', '')

            username = f"tg_{tg_user_id}"
            user, _ = DjUser.objects.get_or_create(
                username=username,
                defaults={'first_name': name or username, 'password': '!'},
            )
            if name and not user.first_name:
                user.first_name = name
                user.save(update_fields=['first_name'])

            link, created = TelegramUserLink.objects.get_or_create(
                telegram_user_id=tg_user_id,
                defaults={
                    'user': user,
                    'telegram_chat_id': chat_id,
                    'is_verified': True,
                    'onboard_name': name,
                    'onboard_designation': desig,
                    'onboard_mobile': mobile,
                },
            )
            if not created:
                link.telegram_chat_id  = chat_id
                link.is_verified       = True
                link.onboard_name      = name
                link.onboard_designation = desig
                link.onboard_mobile    = mobile
                link.save(update_fields=['telegram_chat_id', 'is_verified',
                                         'onboard_name', 'onboard_designation', 'onboard_mobile'])

            for loa_id in invite.loa_ids:
                try:
                    work = Work.objects.get(pk=loa_id)
                    mapping, c = WorkContractorTelegram.objects.get_or_create(
                        work=work, telegram_link=link,
                        defaults={'role': 'site_supervisor', 'is_active': True},
                    )
                    if not c:
                        mapping.is_active = True
                        mapping.save(update_fields=['is_active'])
                except Work.DoesNotExist:
                    pass

            invite.used         = True
            invite.used_by_link = link
            invite.save(update_fields=['used', 'used_by_link'])

        loa_count = len(invite.loa_ids)
        send(token, chat_id,
             f"✅ <b>Registration complete!</b>\n\n"
             f"<b>Name:</b> {name}\n"
             f"<b>Designation:</b> {desig}\n"
             f"<b>Mobile:</b> {mobile}\n\n"
             f"You are mapped to <b>{loa_count}</b> LOA(s) as a Site Supervisor.\n"
             "You will receive site register notifications here.")
        logger.info("SS onboarded tg=%s name=%s", tg_user_id, name)
        reset_session(session)


def handle_rly_onboard(token: str, session: BotSession, user, text: str):
    """Ask HRMS ID confirmation for railway officials after OTP link."""
    if not text:
        return
    hrms_id = text.strip()
    if hrms_id.lower() != user.username.lower():
        send(token, session.telegram_chat_id,
             f"⚠️ HRMS ID <code>{hrms_id}</code> doesn't match your account.\n"
             "Please try again or type your correct HRMS ID.")
        return

    profile     = getattr(user, 'profile', None)
    designation = profile.designation if profile else '—'
    role_label  = profile.role.replace('_', ' ').title() if profile else 'Official'
    send(token, session.telegram_chat_id,
         f"✅ <b>HRMS confirmed!</b>\n\n"
         f"<b>Name:</b> {user.first_name or user.username}\n"
         f"<b>HRMS ID:</b> {user.username}\n"
         f"<b>Designation:</b> {designation}\n"
         f"<b>Role:</b> {role_label}\n\n"
         "Your account is fully set up. You will receive Site Register notifications here.")
    reset_session(session)


def try_link_otp(token: str, chat_id: int, tg_user_id: int, code: str, tg_from: dict | None = None) -> bool:
    """Try to link account using a 6-digit code. Returns True if handled."""
    if not (code.isdigit() and len(code) == 6):
        return False

    # ── Railway Official OTP ─────────────────────────────────────────────────
    try:
        with transaction.atomic():
            otp = TelegramLinkOTP.objects.select_for_update().get(code=code, used=False)
            if otp.is_expired:
                send(token, chat_id, "❌ Code expired. Generate a new one from the web app.")
                return True
            if TelegramUserLink.objects.filter(telegram_user_id=tg_user_id).exclude(user=otp.user).exists():
                send(token, chat_id, "⚠️ Telegram already linked to a different ManageWorks account.")
                return True
            TelegramUserLink.objects.update_or_create(
                user=otp.user,
                defaults={"telegram_user_id": tg_user_id, "telegram_chat_id": chat_id, "is_verified": True},
            )
            otp.used = True
            otp.save(update_fields=["used"])

        logger.info("Linked tg=%s → mw=%s", tg_user_id, otp.user.username)
        # Start HRMS confirmation step
        session = get_session(chat_id)
        session.state   = 'rly_onboard_hrms'
        session.context = {}
        session.save(update_fields=['state', 'context', 'updated_at'])
        send(token, chat_id,
             "✅ <b>Telegram linked!</b>\n\n"
             "Please enter your <b>HRMS ID</b> to complete setup.")
        return True

    except TelegramLinkOTP.DoesNotExist:
        pass

    # ── Supervisor Invite ────────────────────────────────────────────────────
    try:
        invite = SupervisorInvite.objects.get(code=code, used=False)
        if invite.is_expired:
            send(token, chat_id, "❌ Invite code expired. Ask admin to generate a new one.")
            return True

        # Start onboarding — name/designation/mobile collected before creating user
        session = get_session(chat_id)
        session.state   = 'ss_onboard_name'
        session.context = {'pending_invite_code': code}
        session.save(update_fields=['state', 'context', 'updated_at'])

        tg_name = ''
        if tg_from:
            parts = [tg_from.get('first_name', ''), tg_from.get('last_name', '')]
            tg_name = ' '.join(p for p in parts if p).strip()

        send(token, chat_id,
             f"✅ <b>Valid invite code!</b>\n\n"
             f"Let me register you as a Site Supervisor.\n\n"
             f"What is your <b>full name</b>?"
             + (f"\n\n<i>(Telegram name: {tg_name})</i>" if tg_name else ""))
        logger.info("SupervisorInvite %s accepted by tg=%s, starting onboarding", code, tg_user_id)
        return True

    except SupervisorInvite.DoesNotExist:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def dispatch(token: str, upload_chat_id: str, update: dict):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id    = message["chat"]["id"]
    tg_user_id = message["from"]["id"]
    text       = (message.get("text") or message.get("caption") or "").strip()
    attachment = extract_attachment(message)

    # Skip if no content at all
    if not text and not attachment:
        return

    # /start — welcome message
    if text.startswith("/start"):
        handle_start(token, chat_id)
        return

    # 6-digit link code — try before resolving user (unlinked user)
    if try_link_otp(token, chat_id, tg_user_id, text, tg_from=message.get("from")):
        return

    # Onboarding states — handled before resolve_user (contractor not linked yet)
    _session_peek = get_session(chat_id)
    if _session_peek.state in ONBOARD_SS_STATES:
        handle_ss_onboard(token, _session_peek, tg_user_id, chat_id, text)
        return
    if _session_peek.state in ONBOARD_RLY_STATES:
        _rly_user, _ = resolve_user(tg_user_id)
        if _rly_user:
            handle_rly_onboard(token, _session_peek, _rly_user, text)
        return

    user, role = resolve_user(tg_user_id)

    # Cancel — any state
    if text in ("/cancel", "❌ Cancel"):
        if user:
            session = get_session(chat_id)
            if session.state != "idle":
                reset_session(session)
                send(token, chat_id, "❌ Cancelled.", remove_kb=True)
                return
        send(token, chat_id, "Nothing to cancel.", remove_kb=True)
        return

    if not user:
        send(token, chat_id,
             "⚠️ Account not linked.\nGo to Settings → Link Telegram in the web app.")
        return

    session = get_session(chat_id)

    # /done finalises text-input states
    if text == "/done" and session.state in TEXT_INPUT_STATES:
        text = None   # treat as "no new text, just finish"

    if session.state == "idle":
        if attachment:
            send(token, chat_id,
                 "⚠️ Start a new entry first — just send any message to begin.")
            return
        if role in ('rly_official', 'admin'):
            show_loa_list(token, session, user, page=0)
        elif role == 'site_supervisor':
            show_ss_threads(token, session, user, page=0)
        else:
            send(token, chat_id,
                 "ℹ️ You will receive notifications here when entries are created for your LOAs.")

    elif session.state == "rly_select_loa":
        handle_rly_select_loa(token, session, user, text or "")
    elif session.state == "rly_select_category":
        handle_rly_select_category(token, session, text or "")
    elif session.state == "rly_select_item":
        handle_rly_select_item(token, session, text or "")
    elif session.state == "rly_type_text":
        handle_rly_type_text(token, session, text, attachment)
    elif session.state == "rly_confirm":
        handle_rly_confirm(token, upload_chat_id, session, user, text or "")

    elif session.state == "ss_select_thread":
        handle_ss_select_thread(token, session, user, text or "")
    elif session.state == "ss_thread_action":
        handle_ss_thread_action(token, session, user, text or "")
    elif session.state == "ss_type_reply":
        handle_ss_type_reply(token, session, text, attachment)
    elif session.state == "ss_confirm_reply":
        handle_ss_confirm_reply(token, upload_chat_id, session, user, text or "")

    else:
        logger.warning("Unknown state %s chat=%s, resetting", session.state, chat_id)
        reset_session(session)
        dispatch(token, upload_chat_id, update)


# ═══════════════════════════════════════════════════════════════════════════════
# MANAGEMENT COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = "Run the Telegram bot long-polling worker"

    def handle(self, *args, **options):
        config = TelegramBotConfig.objects.filter(pk=1).first()
        if not config or not config.bot_token:
            self.stderr.write("No bot token configured. Set it in Settings → Telegram Bot.")
            return
        if not config.is_active:
            self.stderr.write("Bot disabled. Enable it in Settings → Telegram Bot.")
            return

        token          = config.bot_token
        upload_chat_id = config.upload_group_chat_id or ""
        offset         = 0

        if not upload_chat_id:
            self.stderr.write(
                "Warning: upload_group_chat_id not set — attachments won't be archived to group."
            )

        self.stdout.write(self.style.SUCCESS("Telegram bot started. Listening for updates…"))
        logger.info("Telegram bot started (archive group: %s)", upload_chat_id or "NOT SET")

        while True:
            try:
                data = _api(token, "getUpdates",
                    offset=offset,
                    timeout=POLL_TIMEOUT,
                    allowed_updates=["message"],
                )
                for update in data.get("result", []):
                    try:
                        dispatch(token, upload_chat_id, update)
                    except Exception as exc:
                        logger.exception("Error dispatching update %s: %s",
                                         update.get("update_id"), exc)
                    offset = update["update_id"] + 1

            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as exc:
                logger.warning("Telegram API error: %s — retrying in %ds", exc, RETRY_SLEEP)
                time.sleep(RETRY_SLEEP)
            except KeyboardInterrupt:
                self.stdout.write("\nBot stopped.")
                break
            except Exception as exc:
                logger.exception("Unexpected error: %s — retrying in %ds", exc, RETRY_SLEEP)
                time.sleep(RETRY_SLEEP)
