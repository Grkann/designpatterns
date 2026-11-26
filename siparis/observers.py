# ConcreteObserver sınıfları — 4. Aşama İyileştirilmiş Sürüm
# Mevcut dinleyiciler: CustomerNotifier, RestaurantPanel, CourierDispatcher, RefundHandler
# Yeni dinleyiciler: AuditLogObserver, AnalyticsObserver

from __future__ import annotations

from decimal import Decimal

from .money import fmt, to_money
from .notifications import OrderEvent, OrderObserver
from .order_state import (
    CancelledState,
    DeliveredState,
    OnTheWayState,
    PreparingState,
    ReadyForPickupState,
    ReceivedState,
)


class CustomerNotifier(OrderObserver):
    def __init__(self, output=print) -> None:
        self.output = output

    def update(self, event: OrderEvent) -> None:
        order = event.order
        state = event.new_state
        if isinstance(state, ReceivedState):
            text = f"#{order.id} numaralı siparişiniz alındı. Tutar: {fmt(order.paid_amount)}"
        elif isinstance(state, PreparingState):
            text = "Siparişiniz hazırlanıyor."
        elif isinstance(state, OnTheWayState):
            text = f"Siparişiniz yola çıktı. Tahmini süre: {order.price.estimated_minutes} dk."
        elif isinstance(state, ReadyForPickupState):
            text = "Siparişiniz hazır, restorandan teslim alabilirsiniz."
        elif isinstance(state, DeliveredState):
            text = "Afiyet olsun! Siparişiniz teslim edildi."
        elif isinstance(state, CancelledState):
            text = f"Siparişiniz iptal edildi ({state.reason})."
        else:
            return
        self.output(f"[SMS -> {order.customer.phone}] {text}")


class RestaurantPanel(OrderObserver):
    def __init__(self, output=print) -> None:
        self.output = output
        self.active_orders: set[int] = set()

    def update(self, event: OrderEvent) -> None:
        order = event.order
        if isinstance(event.new_state, ReceivedState):
            self.active_orders.add(order.id)
            self.output(f"[Restoran] Yeni sipariş #{order.id}: " + "; ".join(order.item_descriptions()))
        elif event.new_state.is_final:
            self.active_orders.discard(order.id)
            self.output(f"[Restoran] #{order.id} kapandı ({event.new_state.name}). Aktif: {len(self.active_orders)}")


class CourierDispatcher(OrderObserver):
    def __init__(self, couriers, output=print) -> None:
        self.available: list[str] = list(couriers)
        self.output = output
        self.assignments: dict[int, str] = {}
        self.waiting_queue: list = []

    def update(self, event: OrderEvent) -> None:
        order = event.order
        if isinstance(event.new_state, PreparingState) and order.requires_courier:
            if len(self.available) == 0:
                if order not in self.waiting_queue:
                    self.waiting_queue.append(order)
                self.output(f"[Kurye] #{order.id} için boşta kurye yok, sıraya alındı.")
                return
            courier = self.available.pop(0)
            self.assignments[order.id] = courier
            self.output(f"[Kurye] #{order.id} -> {courier} atandı.")
        elif event.new_state.is_final:
            # Bekleme kuyruğundaki iptal edilmiş siparişi temizle
            self.waiting_queue = [o for o in self.waiting_queue if o.id != order.id]
            if order.id in self.assignments:
                courier = self.assignments.pop(order.id)
                # Sırada bekleyen aktif sipariş varsa boşalan kuryeyi otomatik ata
                assigned_next = False
                while self.waiting_queue:
                    next_order = self.waiting_queue.pop(0)
                    if not next_order.state.is_final:
                        self.assignments[next_order.id] = courier
                        self.output(f"[Kurye] {courier} sıradaki #{next_order.id} siparişine atandı.")
                        assigned_next = True
                        break
                if not assigned_next:
                    self.available.append(courier)
                    self.output(f"[Kurye] {courier} yeniden müsait.")


class RefundHandler(OrderObserver):
    def __init__(self, gateway, output=print) -> None:
        self.gateway = gateway
        self.output = output
        self.refunded: dict[int, Decimal] = {}

    def update(self, event: OrderEvent) -> None:
        state = event.new_state
        order = event.order
        if not isinstance(state, CancelledState) or order.transaction_id is None:
            return
        if state.refund_ratio == 0:
            self.output(f"[İade] #{order.id} için iade yok.")
            return
        amount = to_money(order.paid_amount * state.refund_ratio)
        result = self.gateway.refund(order.transaction_id, amount)
        if result.success:
            self.refunded[order.id] = amount
            self.output(f"[İade] #{order.id}: {fmt(amount)} {self.gateway.provider_name} üzerinden iade edildi.")
        else:
            self.output(f"[İade] #{order.id} iadesi başarısız: {result.message}")


class AuditLogObserver(OrderObserver):
    """Yeni dinleyici: Tüm durum geçişlerini zaman damgasıyla denetim günlüğüne kaydeder."""

    def __init__(self) -> None:
        self.history: list[dict] = []

    def update(self, event: OrderEvent) -> None:
        self.history.append(
            {
                "order_id": event.order.id,
                "from": event.old_state.name,
                "to": event.new_state.name,
                "timestamp": event.timestamp,
            }
        )

    def history_for(self, order_id: int) -> list[dict]:
        return [entry for entry in self.history if entry["order_id"] == order_id]


class AnalyticsObserver(OrderObserver):
    """Yeni dinleyici: Sipariş yaşam döngüsü KPI ve gelir metriklerini canlı toplar."""

    def __init__(self) -> None:
        self.total_received: int = 0
        self.total_delivered: int = 0
        self.total_cancelled: int = 0
        self.delivered_revenue: Decimal = Decimal("0.00")
        self.cancellation_reasons: list[str] = []

    def update(self, event: OrderEvent) -> None:
        state = event.new_state
        order = event.order
        if isinstance(state, ReceivedState):
            self.total_received += 1
        elif isinstance(state, DeliveredState):
            self.total_delivered += 1
            self.delivered_revenue = to_money(self.delivered_revenue + order.paid_amount)
        elif isinstance(state, CancelledState):
            self.total_cancelled += 1
            self.cancellation_reasons.append(state.reason)
