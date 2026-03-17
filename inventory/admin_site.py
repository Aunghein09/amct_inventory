import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin import AdminSite
from django.core.paginator import Paginator
from django.contrib.admin.apps import AdminConfig
from django.db.models import IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone


class InventoryAdminSite(AdminSite):
    site_header = "AMCT Inventory"
    site_title = "AMCT Inventory Admin"
    index_title = "Site administration"

    def logout(self, request, extra_context=None):
        """Redirect admin logout to the tabbed login page."""
        from django.contrib.auth import logout
        logout(request)
        return redirect("login")

    def get_urls(self):
        custom_urls = [
            path(
                "inventory/dashboard/",
                self.admin_view(self.inventory_dashboard_view),
                name="inventory_dashboard",
            ),
            path(
                "inventory/daily-voucher/",
                self.admin_view(self.daily_voucher_view),
                name="daily_voucher",
            ),
        ]
        return custom_urls + super().get_urls()

    def inventory_dashboard_view(self, request):
        from inventory.models import Product, StockMove

        SORTABLE_FIELDS = {"sku", "shop_code", "name", "size", "cost", "selling_price1", "selling_price2", "current_stock"}

        stock_rows = (
            Product.objects.filter(is_active=True)
            .annotate(
                current_stock=Coalesce(
                    Sum("stock_moves__qty_delta", filter=Q(stock_moves__is_voided=False)),
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
        from django.http import QueryDict
        filter_params = QueryDict(mutable=True)
        if search_q:
            filter_params["q"] = search_q
        if size_filter:
            filter_params["size"] = size_filter
        if stock_status:
            filter_params["stock"] = stock_status
        # filter_only_qs: used by sort header links (no sort/dir)
        filter_only_qs = filter_params.urlencode()
        # filter_qs: used by pagination links (includes sort/dir)
        if sort_field != "name" or sort_dir != "asc":
            filter_params["sort"] = sort_field
            filter_params["dir"] = sort_dir
        filter_qs = filter_params.urlencode()

        paginator = Paginator(stock_rows, 30)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            **self.each_context(request),
            "title": "Inventory Dashboard",
            "stock_rows": page_obj,
            "page_obj": page_obj,
            "product_count": stock_rows.count(),
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
                ("size", "Size"),
                ("cost", "Cost"),
                ("selling_price1", "Retail"),
                ("selling_price2", "Wholesale"),
                ("current_stock", "Current Stock"),
            ],
        }
        return TemplateResponse(request, "admin/inventory/dashboard.html", context)

    def daily_voucher_view(self, request):
        from inventory.models import DailyVoucher, StockMove

        date_str = request.GET.get("date", "")
        try:
            selected_date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            selected_date = timezone.localdate()

        # Check if already finalized
        voucher = DailyVoucher.objects.filter(date=selected_date).first()

        # Get all sale moves for this date
        sale_moves = (
            StockMove.objects.filter(
                reason=StockMove.REASON_SALE,
                created_at__date=selected_date,
                is_voided=False,
            )
            .select_related("product")
        )

        # Group by product + price_tier
        line_items = []
        subtotal = Decimal("0.00")
        accessory_total = Decimal("0.00")

        aggregated = {}
        for move in sale_moves:
            key = (move.product_id, move.price_tier or "retail")
            if key not in aggregated:
                tier = move.price_tier or "retail"
                if tier == "wholesale" and move.product.selling_price2 is not None:
                    rate = move.product.selling_price2
                else:
                    rate = move.product.selling_price1
                aggregated[key] = {
                    "product": move.product,
                    "price_tier": tier,
                    "rate": rate,
                    "qty": 0,
                    "accessory_price": move.product.accessory_price or Decimal("0.00"),
                }
            aggregated[key]["qty"] += abs(move.qty_delta)

        for item in aggregated.values():
            amount = item["rate"] * item["qty"]
            accessory_amount = item["accessory_price"] * item["qty"]
            line_items.append({
                "product": item["product"],
                "price_tier": item["price_tier"],
                "rate": item["rate"],
                "qty": item["qty"],
                "amount": amount,
                "accessory_price": item["accessory_price"],
                "accessory_amount": accessory_amount,
            })
            subtotal += amount
            accessory_total += accessory_amount

        grand_total = subtotal - accessory_total

        if request.method == "POST" and not voucher:
            payment_method = request.POST.get("payment_method", "")
            valid_methods = [c[0] for c in DailyVoucher.PAYMENT_CHOICES]
            if payment_method not in valid_methods:
                messages.error(request, "Invalid payment method.")
            elif not sale_moves.exists():
                messages.error(request, "No sales found for this date.")
            else:
                payment_date_str = request.POST.get("payment_date", "")
                try:
                    payment_date = datetime.date.fromisoformat(payment_date_str)
                except (ValueError, TypeError):
                    payment_date = selected_date
                DailyVoucher.objects.create(
                    date=selected_date,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    subtotal=subtotal,
                    accessory_total=accessory_total,
                    grand_total=grand_total,
                    is_finalized=True,
                    finalized_by=request.user,
                )
                messages.success(request, f"Voucher for {selected_date} has been finalized.")
                voucher = DailyVoucher.objects.get(date=selected_date)

        context = {
            **self.each_context(request),
            "title": f"Daily Voucher — {selected_date}",
            "selected_date": selected_date,
            "line_items": line_items,
            "subtotal": subtotal,
            "accessory_total": accessory_total,
            "grand_total": grand_total,
            "voucher": voucher,
            "payment_choices": DailyVoucher.PAYMENT_CHOICES,
        }
        return TemplateResponse(request, "admin/inventory/daily_voucher.html", context)

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label=app_label)
        for app in app_list:
            if app["app_label"] == "inventory":
                app["models"].append({
                    "name": "Dashboard",
                    "admin_url": "/admin/inventory/dashboard/",
                    "view_only": True,
                })
                app["models"].append({
                    "name": "Daily Voucher",
                    "admin_url": "/admin/inventory/daily-voucher/",
                    "view_only": True,
                })
                break
        return app_list


class InventoryAdminConfig(AdminConfig):
    default_site = "inventory.admin_site.InventoryAdminSite"
