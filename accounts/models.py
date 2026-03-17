from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.display_name or self.user.get_username()


class Membership(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_STAFF = "staff"
    ROLE_STAFF0 = "staff0"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "Admin"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_STAFF, "Staff"),
        (ROLE_STAFF0, "Staff (view only)"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STAFF)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user} ({self.role})"
