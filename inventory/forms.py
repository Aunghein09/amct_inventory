from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from .models import Location, Product, StockMove
from .services import record_stock_move


class ProductSearchWidget(forms.TextInput):
    """Text input with a custom JS autocomplete dropdown."""

    def __init__(self, queryset=None, attrs=None):
        defaults = {"autocomplete": "off", "placeholder": "Type SKU or name..."}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)
        self.queryset = queryset or Product.objects.none()

    def render(self, name, value, attrs=None, renderer=None):
        if value and not isinstance(value, str):
            try:
                value = str(self.queryset.get(pk=value))
            except Product.DoesNotExist:
                value = ""
        elif value:
            try:
                value = str(self.queryset.get(pk=value))
            except (Product.DoesNotExist, ValueError):
                pass
        html = super().render(name, value, attrs, renderer)
        import json
        input_id = escape(attrs.get("id", "id_" + name) if attrs else "id_" + name)
        options_json = json.dumps([str(p) for p in self.queryset])
        # Inline JS autocomplete styled like Django admin Select2
        dropdown = '''
<div id="product-ac-wrap" style="position:relative;width:100%%;">
<div id="product-ac-list" style="
  display:none;position:absolute;top:0;left:0;right:0;z-index:999;
  background:#fff;border:1px solid #ccc;border-radius:6px;
  max-height:260px;overflow-y:auto;
  box-shadow:0 4px 12px rgba(0,0,0,.15);
"></div>
</div>
<script>
(function(){
  var opts=%(options)s;
  var inp=document.getElementById("%(input_id)s");
  var wrap=document.getElementById("product-ac-wrap");
  var box=document.getElementById("product-ac-list");

  function show(list){
    box.innerHTML="";
    if(!list.length){box.style.display="none";return;}
    list.forEach(function(t){
      var d=document.createElement("div");
      d.textContent=t;
      d.style.cssText="padding:8px 12px;cursor:pointer;font-size:0.95rem;border-bottom:1px solid #f0f0f0;";
      d.addEventListener("mouseenter",function(){d.style.background="#e8f0fe";});
      d.addEventListener("mouseleave",function(){d.style.background="#fff";});
      d.addEventListener("mousedown",function(e){
        e.preventDefault();
        inp.value=t;
        box.style.display="none";
      });
      box.appendChild(d);
    });
    box.style.display="block";
  }

  function filter(){
    var v=inp.value.toLowerCase();
    if(!v){show(opts.slice(0,30));return;}
    show(opts.filter(function(o){return o.toLowerCase().indexOf(v)!==-1;}).slice(0,30));
  }

  inp.addEventListener("focus",function(){filter();});
  inp.addEventListener("input",function(){filter();});
  inp.addEventListener("click",function(){filter();});

  document.addEventListener("mousedown",function(e){
    if(!wrap.contains(e.target) && e.target!==inp){
      box.style.display="none";
    }
  });
})()
</script>''' % {"options": options_json, "input_id": input_id}
        return mark_safe(str(html) + dropdown)


class ProductSearchField(forms.Field):
    """Field that accepts typed product text and resolves to a Product instance."""

    def __init__(self, queryset=None, **kwargs):
        self.queryset = queryset or Product.objects.none()
        kwargs.setdefault("widget", ProductSearchWidget(queryset=self.queryset))
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        if not value:
            raise ValidationError("This field is required.")
        value = value.strip()
        # Try matching "SKU - Name" format (extract SKU before " - ")
        sku = value.split(" - ")[0].strip() if " - " in value else value
        try:
            return self.queryset.get(sku=sku)
        except Product.DoesNotExist:
            pass
        # Fallback: try exact name match
        try:
            return self.queryset.get(name=value)
        except Product.DoesNotExist:
            pass
        raise ValidationError("Product not found. Please select from the list.")


class BaseStockMoveForm(forms.Form):
    product = ProductSearchField()
    location = forms.ModelChoiceField(queryset=Location.objects.none(), required=False)
    quantity = forms.IntegerField(min_value=1)
    note = forms.CharField(widget=forms.Textarea, required=False)
    reference_id = forms.CharField(max_length=120, required=False)

    reason = None
    quantity_sign = 1

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        qs = Product.objects.filter(is_active=True)
        self.fields["product"].queryset = qs
        self.fields["product"].widget.queryset = qs
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
    quantity_sign = 1


class StockAdjustForm(BaseStockMoveForm):
    DIRECTION_INCREASE = "increase"
    DIRECTION_DECREASE = "decrease"
    DIRECTION_CHOICES = (
        (DIRECTION_INCREASE, "Increase (+)"),
        (DIRECTION_DECREASE, "Decrease (-)"),
    )

    direction = forms.ChoiceField(choices=DIRECTION_CHOICES)
    reason = StockMove.REASON_ADJUST
    quantity_sign = 1  # overridden in save

    def save(self):
        direction = self.cleaned_data["direction"]
        if direction == self.DIRECTION_DECREASE:
            self.quantity_sign = -1
        else:
            self.quantity_sign = 1
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
    quantity_sign = -1

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
