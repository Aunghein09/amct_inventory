from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Membership

from .forms import StockSaleForm
from .models import Product, StockMove
from .services import get_current_stock, record_stock_move


class InventoryLedgerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="staff", password="pass")
        Membership.objects.create(user=self.user, role=Membership.ROLE_ADMIN)
        self.product = Product.objects.create(
            sku="SKU001",
            name="Sample",
            cost=Decimal("5.00"),
            selling_price1=Decimal("8.00"),
            selling_price2=Decimal("7.00"),
        )

    def test_current_stock_comes_from_move_sum(self):
        record_stock_move(
            product=self.product,
            qty_delta=10,
            reason=StockMove.REASON_RECEIVE,
            created_by=self.user,
        )
        record_stock_move(
            product=self.product,
            qty_delta=-3,
            reason=StockMove.REASON_SALE,
            created_by=self.user,
        )
        self.assertEqual(get_current_stock(product=self.product), 7)

    def test_sale_cannot_make_stock_negative(self):
        with self.assertRaises(ValidationError):
            record_stock_move(
                product=self.product,
                qty_delta=-1,
                reason=StockMove.REASON_SALE,
                created_by=self.user,
            )

    def test_stock_move_editable_by_admin(self):
        move = record_stock_move(
            product=self.product,
            qty_delta=5,
            reason=StockMove.REASON_RECEIVE,
            created_by=self.user,
        )
        move.qty_delta = 8
        move.save()
        move.refresh_from_db()
        self.assertEqual(move.qty_delta, 8)

    def test_sale_form_saves_selected_price_tier_in_note(self):
        record_stock_move(
            product=self.product,
            qty_delta=10,
            reason=StockMove.REASON_RECEIVE,
            created_by=self.user,
        )
        form = StockSaleForm(
            data={
                "product": f"{self.product.sku} - {self.product.name}",
                "location": "",
                "quantity": "2",
                "price_tier": "retail",
                "note": "",
                "reference_id": "INV-001",
            },
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        move = form.save()
        self.assertIn("sale_price_tier=retail", move.note)
        self.assertIn("unit_price=8.00", move.note)
        self.assertIn("line_total=16.00", move.note)

    def test_sale_form_rejects_wholesale_when_missing(self):
        product_without_wholesale = Product.objects.create(
            sku="SKU002",
            name="No Wholesale",
            cost=Decimal("2.00"),
            selling_price1=Decimal("3.00"),
            selling_price2=None,
        )
        form = StockSaleForm(
            data={
                "product": f"{product_without_wholesale.sku} - {product_without_wholesale.name}",
                "location": "",
                "quantity": "1",
                "price_tier": "wholesale",
                "note": "",
                "reference_id": "",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("price_tier", form.errors)
