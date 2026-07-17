from django.contrib.auth.models import User
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from works.models import Work


@receiver(pre_save, sender=Work)
def _capture_old_hrms_id_for_autoconvert(sender, instance, **kwargs):
    """
    Own dedicated capture, independent of works.signals._capture_old_consignee /
    notifications.signals.on_work_pre_save. Both of those already stash the previous
    hrms_id on instance._old_hrms_id, but they disagree on None-vs-'' normalization
    and, since Django dispatches multiple receivers for the same signal/sender in
    registration order, whichever runs last silently overwrites the other's value —
    confirmed this actually happens (notifications' version runs second and lacks the
    `or ''` normalization, clobbering works.signals' correctly-normalized ''). Rather
    than depend on that fragile shared attribute, capture our own here.
    """
    if instance.pk:
        try:
            old = Work.objects.get(pk=instance.pk)
            instance._old_hrms_id_autoconvert = old.hrms_id or ''
        except Work.DoesNotExist:
            instance._old_hrms_id_autoconvert = ''
    else:
        instance._old_hrms_id_autoconvert = ''


@receiver(post_save, sender=Work)
def _auto_convert_admin_to_consignee(sender, instance, created, **kwargs):
    """
    One-way: the moment a Work/LOA is assigned to an Admin, they become a Consignee.
    Reverting Consignee -> Admin is manual only (via UpdateRoleView), never automatic.
    Super Admin (username='admin') is never auto-converted.
    """
    new_hrms = (instance.hrms_id or '').strip()
    if not new_hrms or new_hrms == 'admin':
        return

    old_hrms = getattr(instance, '_old_hrms_id_autoconvert', '').strip()
    if not created and old_hrms == new_hrms:
        return  # unchanged assignment

    try:
        user = User.objects.select_related('profile').get(username=new_hrms)
    except User.DoesNotExist:
        return

    profile = getattr(user, 'profile', None)
    if profile is not None and profile.role == 'admin':
        profile.role = 'consignee'
        profile.save(update_fields=['role'])
