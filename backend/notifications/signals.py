from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User

_SR_CATEGORY_LABELS = {
    'order':               'Rly Official Order',
    'progress':            'Progress Update',
    'hindrance':           'Hindrance',
    'inspection_request':  'Inspection Request',
    'document_submission': 'Document Submission',
    'general_remark':      'General Remark',
}

_WI_NOTIF_TYPE = {
    'supply':              'ss_entry',
    'supply_installation': 'si_entry',
    'execution':           'ee_entry',
}

_WI_LABEL = {
    'supply':              'SS Entry (Supply)',
    'supply_installation': 'SI Entry (Supply & Installation)',
    'execution':           'EE Entry (Execution)',
}


def _recipients(work):
    admins = list(User.objects.filter(is_staff=True))
    admin_ids = {u.pk for u in admins}
    consignees = []
    if work.hrms_id:
        consignees = list(User.objects.filter(username=work.hrms_id).exclude(pk__in=admin_ids))
    return admins + consignees


@receiver(post_save, sender='site_register.SiteRegisterThread')
def on_sr_thread_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notification
    cat_label = _SR_CATEGORY_LABELS.get(instance.category, instance.category)
    loa = instance.work.loa_number or f'LOA #{instance.work_id}'
    for user in _recipients(instance.work):
        Notification.objects.create(
            user=user,
            notif_type='new_sr',
            title=f'New SR Entry — {instance.sr_number}',
            body=f'{cat_label} · {loa}',
            thread=instance,
        )


@receiver(post_save, sender='works.WorkItemEntry')
def on_work_item_entry_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notification
    category = instance.work_item.category or ''
    notif_type = _WI_NOTIF_TYPE.get(category)
    if not notif_type:
        return
    work = instance.work_item.work
    loa = work.loa_number or f'LOA #{work.pk}'
    item_desc = instance.work_item.item_desc or instance.work_item.serial_number or f'Item #{instance.work_item_id}'
    for user in _recipients(work):
        Notification.objects.create(
            user=user,
            notif_type=notif_type,
            title=f'{_WI_LABEL[category]} — {loa}',
            body=f'{item_desc} · Qty: {instance.quantity}',
        )


@receiver(pre_save, sender='works.Work')
def on_work_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_hrms_id = old.hrms_id
        except sender.DoesNotExist:
            instance._old_hrms_id = None
    else:
        instance._old_hrms_id = None


@receiver(post_save, sender='works.Work')
def on_work_saved(sender, instance, created, **kwargs):
    if created:
        return
    old_hrms = getattr(instance, '_old_hrms_id', None)
    new_hrms = instance.hrms_id
    if not old_hrms or old_hrms == new_hrms:
        return
    from .models import Notification
    try:
        old_user = User.objects.get(username=old_hrms)
    except User.DoesNotExist:
        return
    loa = instance.loa_number or f'LOA #{instance.pk}'
    Notification.objects.create(
        user=old_user,
        notif_type='loa_unassigned',
        title=f'Work Unassigned — {loa}',
        body='You have been removed from this work order by the administrator.',
    )


@receiver(post_save, sender='mb_details.MBRecord')
def on_mb_record_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notification
    work = instance.work
    loa = work.loa_number or f'LOA #{work.pk}'
    md = instance.measurement_date
    if md and isinstance(md, str):
        from datetime import date as _date
        try:
            md = _date.fromisoformat(md)
        except ValueError:
            md = None
    date_str = f' on {md.strftime("%d %b %Y")}' if md else ''
    for user in _recipients(work):
        Notification.objects.create(
            user=user,
            notif_type='financial',
            title=f'Financial Update — {loa}',
            body=f'MB #{instance.mb_number} recorded{date_str}',
        )
