from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.db.models import IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import QueryDict
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

    SORTABLE_FIELDS = {"sku", "shop_code", "name", "current_stock"}

    stock_rows = (
        Product.objects.filter(is_active=True)
        .annotate(
            current_stock=Coalesce(
                Sum("stock_moves__qty_delta", filter=models.Q(stock_moves__is_voided=False)),
                Value(0),
                output_field=IntegerField(),
            )
        )
    )

    # --- Sorting ---
    sort = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    sort_field = sort if sort in SORTABLE_FIELDS else "name"
    sort_dir = direction if direction in ("asc", "desc") else "asc"
    order_prefix = "-" if sort_dir == "desc" else ""
    stock_rows = stock_rows.order_by(f"{order_prefix}{sort_field}")

    # --- Filters ---
    search_q = request.GET.get("q", "").strip()
    if search_q:
        stock_rows = stock_rows.filter(
            Q(sku__icontains=search_q)
            | Q(shop_code__icontains=search_q)
            | Q(name__icontains=search_q)
        )

    size_filter = request.GET.get("size", "")
    if size_filter:
        stock_rows = stock_rows.filter(size=size_filter)

    stock_status = request.GET.get("stock", "")
    if stock_status == "out":
        stock_rows = stock_rows.filter(current_stock=0)
    elif stock_status == "low":
        stock_rows = stock_rows.filter(current_stock__gt=0, current_stock__lte=5)
    elif stock_status == "in":
        stock_rows = stock_rows.filter(current_stock__gt=5)

    # Build query strings for links
    filter_params = QueryDict(mutable=True)
    if search_q:
        filter_params["q"] = search_q
    if size_filter:
        filter_params["size"] = size_filter
    if stock_status:
        filter_params["stock"] = stock_status
    filter_only_qs = filter_params.urlencode()
    if sort_field != "name" or sort_dir != "asc":
        filter_params["sort"] = sort_field
        filter_params["dir"] = sort_dir
    filter_qs = filter_params.urlencode()

    product_count = stock_rows.count()

    paginator = Paginator(stock_rows, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "role": role,
        "stock_rows": page_obj,
        "page_obj": page_obj,
        "product_count": product_count,
        "move_count": StockMove.objects.filter(is_voided=False).count(),
        "search_q": search_q,
        "size_filter": size_filter,
        "size_choices": Product.SIZE_CHOICES,
        "stock_status": stock_status,
        "filter_qs": filter_qs,
        "filter_only_qs": filter_only_qs,
        "sort_field": sort_field,
        "sort_dir": sort_dir,
        "sortable_columns": [
            ("sku", "SKU"),
            ("shop_code", "Shop Code"),
            ("name", "Name"),
            ("current_stock", "Current Stock"),
        ],
    }
    return render(request, "inventory/dashboard.html", context)


@login_required
def stock_move_list(request):
    role = _get_role(request)
    if role is None:
        return render(request, "accounts/no_membership.html")

    moves = StockMove.objects.select_related(
        "product", "location", "created_by"
    ).filter(created_by=request.user, is_voided=False)

    # Date filtering
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if date_from:
        moves = moves.filter(move_date__gte=date_from)
    if date_to:
        moves = moves.filter(move_date__lte=date_to)

    # Summary aggregation
    summary = moves.aggregate(
        total_receive=Coalesce(
            Sum("qty_delta", filter=models.Q(reason=StockMove.REASON_RECEIVE)),
            Value(0),
            output_field=IntegerField(),
        ),
        total_sale=Coalesce(
            Sum("qty_delta", filter=models.Q(reason=StockMove.REASON_SALE)),
            Value(0),
            output_field=IntegerField(),
        ),
        total_adjust=Coalesce(
            Sum("qty_delta", filter=models.Q(reason=StockMove.REASON_ADJUST)),
            Value(0),
            output_field=IntegerField(),
        ),
        net_change=Coalesce(
            Sum("qty_delta"),
            Value(0),
            output_field=IntegerField(),
        ),
    )

    # Build filter query string for pagination links
    filter_params = QueryDict(mutable=True)
    if date_from:
        filter_params["date_from"] = date_from
    if date_to:
        filter_params["date_to"] = date_to
    filter_qs = filter_params.urlencode()

    # Pagination
    paginator = Paginator(moves, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "inventory/stock_move_list.html",
        {
            "role": role,
            "moves": page_obj,
            "page_obj": page_obj,
            "summary": summary,
            "date_from": date_from,
            "date_to": date_to,
            "filter_qs": filter_qs,
            "move_count": paginator.count,
            "elided_page_range": paginator.get_elided_page_range(page_obj.number),
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
