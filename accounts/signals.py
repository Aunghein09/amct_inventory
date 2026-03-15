from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Membership, Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=Membership)
def sync_user_staff_and_group(sender, instance, **kwargs):
    """Keep User.is_staff and Manager group in sync with membership role."""
    user = instance.user
    manager_group, _ = Group.objects.get_or_create(name="Manager")

    if instance.role == Membership.ROLE_ADMIN:
        # Admins are superusers with staff access
        if not user.is_staff or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
        user.groups.remove(manager_group)
    elif instance.role == Membership.ROLE_MANAGER:
        # Managers get staff access (admin panel) but not superuser
        if not user.is_staff or user.is_superuser:
            user.is_staff = True
            user.is_superuser = False
            user.save(update_fields=["is_staff", "is_superuser"])
        user.groups.add(manager_group)
    else:
        # Staff: no admin panel access
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["is_staff", "is_superuser"])
        user.groups.remove(manager_group)
