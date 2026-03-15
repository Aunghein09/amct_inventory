from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Location, Product, StockMove
from .services import record_stock_move


class BaseStockMoveForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.none())
    location = forms.ModelChoiceField(queryset=Location.objects.none(), required=False)
    quantity = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    note = forms.CharField(widget=forms.Textarea, required=False)
    reference_id = forms.CharField(max_length=120, required=False)

    reason = None
    quantity_sign = Decimal("1")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["product"].queryset = Product.objects.filter(is_active=True)
        self.fields["location"].queryset = Location.objects.all()

    def save(self):
        if self.reason is None:
            raise ValidationError("Reason is required.")
        quantity = self.cleaned_data["quantity"] * self.quantity_sign
        return record_stock_move(
            product=self.cleaned_data["product"],
            location=self.cleaned_data["location"],
            qty_delta=quantity,
            reason=self.reason,
            note=self.cleaned_data["note"],
            reference_id=self.cleaned_data["reference_id"],
            created_by=self.user,
            prevent_negative=True,
        )


class StockReceiveForm(BaseStockMoveForm):
    reason = StockMove.REASON_RECEIVE
    quantity_sign = Decimal("1")


class StockAdjustForm(BaseStockMoveForm):
    DIRECTION_INCREASE = "increase"
    DIRECTION_DECREASE = "decrease"
    DIRECTION_CHOICES = (
        (DIRECTION_INCREASE, "Increase (+)"),
        (DIRECTION_DECREASE, "Decrease (-)"),
    )

    direction = forms.ChoiceField(choices=DIRECTION_CHOICES)
    reason = StockMove.REASON_ADJUST
    quantity_sign = Decimal("1")  # overridden in save

    def save(self):
        direction = self.cleaned_data["direction"]
        if direction == self.DIRECTION_DECREASE:
            self.quantity_sign = Decimal("-1")
        else:
            self.quantity_sign = Decimal("1")
        return super().save()


class StockSaleForm(BaseStockMoveForm):
    PRICE_RETAIL = "retail"
    PRICE_WHOLESALE = "wholesale"
    PRICE_CHOICES = (
        (PRICE_RETAIL, "Retail (selling_price1)"),
        (PRICE_WHOLESALE, "Wholesale (selling_price2)"),
    )

    price_tier = forms.ChoiceField(choices=PRICE_CHOICES, initial=PRICE_RETAIL)
    reason = StockMove.REASON_SALE
    quantity_sign = Decimal("-1")

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        price_tier = cleaned_data.get("price_tier")
        if not product or not price_tier:
            return cleaned_data

        if price_tier == self.PRICE_RETAIL:
            cleaned_data["unit_price"] = product.selling_price1
            return cleaned_data

        if product.selling_price2 is None:
            self.add_error("price_tier", "This product does not have a wholesale price.")
            return cleaned_data

        cleaned_data["unit_price"] = product.selling_price2
        return cleaned_data

    def save(self):
        unit_price = self.cleaned_data["unit_price"]
        quantity = self.cleaned_data["quantity"]
        line_total = (unit_price * quantity).quantize(Decimal("0.01"))

        pricing_note = (
            f"sale_price_tier={self.cleaned_data['price_tier']};"
            f"unit_price={unit_price:.2f};line_total={line_total:.2f}"
        )
        original_note = self.cleaned_data["note"].strip()
        self.cleaned_data["note"] = (
            f"{pricing_note} | {original_note}" if original_note else pricing_note
        )
        quantity_val = self.cleaned_data["quantity"] * self.quantity_sign
        return record_stock_move(
            product=self.cleaned_data["product"],
            location=self.cleaned_data["location"],
            qty_delta=quantity_val,
            reason=self.reason,
            note=self.cleaned_data["note"],
            reference_id=self.cleaned_data["reference_id"],
            price_tier=self.cleaned_data["price_tier"],
            created_by=self.user,
            prevent_negative=True,
        )
