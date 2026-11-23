"""Grkann/designpatterns 1. Aşama (Builder & Adapter) ek testleri ve regresyon doğrulamaları."""

from __future__ import annotations

from decimal import Decimal
import unittest

from siparis.builder import (
    CorporateOrderBuilder,
    IndividualOrderBuilder,
    OrderBuildError,
    OrderDirector,
)
from siparis.external.globalcard import GlobalCardSDK
from siparis.external.kolaypay import KolayPayClient
from siparis.menu import default_catalog
from siparis.order import Customer
from siparis.payment import (
    FailoverPaymentGateway,
    GlobalCardAdapter,
    KolayPayAdapter,
)


class TestAsama1BuilderIyilestirmeleri(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()
        self.customer = Customer(id="C-01", name="Ayşe Demir", phone="05321112233")
        self.director = OrderDirector(self.catalog)

    def test_empty_customer_name_or_phone_rejected(self) -> None:
        builder = IndividualOrderBuilder()
        with self.assertRaises(OrderBuildError):
            builder.for_customer(Customer(id="C-02", name="   ", phone="05321112233"))
        with self.assertRaises(OrderBuildError):
            builder.for_customer(Customer(id="C-03", name="Ali", phone=""))

    def test_corporate_empty_company_name_rejected(self) -> None:
        builder = CorporateOrderBuilder()
        with self.assertRaises(OrderBuildError):
            builder.with_invoice("   ", "1234567890")

    def test_corporate_invoice_accepts_optional_tax_office(self) -> None:
        builder = CorporateOrderBuilder()
        order = (
            builder.for_customer(self.customer)
            .with_invoice("  Örnek A.Ş. ", "1234567890", tax_office="Kadıköy")
            .add_item(self.catalog["burger"], quantity=3)
            .deliver_to("Moda Cad. No:10", 4.5)
            .build()
        )
        assert order.invoice is not None
        self.assertEqual(order.invoice.company_name, "Örnek A.Ş.")
        self.assertEqual(order.invoice.tax_office, "Kadıköy")

    def test_clear_items_resets_only_items_fluently(self) -> None:
        ayran = self.catalog["ayran"]
        builder = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog["burger"], quantity=2)
            .clear_items()
            .add_item(ayran, quantity=1)
        )
        order = builder.build()
        self.assertEqual(len(order.items), 1)
        self.assertEqual(order.subtotal(), ayran.price())

    def test_director_family_feast_recipe_and_missing_catalog_key(self) -> None:
        builder = IndividualOrderBuilder().for_customer(self.customer)
        self.director.make_family_feast(builder)
        order = builder.build()
        self.assertEqual(len(order.items), 10)

        incomplete_director = OrderDirector({"burger": self.catalog["burger"]})
        with self.assertRaises(OrderBuildError):
            incomplete_director.make_student_menu(IndividualOrderBuilder())

    def test_existing_builder_rules_remain_intact(self) -> None:
        with self.assertRaises(OrderBuildError):
            CorporateOrderBuilder().with_coupon("OGRENCI15")

        with self.assertRaises(OrderBuildError):
            IndividualOrderBuilder().deliver_to("Uzak Mahalle", 16.0)

        order = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog["pizza"])
            .with_coupon(" ogrenci15 ")
            .build()
        )
        self.assertEqual(order.coupon_code, "OGRENCI15")
        self.assertEqual(order.coupon_rate, Decimal("0.15"))


class TestAsama1AdapterIyilestirmeleri(unittest.TestCase):
    def test_kolaypay_kurus_precision_with_decimal_and_float(self) -> None:
        adapter = KolayPayAdapter(KolayPayClient())
        self.assertEqual(adapter.to_kurus(Decimal("19.99")), 1999)
        self.assertEqual(adapter.to_kurus(19.99), 1999)
        self.assertEqual(adapter.to_kurus(Decimal("150.555")), 15056)

    def test_empty_transaction_id_refund_guarded_safely(self) -> None:
        kp = KolayPayAdapter(KolayPayClient())
        gc = GlobalCardAdapter(GlobalCardSDK())

        res_kp = kp.refund("", Decimal("10.00"))
        res_gc = gc.refund("", Decimal("10.00"))
        self.assertFalse(res_kp.success)
        self.assertFalse(res_gc.success)

    def test_failover_gateway_uses_primary_when_available(self) -> None:
        primary = KolayPayAdapter(KolayPayClient(islem_limiti_kurus=50_000))
        secondary = GlobalCardAdapter(GlobalCardSDK(max_amount=5000.0))
        gateway = FailoverPaymentGateway(primary, secondary)

        res = gateway.charge(Decimal("250.00"), "C-01")
        self.assertTrue(res.success)
        self.assertEqual(res.provider, "KolayPay")
        assert res.transaction_id is not None

        refund = gateway.refund(res.transaction_id, Decimal("100.00"))
        self.assertTrue(refund.success)
        self.assertEqual(refund.provider, "KolayPay")

    def test_failover_gateway_falls_back_to_secondary_on_limit_exceeded(self) -> None:
        primary = KolayPayAdapter(KolayPayClient(islem_limiti_kurus=20_000))
        secondary = GlobalCardAdapter(GlobalCardSDK(max_amount=5000.0))
        gateway = FailoverPaymentGateway(primary, secondary)

        res = gateway.charge(Decimal("1200.00"), "C-01")
        self.assertTrue(res.success)
        self.assertEqual(res.provider, "GlobalCard")
        assert res.transaction_id is not None
        self.assertTrue(res.transaction_id.startswith("gc_"))

        refund = gateway.refund(res.transaction_id, Decimal("600.00"))
        self.assertTrue(refund.success)
        self.assertEqual(refund.provider, "GlobalCard")

    def test_failover_gateway_returns_failure_when_both_providers_decline(self) -> None:
        primary = KolayPayAdapter(KolayPayClient(islem_limiti_kurus=10_000))
        secondary = GlobalCardAdapter(GlobalCardSDK(max_amount=100.0))
        gateway = FailoverPaymentGateway(primary, secondary)

        res = gateway.charge(Decimal("900.00"), "C-01")
        self.assertFalse(res.success)
        self.assertIsNone(res.transaction_id)


if __name__ == "__main__":
    unittest.main()
