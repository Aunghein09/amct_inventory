import io
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q
from PIL import Image as PILImage


class Product(models.Model):
    SIZE_XS = "XS"
    SIZE_S = "S"
    SIZE_M = "M"
    SIZE_L = "L"
    SIZE_XL = "XL"
    SIZE_2XL = "2XL"
    SIZE_3XL = "3XL"
    SIZE_CUSTOM = "custom"
    SIZE_CHOICES = (
        (SIZE_XS, "XS"),
        (SIZE_S, "S"),
        (SIZE_M, "M"),
        (SIZE_L, "L"),
        (SIZE_XL, "XL"),
        (SIZE_2XL, "2XL"),
        (SIZE_3XL, "3XL"),
        (SIZE_CUSTOM, "Custom"),
    )

    MAX_IMAGE_SIZE = (800, 800)
    IMAGE_QUALITY = 85

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=64, unique=True)
    shop_code = models.CharField(max_length=64, blank=True, verbose_name="Shop Code")
    name = models.CharField(max_length=255)
    size = models.CharField(max_length=100, choices=SIZE_CHOICES, blank=True)
    custom_size = models.CharField(
        max_length=50, blank=True, help_text="Number/custom value when size is 'Custom'"
    )
    image = models.ImageField(upload_to="products/", blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    selling_price1 = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    selling_price2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    accessory_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    barcode = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        if self.selling_price1 < self.cost:
            raise ValidationError("Retail selling price cannot be lower than cost.")
        if self.selling_price2 is not None and self.selling_price2 < self.cost:
            raise ValidationError("Wholesale selling price cannot be lower than cost.")
        if self.accessory_price is not None and self.accessory_price < 0:
            raise ValidationError("Accessory price cannot be negative.")

    def save(self, *args, **kwargs):
        if self.image:
            self._compress_image()
        super().save(*args, **kwargs)

    def _compress_image(self):
        try:
            img = PILImage.open(self.image)
        except Exception:
            return
        img.thumbnail(self.MAX_IMAGE_SIZE, PILImage.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.IMAGE_QUALITY, optimize=True)
        name = self.image.name.rsplit(".", 1)[0] + ".jpg"
        self.image = ContentFile(buf.getvalue(), name=name)

    @property
    def display_size(self):
        if self.size == self.SIZE_CUSTOM:
            return self.custom_size or "Custom"
        return self.get_size_display() or "-"

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Location(models.Model):
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockMove(models.Model):
    REASON_RECEIVE = "receive"
    REASON_SALE = "sale"
    REASON_ADJUST = "adjust"
    REASON_TRANSFER_IN = "transfer_in"
    REASON_TRANSFER_OUT = "transfer_out"
    REASON_CHOICES = (
        (REASON_RECEIVE, "Receive"),
        (REASON_SALE, "Sale"),
        (REASON_ADJUST, "Adjust"),
        (REASON_TRANSFER_IN, "Transfer In"),
        (REASON_TRANSFER_OUT, "Transfer Out"),
    )

    TIER_RETAIL = "retail"
    TIER_WHOLESALE = "wholesale"
    PRICE_TIER_CHOICES = (
        (TIER_RETAIL, "Retail"),
        (TIER_WHOLESALE, "Wholesale"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="stock_moves"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="stock_moves",
        null=True,
        blank=True,
    )
    qty_delta = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    price_tier = models.CharField(
        max_length=20, choices=PRICE_TIER_CHOICES, blank=True,
        help_text="Applicable only for sale moves.",
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_moves_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reference_id = models.CharField(max_length=120, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_moves_edited",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=~Q(qty_delta=0), name="qty_delta_not_zero"),
        ]

    def clean(self):
        if self.reason in {self.REASON_RECEIVE, self.REASON_TRANSFER_IN} and self.qty_delta <= 0:
            raise ValidationError("Receive and transfer_in qty_delta must be positive.")
        if self.reason in {self.REASON_SALE, self.REASON_TRANSFER_OUT} and self.qty_delta >= 0:
            raise ValidationError("Sale and transfer_out qty_delta must be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.sku} {self.qty_delta} ({self.reason})"


class DailyVoucher(models.Model):
    PAYMENT_KPAY = "kpay"
    PAYMENT_KBZ_BANK = "kbzBank"
    PAYMENT_KPAY_KBZ = "kpay_kbzBank"
    PAYMENT_CASH = "cash"
    PAYMENT_CHOICES = (
        (PAYMENT_KPAY, "KPay"),
        (PAYMENT_KBZ_BANK, "KBZ Bank"),
        (PAYMENT_KPAY_KBZ, "KPay + KBZ Bank"),
        (PAYMENT_CASH, "Cash"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    payment_date = models.DateField(
        null=True, blank=True,
        help_text="Date the payment was made (may differ from voucher date).",
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    accessory_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    is_finalized = models.BooleanField(default=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalized_vouchers",
    )
    finalized_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Voucher {self.date} — {self.grand_total}"
