# State (Davranışsal) — 3. Aşama İyileştirilmiş Sürüm
# Context: Order
# State: OrderState
# ConcreteState: AwaitingPaymentState, ReceivedState, PreparingState, OnTheWayState,
#                ReadyForPickupState, DeliveredState, CancelledState

from __future__ import annotations

from abc import ABC
from decimal import Decimal


class InvalidTransitionError(Exception):
    """Mevcut sipariş durumunda izin verilmeyen bir geçiş denendiğinde fırlatılır."""


class OrderState(ABC):
    name = ""
    is_final = False
    cancellation_refund_ratio: Decimal | None = None

    @property
    def can_cancel(self) -> bool:
        return self.cancellation_refund_ratio is not None

    def allowed_actions(self) -> tuple[str, ...]:
        """Bu durumda çağrılabilecek izinli işlem adlarını döner."""
        return ()

    def mark_paid(self, order, payment) -> None:
        self.reject("ödeme kaydı")

    def accept(self, order) -> None:
        self.reject("restoran onayı")

    def hand_over(self, order) -> None:
        self.reject("teslimata çıkış")

    def complete(self, order) -> None:
        self.reject("teslim")

    def cancel(self, order, reason: str) -> None:
        self.reject("iptal")

    def reject(self, action: str) -> None:
        raise InvalidTransitionError(f"'{self.name}' durumundaki siparişte {action} yapılamaz.")


class AwaitingPaymentState(OrderState):
    name = "ÖDEME BEKLİYOR"
    cancellation_refund_ratio = Decimal("0")

    def allowed_actions(self) -> tuple[str, ...]:
        return ("mark_paid", "cancel")

    def mark_paid(self, order, payment) -> None:
        order.apply_payment(payment)
        order.change_state(ReceivedState())

    def cancel(self, order, reason: str) -> None:
        order.change_state(CancelledState(reason, Decimal("0")))


class ReceivedState(OrderState):
    name = "ALINDI"
    cancellation_refund_ratio = Decimal("1")

    def allowed_actions(self) -> tuple[str, ...]:
        return ("accept", "cancel")

    def accept(self, order) -> None:
        order.change_state(PreparingState())

    def cancel(self, order, reason: str) -> None:
        order.change_state(CancelledState(reason, Decimal("1")))


class PreparingState(OrderState):
    name = "HAZIRLANIYOR"
    cancellation_refund_ratio = Decimal("0.5")

    def allowed_actions(self) -> tuple[str, ...]:
        return ("hand_over", "cancel")

    def hand_over(self, order) -> None:
        if order.requires_courier:
            order.change_state(OnTheWayState())
        else:
            order.change_state(ReadyForPickupState())

    def cancel(self, order, reason: str) -> None:
        # yemek hazırlanmaya başladığı için yarım iade
        order.change_state(CancelledState(reason, Decimal("0.5")))


class OnTheWayState(OrderState):
    name = "YOLDA"

    def allowed_actions(self) -> tuple[str, ...]:
        return ("complete",)

    def complete(self, order) -> None:
        order.change_state(DeliveredState())


class ReadyForPickupState(OrderState):
    name = "GEL-AL İÇİN HAZIR"

    def allowed_actions(self) -> tuple[str, ...]:
        return ("complete",)

    def complete(self, order) -> None:
        order.change_state(DeliveredState())


class DeliveredState(OrderState):
    name = "TESLİM EDİLDİ"
    is_final = True


class CancelledState(OrderState):
    name = "İPTAL EDİLDİ"
    is_final = True

    def __init__(self, reason: str, refund_ratio: Decimal) -> None:
        cleaned = reason.strip() if isinstance(reason, str) else ""
        self.reason = cleaned or "Belirtilmedi"
        self.refund_ratio = refund_ratio
