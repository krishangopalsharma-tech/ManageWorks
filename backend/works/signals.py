import logging
import requests

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from works.models import Work

logger = logging.getLogger(__name__)


def _get_bot_token():
    from telegram_settings.models import TelegramBotConfig
    try:
        cfg = TelegramBotConfig.objects.filter(pk=1).first()
        return cfg.bot_token if (cfg and cfg.bot_token and cfg.is_active) else None
    except Exception:
        return None


def _find_consignee_chat(hrms_id: str):
    from site_register.models import TelegramUserLink, RlyTelegramLink
    if not hrms_id:
        return None, ''
    try:
        tg = TelegramUserLink.objects.select_related('user').get(
            user__username=hrms_id, is_verified=True
        )
        return tg.telegram_chat_id, tg.user.first_name or hrms_id
    except TelegramUserLink.DoesNotExist:
        pass
    try:
        rly = RlyTelegramLink.objects.get(hrms_id=hrms_id, is_verified=True)
        return rly.telegram_chat_id, rly.display_name
    except RlyTelegramLink.DoesNotExist:
        pass
    return None, ''


def _tg_send(token: str, chat_id: int, text: str):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={
            'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'
        }, timeout=10, headers={"Connection": "close"})
    except Exception as exc:
        logger.warning("LOA notification send failed chat=%s: %s", chat_id, exc)


@receiver(pre_save, sender=Work)
def _capture_old_consignee(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Work.objects.get(pk=instance.pk)
            instance._old_hrms_id = old.hrms_id or ''
        except Work.DoesNotExist:
            instance._old_hrms_id = None
    else:
        instance._old_hrms_id = None  # new Work


@receiver(post_save, sender=Work)
def _notify_consignee_loa_change(sender, instance, created, **kwargs):
    token = _get_bot_token()
    if not token:
        return

    old_hrms = getattr(instance, '_old_hrms_id', None)
    # If pre_save didn't run (e.g. update_fields omitted hrms_id), skip
    if old_hrms is None and not created:
        return

    new_hrms   = (instance.hrms_id or '').strip()
    loa        = instance.loa_number or '?'
    work_name  = (instance.name_of_work or '')[:80]
    contractor = instance.contractor_name or '?'

    if created:
        if new_hrms:
            chat_id, _ = _find_consignee_chat(new_hrms)
            if chat_id:
                _tg_send(token, chat_id,
                    f"📋 <b>New LOA Assigned to You</b>\n\n"
                    f"<b>LOA No:</b> {loa}\n"
                    f"<b>Work:</b> {work_name}\n"
                    f"<b>Contractor:</b> {contractor}"
                )
    else:
        old_hrms = (old_hrms or '').strip()
        if old_hrms != new_hrms:
            if old_hrms:
                old_chat, _ = _find_consignee_chat(old_hrms)
                if old_chat:
                    _tg_send(token, old_chat,
                        f"ℹ️ <b>LOA Reassigned (No Longer Yours)</b>\n\n"
                        f"<b>LOA No:</b> {loa}\n"
                        f"<b>Work:</b> {work_name}\n"
                        "This LOA has been reassigned to another consignee."
                    )
            if new_hrms:
                new_chat, _ = _find_consignee_chat(new_hrms)
                if new_chat:
                    _tg_send(token, new_chat,
                        f"📋 <b>LOA Assigned to You</b>\n\n"
                        f"<b>LOA No:</b> {loa}\n"
                        f"<b>Work:</b> {work_name}\n"
                        f"<b>Contractor:</b> {contractor}"
                    )
