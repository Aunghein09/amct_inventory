from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import DailyVoucher, Location, Product, StockMove


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "display_size",
        "cost",
        "selling_price1",
        "selling_price2",
        "accessory_price",
        "is_active",
    )
    list_filter = ("is_active", "size")
    search_fields = ("sku", "shop_code", "name", "barcode")
    list_per_page = 30

    fieldsets = (
        (None, {
            "fields": ("product_image_display",),
        }),
        ("Details", {
            "fields": (
                "sku", "shop_code", "name", "size", "custom_size",
                "image", "cost",
                "selling_price1", "selling_price2", "accessory_price",
                "barcode", "is_active",
            ),
        }),
    )

    readonly_fields = ("product_image_display",)

    def product_image_display(self, obj):
        if obj.image:
            return format_html(
                '<div style="text-align:center; margin-bottom:1rem;">'
                '<img src="{}" style="max-height:300px; max-width:100%; border-radius:8px;" />'
                '</div>',
                obj.image.url,
            )
        return format_html('<p style="text-align:center; color:#999;">No image uploaded</p>')
    product_image_display.short_description = "Image Preview"

    def display_size(self, obj):
        return obj.display_size
    display_size.short_description = "Size"

    def get_readonly_fields(self, request, obj=None):
        """Make all fields read-only unless ?edit=1 is in the URL."""
        base = list(self.readonly_fields)
        if obj and "edit" not in request.GET:
            return base + [
                "sku", "shop_code", "name", "size", "custom_size",
                "image", "cost",
                "selling_price1", "selling_price2", "accessory_price",
                "barcode", "is_active",
            ]
        return base

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if "edit" not in request.GET:
            extra_context["show_edit_button"] = True
            edit_url = reverse("admin:inventory_product_change", args=[object_id])
            extra_context["edit_url"] = f"{edit_url}?edit=1"
        return super().change_view(request, object_id, form_url, extra_context)

    class Media:
        js = ("admin/js/product_size.js",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "product",
        "location",
        "qty_delta",
        "reason",
        "price_tier",
        "created_by",
        "voided_display",
    )
    list_filter = ("reason", "price_tier", "location", "is_voided")
    search_fields = ("product__sku", "product__name", "reference_id", "note")
    list_select_related = ("product", "location", "created_by")
    list_per_page = 30
    autocomplete_fields = ("product", "location")
    actions = ["void_selected_moves"]

    readonly_fields = ("id", "created_by", "created_at", "edited_at", "edited_by",
                        "is_voided", "voided_at", "voided_by")

    def voided_display(self, obj):
        if obj.is_voided:
            return format_html('<span style="color:red; font-weight:bold;">VOIDED</span>')
        if obj.edited_at:
            return format_html('<span style="color:#e09000; font-weight:bold;">Edited</span>')
        return ""
    voided_display.short_description = "Status"

    @admin.action(description="Void selected stock moves")
    def void_selected_moves(self, request, queryset):
        already_voided = queryset.filter(is_voided=True).count()
        to_void = queryset.filter(is_voided=False)
        count = to_void.count()
        now = timezone.now()
        to_void.update(is_voided=True, voided_at=now, voided_by=request.user)
        if count:
            self.message_user(request, f"{count} stock move(s) voided.")
        if already_voided:
            self.message_user(request, f"{already_voided} move(s) were already voided.")

    def get_readonly_fields(self, request, obj=None):
        base = list(self.readonly_fields)
        if obj and "edit" not in request.GET:
            return base + [
                "product", "location", "qty_delta",
                "reason", "price_tier", "note", "reference_id",
            ]
        return base

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj and not obj.is_voided:
            extra_context["show_void_button"] = True
            extra_context["void_url"] = reverse("admin:inventory_stockmove_void", args=[object_id])
        if "edit" not in request.GET:
            extra_context["show_edit_button"] = True
            edit_url = reverse("admin:inventory_stockmove_change", args=[object_id])
            extra_context["edit_url"] = f"{edit_url}?edit=1"
        return super().change_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        custom_urls = [
            path(
                "<path:object_id>/void/",
                self.admin_site.admin_view(self.void_view),
                name="inventory_stockmove_void",
            ),
        ]
        return custom_urls + super().get_urls()

    def void_view(self, request, object_id):
        obj = get_object_or_404(StockMove, pk=object_id)
        if request.method == "POST" and not obj.is_voided:
            obj.is_voided = True
            obj.voided_at = timezone.now()
            obj.voided_by = request.user
            obj.save(update_fields=["is_voided", "voided_at", "voided_by"])
            messages.success(request, f"Stock move {obj} has been voided.")
        return redirect(reverse("admin:inventory_stockmove_change", args=[object_id]))

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        else:
            from django.utils import timezone
            obj.edited_at = timezone.now()
            obj.edited_by = request.user
        super().save_model(request, obj, form, change)

    class Media:
        js = ("admin/js/stockmove_price_tier.js",)


@admin.register(DailyVoucher)
class DailyVoucherAdmin(admin.ModelAdmin):
    list_display = ("date", "payment_method", "payment_date", "subtotal", "accessory_total", "grand_total", "finalized_by", "finalized_at")
    list_filter = ("payment_method",)
    ordering = ("-date",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
