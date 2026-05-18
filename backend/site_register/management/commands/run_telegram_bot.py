"""
Management command: python manage.py run_telegram_bot

Long-polls Telegram getUpdates and routes messages through conversation flows.

States
------
idle
sse_select_loa
sse_select_category
sse_select_item
sse_type_text
sse_confirm
contractor_select_thread
contractor_thread_action
contractor_type_reply
contractor_confirm_reply
"""

import logging
import time
from datetime import timezone as tz

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from site_register.models import (
    BotSession, TelegramLinkOTP, TelegramUserLink,
    WorkContractorTelegram, SiteRegisterThread, SiteRegisterMessage,
)
from telegram_settings.models import TelegramBotConfig
from works.models import WorkItem

logger = logging.getLogger(__name__)

POLL_TIMEOUT = 30
RETRY_SLEEP  = 5
PAGE_SIZE    = 8

CATEGORIES = [
    ('order',               '📋 SSE Order'),
    ('progress',            '📈 Progress Update'),
    ('hindrance',           '🚧 Hindrance'),
    ('inspection_request',  '🔍 Inspection Request'),
    ('document_submission', '📎 Document Submission'),
    ('general_remark',      '💬 General Remark'),
]
ITEM_CATEGORIES = {'order', 'progress', 'hindrance', 'inspection_request'}

CATEGORY_LABELS = dict(CATEGORIES)

REMOVE_KEYBOARD = {"remove_keyboard": True}


# ── Telegram API helpers ─────────────────────────────────────────────────────

def _api(token: str, method: str, **kwargs) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
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


def number_keyboard(n: int, per_row: int = 4, extras: list | None = None) -> list:
    nums = [str(i) for i in range(1, n + 1)]
    rows = [nums[i:i + per_row] for i in range(0, len(nums), per_row)]
    if extras:
        rows.append(extras)
    return rows


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
    """Return human-readable relative time string."""
    now   = timezone.now()
    delta = now - dt
    secs  = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{delta.days}d ago"


# ═══════════════════════════════════════════════════════════════════════════════
# SSE FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def sse_works_page(user, page: int):
    mappings = (
        WorkContractorTelegram.objects
        .filter(telegram_link__user=user, role='sse', is_active=True)
        .select_related('work')
        .order_by('work__loa_number')
    )
    all_works = [m.work for m in mappings]
    start     = page * PAGE_SIZE
    end       = start + PAGE_SIZE
    return all_works[start:end], len(all_works), len(all_works) > end


def show_loa_list(token: str, session: BotSession, user, page: int = 0):
    works, total, has_next = sse_works_page(user, page)
    if not works:
        send(token, session.telegram_chat_id,
             "⚠️ No LOAs assigned to you. Ask admin to assign you under Settings → LOA Parties.",
             remove_kb=True)
        reset_session(session)
        return

    lines = [f"<b>📋 New Site Register Entry</b> (page {page+1})\nSelect LOA:\n"]
    for i, w in enumerate(works, 1):
        lines.append(f"{i}. {w.loa_number} — {w.contractor_name or '—'}")

    extras = []
    if has_next:
        extras.append("Next ▶")
    if page > 0:
        extras.append("◀ Prev")
    extras.append("❌ Cancel")

    session.context = {"loa_page": page, "loa_choices": [w.id for w in works]}
    session.state   = "sse_select_loa"
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
    if has_next:
        extras.append("Next ▶")
    if page > 0:
        extras.append("◀ Prev")
    extras.append("❌ Cancel")

    session.context.update({"item_page": page, "item_choices": [item.id for item in page_items]})
    session.state = "sse_select_item"
    session.save(update_fields=["state", "context", "updated_at"])

    send(token, session.telegram_chat_id, "\n".join(lines),
         keyboard=number_keyboard(len(page_items), extras=extras))


def show_text_prompt(token: str, session: BotSession):
    ctx      = session.context
    item_line = f"\n<b>Item:</b> {ctx['work_item_desc']}" if ctx.get('work_item_id') else ""
    send(token, session.telegram_chat_id,
         f"<b>LOA:</b> {ctx['loa_number']}\n"
         f"<b>Type:</b> {ctx['category_label']}{item_line}\n\n"
         "✏️ <b>Type your message:</b>",
         remove_kb=True)
    session.state = "sse_type_text"
    session.save(update_fields=["state", "updated_at"])


def show_sse_confirm(token: str, session: BotSession):
    ctx      = session.context
    item_line = f"\n<b>Item:</b> {ctx['work_item_desc']}" if ctx.get('work_item_id') else ""
    send(token, session.telegram_chat_id,
         "📋 <b>Review your entry:</b>\n\n"
         f"<b>LOA:</b> {ctx['loa_number']}\n"
         f"<b>Contractor:</b> {ctx['contractor_name']}\n"
         f"<b>Type:</b> {ctx['category_label']}{item_line}\n"
         f"<b>Message:</b>\n{ctx['text']}\n\n"
         "Send this to the contractor?",
         keyboard=[["1. ✅ Confirm"], ["2. ❌ Cancel"]])
    session.state = "sse_confirm"
    session.save(update_fields=["state", "updated_at"])


def do_create_thread(token: str, session: BotSession, user):
    ctx = session.context

    with transaction.atomic():
        thread = SiteRegisterThread.objects.create(
            work_id           = ctx['work_id'],
            work_item_id      = ctx.get('work_item_id'),
            initiated_by_role = 'sse',
            category          = ctx['category'],
            initial_text      = ctx['text'],
            status            = 'open',
            created_by        = user,
        )

    contractor_links = (
        WorkContractorTelegram.objects
        .filter(work_id=ctx['work_id'], role='contractor', is_active=True)
        .select_related('telegram_link')
    )
    item_line  = f"\n📦 <b>Item:</b> {ctx['work_item_desc']}" if ctx.get('work_item_id') else ""
    notify_text = (
        f"📋 <b>New SSE Entry — SR-{thread.pk:06d}</b>\n\n"
        f"<b>LOA:</b> {ctx['loa_number']}\n"
        f"<b>Type:</b> {ctx['category_label']}{item_line}\n\n"
        f"{ctx['text']}\n\n"
        f"— <i>{user.first_name or user.username}</i>\n\n"
        f"Reply to this entry from the bot menu."
    )
    notified = 0
    for m in contractor_links:
        send(token, m.telegram_link.telegram_chat_id, notify_text)
        notified += 1

    send(token, session.telegram_chat_id,
         f"✅ <b>SR-{thread.pk:06d} created.</b> Notified {notified} contractor(s).",
         remove_kb=True)
    logger.info("SR-%06d created by %s, notified %d", thread.pk, user.username, notified)
    reset_session(session)


# ── SSE state handlers ────────────────────────────────────────────────────────

def handle_sse_select_loa(token: str, session: BotSession, user, text: str):
    ctx = session.context
    if text in ("Next ▶",):
        show_loa_list(token, session, user, page=ctx.get("loa_page", 0) + 1)
        return
    if text in ("◀ Prev",):
        show_loa_list(token, session, user, page=max(0, ctx.get("loa_page", 0) - 1))
        return
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send the number of your LOA.")
        return
    choices = ctx.get("loa_choices", [])
    if not (0 <= idx < len(choices)):
        send(token, session.telegram_chat_id, f"⚠️ Enter a number between 1 and {len(choices)}.")
        return

    from works.models import Work
    work = Work.objects.get(pk=choices[idx])
    session.context.update({
        "work_id":         work.id,
        "loa_number":      work.loa_number,
        "contractor_name": work.contractor_name or "—",
    })
    session.state = "sse_select_category"
    session.save(update_fields=["state", "context", "updated_at"])
    show_categories(token, session)


def handle_sse_select_category(token: str, session: BotSession, text: str):
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send the category number.")
        return
    if not (0 <= idx < len(CATEGORIES)):
        send(token, session.telegram_chat_id, f"⚠️ Enter a number between 1 and {len(CATEGORIES)}.")
        return

    cat_key, cat_label = CATEGORIES[idx]
    session.context.update({"category": cat_key, "category_label": cat_label})
    session.save(update_fields=["context", "updated_at"])

    if cat_key in ITEM_CATEGORIES:
        show_items(token, session, session.context["work_id"], page=0)
    else:
        show_text_prompt(token, session)


def handle_sse_select_item(token: str, session: BotSession, text: str):
    ctx = session.context
    if text == "Next ▶":
        show_items(token, session, ctx["work_id"], page=ctx.get("item_page", 0) + 1)
        return
    if text == "◀ Prev":
        show_items(token, session, ctx["work_id"], page=max(0, ctx.get("item_page", 0) - 1))
        return
    if text.strip() == "0":
        session.context.pop("work_item_id", None)
        session.context.pop("work_item_desc", None)
        session.save(update_fields=["context", "updated_at"])
        show_text_prompt(token, session)
        return
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send item number or 0 to skip.")
        return
    choices = ctx.get("item_choices", [])
    if not (0 <= idx < len(choices)):
        send(token, session.telegram_chat_id, f"⚠️ Enter 1–{len(choices)} or 0 to skip.")
        return

    item = WorkItem.objects.get(pk=choices[idx])
    desc = f"{item.schedule}/{item.serial_number} — {(item.item_desc or '').strip()[:60]}"
    session.context.update({"work_item_id": item.id, "work_item_desc": desc})
    session.save(update_fields=["context", "updated_at"])
    show_text_prompt(token, session)


def handle_sse_type_text(token: str, session: BotSession, text: str):
    session.context["text"] = text
    session.save(update_fields=["context", "updated_at"])
    show_sse_confirm(token, session)


def handle_sse_confirm(token: str, session: BotSession, user, text: str):
    if text.strip().startswith("1"):
        do_create_thread(token, session, user)
    elif text.strip().startswith("2"):
        send(token, session.telegram_chat_id, "❌ Entry cancelled.", remove_kb=True)
        reset_session(session)
    else:
        send(token, session.telegram_chat_id, "⚠️ Reply 1 to confirm or 2 to cancel.")


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACTOR FLOW
# ═══════════════════════════════════════════════════════════════════════════════

def contractor_threads_page(user, page: int):
    """Open/replied threads for works where user is a contractor."""
    work_ids = list(
        WorkContractorTelegram.objects
        .filter(telegram_link__user=user, role='contractor', is_active=True)
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


def _thread_summary_short(t: SiteRegisterThread) -> str:
    preview = t.initial_text[:60].replace('\n', ' ')
    return (
        f"SR-{t.pk:06d} | {t.work.loa_number} | "
        f"{CATEGORY_LABELS.get(t.category, t.category)} | "
        f"{_time_ago(t.created_at)}\n{preview}…"
    )


def _thread_summary_full(t: SiteRegisterThread) -> str:
    item_line = ""
    if t.work_item:
        wi = t.work_item
        item_line = f"\n<b>Item:</b> {wi.schedule}/{wi.serial_number} — {(wi.item_desc or '').strip()[:60]}"

    last_msgs = list(
        SiteRegisterMessage.objects
        .filter(thread=t)
        .select_related('sender')
        .order_by('-created_at')[:3]
    )
    last_msgs.reverse()

    replies = ""
    if last_msgs:
        parts = []
        for m in last_msgs:
            name = m.sender.first_name if m.sender else m.sender_role
            parts.append(f"  [{m.sender_role.upper()}] {name}: {m.message_text[:80]}")
        replies = "\n\n<b>Recent replies:</b>\n" + "\n".join(parts)

    return (
        f"<b>SR-{t.pk:06d}</b> — {CATEGORY_LABELS.get(t.category, t.category)}\n"
        f"<b>LOA:</b> {t.work.loa_number} | <b>Status:</b> {t.status.upper()}{item_line}\n"
        f"<b>Created:</b> {_time_ago(t.created_at)}\n\n"
        f"{t.initial_text}{replies}"
    )


def show_contractor_threads(token: str, session: BotSession, user, page: int = 0):
    threads, total, has_next = contractor_threads_page(user, page)

    if not threads and page == 0:
        send(token, session.telegram_chat_id,
             "✅ No open entries for your LOAs right now.",
             remove_kb=True)
        reset_session(session)
        return

    lines = [f"<b>📬 Open Entries</b> ({total} total, page {page+1}):\n"]
    for i, t in enumerate(threads, 1):
        lines.append(f"{i}. {_thread_summary_short(t)}\n")

    extras = []
    if has_next:
        extras.append("Next ▶")
    if page > 0:
        extras.append("◀ Prev")
    extras.append("❌ Cancel")

    session.context = {
        "thread_page":    page,
        "thread_choices": [t.pk for t in threads],
    }
    session.state = "contractor_select_thread"
    session.save(update_fields=["state", "context", "updated_at"])

    send(token, session.telegram_chat_id, "\n".join(lines),
         keyboard=number_keyboard(len(threads), extras=extras))


def show_thread_actions(token: str, session: BotSession, thread: SiteRegisterThread):
    summary = _thread_summary_full(thread)
    send(token, session.telegram_chat_id,
         summary + "\n\nWhat would you like to do?",
         keyboard=[["1. ✉️ Reply"], ["2. ✅ Mark Resolved"], ["3. ◀ Back"], ["❌ Cancel"]])
    session.context["thread_id"] = thread.pk
    session.state = "contractor_thread_action"
    session.save(update_fields=["state", "context", "updated_at"])


def show_contractor_reply_prompt(token: str, session: BotSession):
    send(token, session.telegram_chat_id,
         "✏️ <b>Type your reply:</b>",
         remove_kb=True)
    session.state = "contractor_type_reply"
    session.save(update_fields=["state", "updated_at"])


def show_contractor_confirm(token: str, session: BotSession):
    ctx = session.context
    send(token, session.telegram_chat_id,
         f"<b>Reply to SR-{ctx['thread_id']:06d}:</b>\n\n"
         f"{ctx['reply_text']}\n\n"
         "Send this reply?",
         keyboard=[["1. ✅ Send"], ["2. ❌ Cancel"]])
    session.state = "contractor_confirm_reply"
    session.save(update_fields=["state", "updated_at"])


def do_send_reply(token: str, session: BotSession, user):
    ctx = session.context
    try:
        thread = SiteRegisterThread.objects.select_related('work').get(pk=ctx['thread_id'])
    except SiteRegisterThread.DoesNotExist:
        send(token, session.telegram_chat_id, "⚠️ Entry not found (may have been closed).", remove_kb=True)
        reset_session(session)
        return

    with transaction.atomic():
        msg = SiteRegisterMessage.objects.create(
            thread       = thread,
            sender       = user,
            sender_role  = 'contractor',
            message_text = ctx['reply_text'],
        )
        thread.status = 'replied'
        thread.save(update_fields=['status'])

    # Notify SSE(s) on this LOA
    sse_links = (
        WorkContractorTelegram.objects
        .filter(work=thread.work, role='sse', is_active=True)
        .select_related('telegram_link')
    )
    notify_text = (
        f"💬 <b>Contractor Reply — SR-{thread.pk:06d}</b>\n\n"
        f"<b>LOA:</b> {thread.work.loa_number}\n"
        f"<b>Type:</b> {CATEGORY_LABELS.get(thread.category, thread.category)}\n\n"
        f"{ctx['reply_text']}\n\n"
        f"— <i>{user.first_name or user.username}</i>"
    )
    notified = 0
    for m in sse_links:
        send(token, m.telegram_link.telegram_chat_id, notify_text)
        notified += 1

    send(token, session.telegram_chat_id,
         f"✅ Reply sent. Notified {notified} SSE(s).",
         remove_kb=True)
    logger.info("SR-%06d reply by contractor %s, notified %d SSEs", thread.pk, user.username, notified)
    reset_session(session)


def do_mark_resolved(token: str, session: BotSession, user):
    ctx = session.context
    try:
        thread = SiteRegisterThread.objects.select_related('work').get(pk=ctx['thread_id'])
    except SiteRegisterThread.DoesNotExist:
        send(token, session.telegram_chat_id, "⚠️ Entry not found.", remove_kb=True)
        reset_session(session)
        return

    with transaction.atomic():
        SiteRegisterMessage.objects.create(
            thread       = thread,
            sender       = user,
            sender_role  = 'contractor',
            message_text = '✅ Marked as resolved by contractor.',
        )
        thread.status = 'verified'
        thread.save(update_fields=['status'])

    # Notify SSE(s)
    sse_links = (
        WorkContractorTelegram.objects
        .filter(work=thread.work, role='sse', is_active=True)
        .select_related('telegram_link')
    )
    notify_text = (
        f"✅ <b>SR-{thread.pk:06d} Resolved</b>\n\n"
        f"<b>LOA:</b> {thread.work.loa_number}\n"
        f"<b>Type:</b> {CATEGORY_LABELS.get(thread.category, thread.category)}\n\n"
        f"Marked as resolved by <i>{user.first_name or user.username}</i>."
    )
    for m in sse_links:
        send(token, m.telegram_link.telegram_chat_id, notify_text)

    send(token, session.telegram_chat_id,
         f"✅ SR-{thread.pk:06d} marked as resolved.",
         remove_kb=True)
    logger.info("SR-%06d resolved by contractor %s", thread.pk, user.username)
    reset_session(session)


# ── Contractor state handlers ─────────────────────────────────────────────────

def handle_contractor_select_thread(token: str, session: BotSession, user, text: str):
    ctx = session.context
    if text == "Next ▶":
        show_contractor_threads(token, session, user, page=ctx.get("thread_page", 0) + 1)
        return
    if text == "◀ Prev":
        show_contractor_threads(token, session, user, page=max(0, ctx.get("thread_page", 0) - 1))
        return
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        send(token, session.telegram_chat_id, "⚠️ Send the entry number.")
        return
    choices = ctx.get("thread_choices", [])
    if not (0 <= idx < len(choices)):
        send(token, session.telegram_chat_id, f"⚠️ Enter a number between 1 and {len(choices)}.")
        return

    try:
        thread = SiteRegisterThread.objects.select_related('work', 'work_item').get(pk=choices[idx])
    except SiteRegisterThread.DoesNotExist:
        send(token, session.telegram_chat_id, "⚠️ Entry no longer available.", remove_kb=True)
        reset_session(session)
        return

    show_thread_actions(token, session, thread)


def handle_contractor_thread_action(token: str, session: BotSession, user, text: str):
    t = text.strip()
    if t.startswith("1"):
        show_contractor_reply_prompt(token, session)
    elif t.startswith("2"):
        do_mark_resolved(token, session, user)
    elif t.startswith("3"):
        show_contractor_threads(token, session, user,
                                page=session.context.get("thread_page", 0))
    else:
        send(token, session.telegram_chat_id, "⚠️ Send 1, 2, or 3.")


def handle_contractor_type_reply(token: str, session: BotSession, text: str):
    session.context["reply_text"] = text
    session.save(update_fields=["context", "updated_at"])
    show_contractor_confirm(token, session)


def handle_contractor_confirm_reply(token: str, session: BotSession, user, text: str):
    if text.strip().startswith("1"):
        do_send_reply(token, session, user)
    elif text.strip().startswith("2"):
        send(token, session.telegram_chat_id, "❌ Reply cancelled.", remove_kb=True)
        reset_session(session)
    else:
        send(token, session.telegram_chat_id, "⚠️ Reply 1 to send or 2 to cancel.")


# ═══════════════════════════════════════════════════════════════════════════════
# OTP LINKING
# ═══════════════════════════════════════════════════════════════════════════════

def handle_start(token: str, chat_id: int, tg_user_id: int, text: str):
    parts    = text.strip().split(maxsplit=1)
    otp_code = parts[1].strip() if len(parts) > 1 else ""

    if not otp_code:
        send(token, chat_id,
             "👋 <b>Welcome to ManageWorks Site Register Bot.</b>\n\n"
             "To link your account, open the web app → Settings → Link Telegram, "
             "generate a code and send:\n<code>/start &lt;your-code&gt;</code>")
        return

    try:
        with transaction.atomic():
            otp = TelegramLinkOTP.objects.select_for_update().get(code=otp_code, used=False)
            if TelegramUserLink.objects.filter(telegram_user_id=tg_user_id).exclude(user=otp.user).exists():
                send(token, chat_id,
                     "⚠️ This Telegram account is already linked to a different ManageWorks account.")
                return
            TelegramUserLink.objects.update_or_create(
                user=otp.user,
                defaults={"telegram_user_id": tg_user_id, "telegram_chat_id": chat_id, "is_verified": True},
            )
            otp.used = True
            otp.save(update_fields=["used"])

        profile = getattr(otp.user, 'profile', None)
        role    = profile.role if profile else ('admin' if otp.user.is_staff else 'consignee')
        send(token, chat_id,
             f"✅ <b>Account linked!</b>\n\n"
             f"Connected as <b>{otp.user.first_name or otp.user.username}</b> ({role}).\n"
             "You will receive Site Register notifications here.")
        logger.info("Linked tg=%s → mw=%s", tg_user_id, otp.user.username)

    except TelegramLinkOTP.DoesNotExist:
        send(token, chat_id, "❌ Invalid or expired code. Generate a new one from the web app.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def dispatch(token: str, update: dict):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id    = message["chat"]["id"]
    tg_user_id = message["from"]["id"]
    text       = (message.get("text") or "").strip()

    if not text:
        return

    if text.startswith("/start"):
        handle_start(token, chat_id, tg_user_id, text)
        return

    user, role = resolve_user(tg_user_id)

    # Cancel — works from any state
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
             "⚠️ Account not linked.\n"
             "Go to Settings → Link Telegram in the web app.")
        return

    session = get_session(chat_id)

    if session.state == "idle":
        if role in ('sse', 'admin'):
            show_loa_list(token, session, user, page=0)
        elif role == 'contractor':
            show_contractor_threads(token, session, user, page=0)
        else:
            send(token, chat_id,
                 "ℹ️ You will receive notifications here when entries are created for your LOAs.")

    elif session.state == "sse_select_loa":
        handle_sse_select_loa(token, session, user, text)
    elif session.state == "sse_select_category":
        handle_sse_select_category(token, session, text)
    elif session.state == "sse_select_item":
        handle_sse_select_item(token, session, text)
    elif session.state == "sse_type_text":
        handle_sse_type_text(token, session, text)
    elif session.state == "sse_confirm":
        handle_sse_confirm(token, session, user, text)

    elif session.state == "contractor_select_thread":
        handle_contractor_select_thread(token, session, user, text)
    elif session.state == "contractor_thread_action":
        handle_contractor_thread_action(token, session, user, text)
    elif session.state == "contractor_type_reply":
        handle_contractor_type_reply(token, session, text)
    elif session.state == "contractor_confirm_reply":
        handle_contractor_confirm_reply(token, session, user, text)

    else:
        logger.warning("Unknown state %s chat=%s, resetting", session.state, chat_id)
        reset_session(session)
        dispatch(token, update)   # re-dispatch after reset


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

        token  = config.bot_token
        offset = 0

        self.stdout.write(self.style.SUCCESS("Telegram bot started. Listening for updates…"))
        logger.info("Telegram bot started")

        while True:
            try:
                data = _api(token, "getUpdates",
                    offset=offset,
                    timeout=POLL_TIMEOUT,
                    allowed_updates=["message"],
                )
                for update in data.get("result", []):
                    try:
                        dispatch(token, update)
                    except Exception as exc:
                        logger.exception("Error dispatching update %s: %s", update.get("update_id"), exc)
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
