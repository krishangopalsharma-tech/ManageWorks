from django.db.models.signals import post_save, pre_save
from django.db.models import Q
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
    'supply':              'Supply',
    'supply_installation': 'Supply & Installation',
    'execution':           'Execution',
}


def _recipients(work):
    admins = list(User.objects.filter(
        Q(is_staff=True) | Q(profile__role='admin')
    ).distinct())
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
    creator = instance.created_by
    if creator:
        creator_name = creator.first_name or creator.username
    else:
        creator_name = loa
    for user in _recipients(instance.work):
        Notification.objects.create(
            user=user,
            notif_type='new_sr',
            title=instance.sr_number,
            body=f'{creator_name} · {cat_label}',
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
            title=f'{loa} · {_WI_LABEL[category]}',
            body=f'{item_desc} · Qty: {instance.quantity}',
        )


@receiver(post_save, sender='financial_progress.BillRecord')
def on_bill_record_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Notification
    work = instance.work
    loa = work.loa_number or f'LOA #{work.pk}'
    uploader = instance.uploaded_by
    uploader_name = (uploader.first_name or uploader.username) if uploader else loa
    for user in _recipients(work):
        Notification.objects.create(
            user=user,
            notif_type='financial',
            title=f'{loa} · Bill Uploaded',
            body=f'{uploader_name} · Bill {instance.bill_number}',
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


