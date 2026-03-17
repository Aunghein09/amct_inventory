from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import StockMove


def get_current_stock(product, location=None):
    moves = StockMove.objects.filter(product=product, is_voided=False)
    if location is not None:
        moves = moves.filter(location=location)
    total = moves.aggregate(total_qty=Sum("qty_delta"))["total_qty"]
    return total if total is not None else 0


@transaction.atomic
def record_stock_move(
    *,
    product,
    qty_delta,
    reason,
    created_by,
    location=None,
    note="",
    reference_id="",
    price_tier="",
    move_date=None,
    prevent_negative=True,
):
    qty_delta = int(qty_delta)
    current = get_current_stock(product=product, location=location)
    projected = current + qty_delta
    if prevent_negative and projected < 0:
        raise ValidationError("Stock cannot go negative.")

    kwargs = dict(
        product=product,
        location=location,
        qty_delta=qty_delta,
        reason=reason,
        price_tier=price_tier,
        note=note,
        created_by=created_by,
        reference_id=reference_id,
    )
    if move_date:
        kwargs["move_date"] = move_date
    return StockMove.objects.create(**kwargs)


@transaction.atomic
def transfer_stock(
    *,
    product,
    quantity,
    from_location,
    to_location,
    created_by,
    note="",
    reference_id="",
):
    quantity = int(quantity)
    if quantity <= 0:
        raise ValidationError("Transfer quantity must be positive.")
    if from_location == to_location:
        raise ValidationError("Source and destination locations must be different.")

    current_at_source = get_current_stock(product=product, location=from_location)
    if current_at_source - quantity < 0:
        raise ValidationError("Transfer would make source location stock negative.")

    transfer_out = StockMove.objects.create(
        product=product,
        location=from_location,
        qty_delta=-quantity,
        reason=StockMove.REASON_TRANSFER_OUT,
        note=note,
        created_by=created_by,
        reference_id=reference_id,
    )
    transfer_in = StockMove.objects.create(
        product=product,
        location=to_location,
        qty_delta=quantity,
        reason=StockMove.REASON_TRANSFER_IN,
        note=note,
        created_by=created_by,
        reference_id=reference_id,
    )
    return transfer_out, transfer_in
