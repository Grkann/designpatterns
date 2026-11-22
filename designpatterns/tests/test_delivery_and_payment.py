from decimal import Decimal

import pytest

from siparis.builder import IndividualOrderBuilder
from siparis.checkout import CheckoutService, PaymentFailedError
from siparis.delivery import ExpressDelivery, PickupDelivery, PriceCalculator, StandardDelivery
from siparis.external.globalcard import GlobalCardSDK
from siparis.external.kolaypay import KolayPayClient
from siparis.payment import GlobalCardAdapter, KolayPayAdapter, PaymentGateway


def test_standard_delivery_fee():
    s = StandardDelivery()
    assert s.fee(Decimal("100"), 1.0) == Decimal("20.00")
    assert s.fee(Decimal("100"), 4.5) == Decimal("32.50")
    assert s.fee(Decimal("400"), 10.0) == Decimal("0.00")


def test_express_and_pickup_fee():
    assert ExpressDelivery().fee(Decimal("999"), 2.5) == Decimal("65.00")
    assert PickupDelivery().fee(Decimal("10"), 5) == Decimal("0.00")
    assert PickupDelivery().requires_courier is False


def test_change_strategy_at_runtime(simple_order):
    calc = PriceCalculator(StandardDelivery())
    standard = calc.calculate(simple_order)
    calc.set_strategy(ExpressDelivery())
    express = calc.calculate(simple_order)

    assert standard.subtotal == Decimal("210.00")
    assert standard.delivery_fee == Decimal("25.00")
    assert express.delivery_fee == Decimal("69.00")
    assert express.estimated_minutes < standard.estimated_minutes


def test_coupon_applied_before_delivery_fee(menu, customer):
    order = (IndividualOrderBuilder().for_customer(customer)
             .add_item(menu["pizza"], 2)
             .with_coupon("HOSGELDIN10")
             .deliver_to("A", 1)
             .build())
    q = PriceCalculator(StandardDelivery()).calculate(order)
    assert q.discount == Decimal("48.00")
    assert q.delivery_fee == Decimal("0.00")  # 432 TL, 400 TL sınırının üstünde
    assert q.total == Decimal("432.00")


def check_gateway(gateway):
    assert isinstance(gateway, PaymentGateway)
    charged = gateway.charge(Decimal("123.45"), "C-1")
    assert charged.success
    assert gateway.refund(charged.transaction_id, Decimal("100.00")).success
    assert not gateway.refund(charged.transaction_id, Decimal("50.00")).success


def test_kolaypay_adapter():
    check_gateway(KolayPayAdapter(KolayPayClient()))


def test_globalcard_adapter():
    check_gateway(GlobalCardAdapter(GlobalCardSDK()))


def test_kolaypay_uses_kurus():
    client = KolayPayClient()
    KolayPayAdapter(client).charge(Decimal("19.99"), "C-1")
    assert client.islemler == {"KP-00001": 1999}


def test_failed_payment(simple_order):
    gateway = GlobalCardAdapter(GlobalCardSDK(max_amount=50))
    with pytest.raises(PaymentFailedError, match="declined"):
        CheckoutService(gateway).checkout(simple_order, StandardDelivery())
    assert simple_order.transaction_id is None
    assert simple_order.state.name == "ÖDEME BEKLİYOR"


def test_courier_needs_address(menu, customer):
    order = IndividualOrderBuilder().for_customer(customer).add_item(menu["kola"]).build()
    service = CheckoutService(KolayPayAdapter(KolayPayClient()))
    with pytest.raises(ValueError, match="adres"):
        service.checkout(order, StandardDelivery())
    service.checkout(order, PickupDelivery())
    assert order.state.name == "ALINDI"
