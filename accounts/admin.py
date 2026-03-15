from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import Membership, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name")
    search_fields = ("user__username", "display_name")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "edit_link")
    list_display_links = None
    list_filter = ("role",)
    search_fields = ("user__username",)

    def edit_link(self, obj):
        url = reverse("admin:accounts_membership_change", args=[obj.pk])
        return format_html('<a class="button" href="{}">Edit</a>', url)
    edit_link.short_description = "Edit"

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing existing — lock user
            return ("user",)
        return ()  # creating new — allow setting everything
