from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render

from accounts.decorators import role_required
from accounts.utils import get_membership_for_user

from .forms import (
    StockAdjustForm,
    StockReceiveForm,
    StockSaleForm,
)
from .models import Product, StockMove


def _get_role(request):
    """Return role string or None if no membership."""
    membership = get_membership_for_user(request.user)
    if membership is None:
        return None
    return membership.role


@login_required
def dashboard(request):
    # If user logged in via Admin tab, redirect to admin panel
    if request.session.get("login_dest") == "/admin/":
        return redirect("/admin/")

    role = _get_role(request)
    if role is None:
        return render(request, "accounts/no_membership.html")

    stock_rows = (
        Product.objects.filter(is_active=True)
        .annotate(
            current_stock=Coalesce(
                Sum("stock_moves__qty_delta"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("name")
    )

    context = {
        "role": role,
        "stock_rows": stock_rows,
        "product_count": stock_rows.count(),
        "move_count": StockMove.objects.count(),
    }
    return render(request, "inventory/dashboard.html", context)


@login_required
def stock_move_list(request):
    role = _get_role(request)
    if role is None:
        return render(request, "accounts/no_membership.html")

    moves = StockMove.objects.select_related(
        "product", "location", "created_by"
    ).filter(created_by=request.user)

    # Date filtering
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if date_from:
        moves = moves.filter(created_at__date__gte=date_from)
    if date_to:
        moves = moves.filter(created_at__date__lte=date_to)

    # Summary aggregation
    summary = moves.aggregate(
        total_receive=Coalesce(
            Sum("qty_delta", filter=models.Q(reason=StockMove.REASON_RECEIVE)),
            Value(Decimal("0.00")),
            output_field=DecimalField(),
        ),
        total_sale=Coalesce(
            Sum("qty_delta", filter=models.Q(reason=StockMove.REASON_SALE)),
            Value(Decimal("0.00")),
            output_field=DecimalField(),
        ),
        total_adjust=Coalesce(
            Sum("qty_delta", filter=models.Q(reason=StockMove.REASON_ADJUST)),
            Value(Decimal("0.00")),
            output_field=DecimalField(),
        ),
        net_change=Coalesce(
            Sum("qty_delta"),
            Value(Decimal("0.00")),
            output_field=DecimalField(),
        ),
    )

    return render(
        request,
        "inventory/stock_move_list.html",
        {
            "role": role,
            "moves": moves,
            "summary": summary,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
@role_required("admin", "manager", "staff")
def stock_receive_create(request):
    role = _get_role(request)
    if role is None:
        return render(request, "accounts/no_membership.html")

    form = StockReceiveForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, "Stock receipt recorded.")
            return redirect("inventory:stock_move_list")
        except ValidationError as e:
            form.add_error(None, e.message)
    return render(
        request,
        "inventory/stock_move_form.html",
        {"form": form, "title": "Record Stock Receive"},
    )


@login_required
@role_required("admin", "manager", "staff")
def stock_sale_create(request):
    role = _get_role(request)
    if role is None:
        return render(request, "accounts/no_membership.html")

    form = StockSaleForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, "Stock sale recorded.")
            return redirect("inventory:stock_move_list")
        except ValidationError as e:
            form.add_error(None, e.message)
    return render(
        request,
        "inventory/stock_move_form.html",
        {"form": form, "title": "Record Stock Sale"},
    )


@login_required
@role_required("admin")
def stock_adjust_create(request):
    role = _get_role(request)
    if role is None:
        return render(request, "accounts/no_membership.html")

    form = StockAdjustForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, "Stock adjustment recorded.")
            return redirect("inventory:stock_move_list")
        except ValidationError as e:
            form.add_error(None, e.message)
    return render(
        request,
        "inventory/stock_move_form.html",
        {"form": form, "title": "Record Stock Adjustment"},
    )
