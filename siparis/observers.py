from .money import fmt, to_money
from .notifications import OrderObserver
from .order_state import (
    CancelledState,
    DeliveredState,
    OnTheWayState,
    PreparingState,
    ReadyForPickupState,
    ReceivedState,
)


class CustomerNotifier(OrderObserver):
    def __init__(self, output=print):
        self.output = output

    def update(self, event):
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
        self.output(f"[SMS → {order.customer.phone}] {text}")


class RestaurantPanel(OrderObserver):
    def __init__(self, output=print):
        self.output = output
        self.active_orders = set()

    def update(self, event):
        order = event.order
        if isinstance(event.new_state, ReceivedState):
            self.active_orders.add(order.id)
            self.output(f"[Restoran] Yeni sipariş #{order.id}: " + "; ".join(order.item_descriptions()))
        elif event.new_state.is_final:
            self.active_orders.discard(order.id)
            self.output(f"[Restoran] #{order.id} kapandı ({event.new_state.name}). Aktif: {len(self.active_orders)}")


class CourierDispatcher(OrderObserver):
    def __init__(self, couriers, output=print):
        self.available = list(couriers)
        self.output = output
        self.assignments = {}

    def update(self, event):
        order = event.order
        if isinstance(event.new_state, PreparingState) and order.requires_courier:
            if len(self.available) == 0:
                self.output(f"[Kurye] #{order.id} için boşta kurye yok, sıraya alındı.")
                return
            courier = self.available.pop(0)
            self.assignments[order.id] = courier
            self.output(f"[Kurye] #{order.id} → {courier} atandı.")
        elif event.new_state.is_final and order.id in self.assignments:
            courier = self.assignments.pop(order.id)
            self.available.append(courier)
            self.output(f"[Kurye] {courier} yeniden müsait.")


class RefundHandler(OrderObserver):
    def __init__(self, gateway, output=print):
        self.gateway = gateway
        self.output = output
        self.refunded = {}

    def update(self, event):
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
