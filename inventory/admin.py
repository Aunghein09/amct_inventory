from django.contrib import admin
from django.urls import reverse
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
        "edited_at",
        "edited_by",
    )
    list_filter = ("reason", "price_tier", "location")
    search_fields = ("product__sku", "product__name", "reference_id", "note")

    readonly_fields = ("id", "created_by", "created_at", "edited_at", "edited_by")

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
        if "edit" not in request.GET:
            extra_context["show_edit_button"] = True
            edit_url = reverse("admin:inventory_stockmove_change", args=[object_id])
            extra_context["edit_url"] = f"{edit_url}?edit=1"
        return super().change_view(request, object_id, form_url, extra_context)

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
