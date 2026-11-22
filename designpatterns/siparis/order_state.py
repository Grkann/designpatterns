# State
# Context: Order
# State: OrderState
# ConcreteState: AwaitingPaymentState, ReceivedState, PreparingState, OnTheWayState,
#                ReadyForPickupState, DeliveredState, CancelledState

from abc import ABC
from decimal import Decimal


class InvalidTransitionError(Exception):
    pass


class OrderState(ABC):
    name = ""
    is_final = False

    def mark_paid(self, order, payment):
        self.reject("ödeme kaydı")

    def accept(self, order):
        self.reject("restoran onayı")

    def hand_over(self, order):
        self.reject("teslimata çıkış")

    def complete(self, order):
        self.reject("teslim")

    def cancel(self, order, reason):
        self.reject("iptal")

    def reject(self, action):
        raise InvalidTransitionError(f"'{self.name}' durumundaki siparişte {action} yapılamaz.")


class AwaitingPaymentState(OrderState):
    name = "ÖDEME BEKLİYOR"

    def mark_paid(self, order, payment):
        order.apply_payment(payment)
        order.change_state(ReceivedState())

    def cancel(self, order, reason):
        order.change_state(CancelledState(reason, Decimal("0")))


class ReceivedState(OrderState):
    name = "ALINDI"

    def accept(self, order):
        order.change_state(PreparingState())

    def cancel(self, order, reason):
        order.change_state(CancelledState(reason, Decimal("1")))


class PreparingState(OrderState):
    name = "HAZIRLANIYOR"

    def hand_over(self, order):
        if order.requires_courier:
            order.change_state(OnTheWayState())
        else:
            order.change_state(ReadyForPickupState())

    def cancel(self, order, reason):
        # yemek hazırlanmaya başladığı için yarım iade
        order.change_state(CancelledState(reason, Decimal("0.5")))


class OnTheWayState(OrderState):
    name = "YOLDA"

    def complete(self, order):
        order.change_state(DeliveredState())


class ReadyForPickupState(OrderState):
    name = "GEL-AL İÇİN HAZIR"

    def complete(self, order):
        order.change_state(DeliveredState())


class DeliveredState(OrderState):
    name = "TESLİM EDİLDİ"
    is_final = True


class CancelledState(OrderState):
    name = "İPTAL EDİLDİ"
    is_final = True

    def __init__(self, reason, refund_ratio):
        self.reason = reason
        self.refund_ratio = refund_ratio
