from decimal import Decimal

import pytest

from siparis.checkout import CheckoutService
from siparis.delivery import PickupDelivery, StandardDelivery
from siparis.external.kolaypay import KolayPayClient
from siparis.notifications import OrderObserver
from siparis.observers import CourierDispatcher, CustomerNotifier, RefundHandler, RestaurantPanel
from siparis.order_state import (
    CancelledState,
    DeliveredState,
    InvalidTransitionError,
    OnTheWayState,
    ReadyForPickupState,
)
from siparis.payment import KolayPayAdapter


class Recorder(OrderObserver):
    def __init__(self):
        self.events = []

    def update(self, event):
        self.events.append(event)


@pytest.fixture
def gateway():
    return KolayPayAdapter(KolayPayClient())


def pay(order, gateway, strategy=None):
    if strategy is None:
        strategy = StandardDelivery()
    CheckoutService(gateway).checkout(order, strategy)


def test_full_lifecycle(simple_order, gateway):
    rec = Recorder()
    simple_order.attach(rec)
    pay(simple_order, gateway)
    simple_order.accept()
    simple_order.hand_over()
    assert isinstance(simple_order.state, OnTheWayState)
    simple_order.complete()
    assert isinstance(simple_order.state, DeliveredState)

    names = [e.new_state.name for e in rec.events]
    assert names == ["ALINDI", "HAZIRLANIYOR", "YOLDA", "TESLİM EDİLDİ"]


def test_pickup_order(simple_order, gateway):
    pay(simple_order, gateway, PickupDelivery())
    simple_order.accept()
    simple_order.hand_over()
    assert isinstance(simple_order.state, ReadyForPickupState)


def test_invalid_transitions(simple_order, gateway):
    with pytest.raises(InvalidTransitionError):
        simple_order.accept()
    pay(simple_order, gateway)
    with pytest.raises(InvalidTransitionError):
        simple_order.complete()
    simple_order.accept()
    simple_order.hand_over()
    with pytest.raises(InvalidTransitionError):
        simple_order.cancel("geç kaldı")


def test_cancel_after_payment_full_refund(simple_order, gateway):
    pay(simple_order, gateway)
    simple_order.cancel("vazgeçti")
    assert isinstance(simple_order.state, CancelledState)
    assert simple_order.state.refund_ratio == Decimal("1")


def test_cancel_while_preparing_half_refund(simple_order, gateway):
    pay(simple_order, gateway)
    simple_order.accept()
    simple_order.cancel("vazgeçti")
    assert simple_order.state.refund_ratio == Decimal("0.5")


def test_observers(simple_order, gateway):
    log = []
    panel = RestaurantPanel(log.append)
    couriers = CourierDispatcher(["Ali"], log.append)
    refunds = RefundHandler(gateway, log.append)
    simple_order.attach(CustomerNotifier(log.append))
    simple_order.attach(panel)
    simple_order.attach(couriers)
    simple_order.attach(refunds)

    pay(simple_order, gateway)  # toplam 235 TL
    assert simple_order.id in panel.active_orders

    simple_order.accept()
    assert couriers.assignments == {simple_order.id: "Ali"}

    simple_order.cancel("adres yanlış")
    assert refunds.refunded[simple_order.id] == Decimal("117.50")
    assert couriers.assignments == {}
    assert simple_order.id not in panel.active_orders
    assert any("iptal" in line for line in log if line.startswith("[SMS"))


def test_no_refund_before_payment(simple_order, gateway):
    log = []
    refunds = RefundHandler(gateway, log.append)
    simple_order.attach(refunds)
    simple_order.cancel("vazgeçti")
    assert refunds.refunded == {}
    assert log == []


def test_detach(simple_order, gateway):
    rec = Recorder()
    simple_order.attach(rec)
    simple_order.attach(rec)
    pay(simple_order, gateway)
    simple_order.detach(rec)
    simple_order.accept()
    assert len(rec.events) == 1
