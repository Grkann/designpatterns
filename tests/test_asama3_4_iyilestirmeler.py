"""Grkann/designpatterns 3. ve 4. Aşama (State & Observer) + 6 Kalıp Uçtan Uca Entegrasyon Testleri."""

from __future__ import annotations

from decimal import Decimal
import unittest

from siparis.builder import CorporateOrderBuilder, IndividualOrderBuilder, OrderDirector
from siparis.checkout import CheckoutService
from siparis.delivery import PickupDelivery, ScheduledDelivery, StandardDelivery
from siparis.external.globalcard import GlobalCardSDK
from siparis.external.kolaypay import KolayPayClient
from siparis.menu import ExtraCheese, GlutenFreeBase, LargePortion, default_catalog
from siparis.notifications import OrderEvent, OrderObserver
from siparis.observers import (
    AnalyticsObserver,
    AuditLogObserver,
    CourierDispatcher,
    CustomerNotifier,
    RefundHandler,
    RestaurantPanel,
)
from siparis.order import Customer, PaymentRecord
from siparis.order_state import (
    AwaitingPaymentState,
    CancelledState,
    DeliveredState,
    InvalidTransitionError,
    OnTheWayState,
    PreparingState,
    ReadyForPickupState,
    ReceivedState,
)
from siparis.payment import FailoverPaymentGateway, GlobalCardAdapter, KolayPayAdapter


class TestAsama3StateIyilestirmeleri(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()
        self.customer = Customer(id="C-30", name="Mert Yılmaz", phone="05321002030")

    def _new_order(self, distance_km: float = 4.0):
        return (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog["burger"], quantity=2)
            .deliver_to("Moda Cad. No:15", distance_km)
            .build()
        )

    def test_allowed_actions_and_refund_ratios_across_states(self) -> None:
        self.assertEqual(AwaitingPaymentState().allowed_actions(), ("mark_paid", "cancel"))
        self.assertEqual(AwaitingPaymentState().cancellation_refund_ratio, Decimal("0"))
        self.assertTrue(ReceivedState().can_cancel)
        self.assertEqual(ReceivedState().cancellation_refund_ratio, Decimal("1"))
        self.assertEqual(PreparingState().cancellation_refund_ratio, Decimal("0.5"))
        self.assertFalse(OnTheWayState().can_cancel)
        self.assertEqual(OnTheWayState().allowed_actions(), ("complete",))
        self.assertEqual(ReadyForPickupState().allowed_actions(), ("complete",))
        self.assertEqual(DeliveredState().allowed_actions(), ())
        self.assertEqual(CancelledState("test", Decimal("0")).allowed_actions(), ())

    def test_full_delivery_state_transitions(self) -> None:
        order = self._new_order()
        gateway = KolayPayAdapter(KolayPayClient())
        CheckoutService(gateway).checkout(order, StandardDelivery())

        self.assertIsInstance(order.state, ReceivedState)
        order.accept()
        self.assertIsInstance(order.state, PreparingState)
        order.hand_over()
        self.assertIsInstance(order.state, OnTheWayState)
        order.complete()
        self.assertIsInstance(order.state, DeliveredState)
        self.assertTrue(order.state.is_final)

    def test_pickup_order_transitions_to_ready_for_pickup(self) -> None:
        order = self._new_order()
        gateway = KolayPayAdapter(KolayPayClient())
        CheckoutService(gateway).checkout(order, PickupDelivery())

        order.accept()
        order.hand_over()
        self.assertIsInstance(order.state, ReadyForPickupState)
        order.complete()
        self.assertIsInstance(order.state, DeliveredState)

    def test_cancellation_refund_ratios_and_empty_reason_normalization(self) -> None:
        order_unpaid = self._new_order()
        order_unpaid.cancel("   ")
        self.assertIsInstance(order_unpaid.state, CancelledState)
        self.assertEqual(order_unpaid.state.reason, "Belirtilmedi")
        self.assertEqual(order_unpaid.state.refund_ratio, Decimal("0"))

        order_received = self._new_order()
        CheckoutService(KolayPayAdapter(KolayPayClient())).checkout(order_received, StandardDelivery())
        order_received.cancel("Yanlış adres")
        self.assertEqual(order_received.state.refund_ratio, Decimal("1"))

        order_preparing = self._new_order()
        CheckoutService(KolayPayAdapter(KolayPayClient())).checkout(order_preparing, StandardDelivery())
        order_preparing.accept()
        order_preparing.cancel("Vazgeçtim")
        self.assertEqual(order_preparing.state.refund_ratio, Decimal("0.5"))

    def test_invalid_transitions_raise_error(self) -> None:
        order = self._new_order()
        with self.assertRaises(InvalidTransitionError):
            order.accept()  # Ödeme alınmadan onaylanamaz
        with self.assertRaises(InvalidTransitionError):
            order.hand_over()

        CheckoutService(KolayPayAdapter(KolayPayClient())).checkout(order, StandardDelivery())
        order.accept()
        order.hand_over()
        with self.assertRaises(InvalidTransitionError):
            order.cancel("Yoldayken iptal")

        order.complete()
        with self.assertRaises(InvalidTransitionError):
            order.cancel("Teslim sonrası iptal")

    def test_duplicate_payment_rejected_after_received(self) -> None:
        order = self._new_order()
        gateway = KolayPayAdapter(KolayPayClient())
        CheckoutService(gateway).checkout(order, StandardDelivery())
        with self.assertRaises(InvalidTransitionError):
            order.record_payment(PaymentRecord("KP-99999", "KolayPay", order.price))


class TestAsama4ObserverIyilestirmeleri(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()
        self.customer = Customer(id="C-40", name="Elif Kaya", phone="05332004050")

    def _new_order(self):
        return (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog["pizza"])
            .deliver_to("Bağdat Cad. No:88", 3.0)
            .build()
        )

    def test_attach_rejects_non_observer_and_detach_is_safe(self) -> None:
        order = self._new_order()
        with self.assertRaises(TypeError):
            order.attach("not_an_observer")  # type: ignore[arg-type]

        audit = AuditLogObserver()
        # Ekli olmayan dinleyiciyi detach etmek hata vermemelidir
        order.detach(audit)
        order.attach(audit)
        order.detach(audit)
        order.detach(audit)

    def test_self_detaching_observer_does_not_break_notification_loop(self) -> None:
        calls: list[str] = []

        class OneShotObserver(OrderObserver):
            def update(self, event: OrderEvent) -> None:
                calls.append("oneshot")
                event.order.detach(self)

        class PersistentObserver(OrderObserver):
            def update(self, event: OrderEvent) -> None:
                calls.append("persistent")

        order = self._new_order()
        order.attach(OneShotObserver())
        order.attach(PersistentObserver())

        CheckoutService(KolayPayAdapter(KolayPayClient())).checkout(order, StandardDelivery())
        order.accept()
        self.assertEqual(calls, ["oneshot", "persistent", "persistent"])

    def test_courier_dispatcher_auto_assigns_waiting_order_when_courier_frees(self) -> None:
        logs: list[str] = []
        dispatcher = CourierDispatcher(["Kurye-1"], output=logs.append)
        gateway = KolayPayAdapter(KolayPayClient())
        checkout = CheckoutService(gateway)

        order1 = self._new_order()
        order2 = self._new_order()
        order1.attach(dispatcher)
        order2.attach(dispatcher)

        checkout.checkout(order1, StandardDelivery())
        checkout.checkout(order2, StandardDelivery())
        order1.accept()  # Kurye-1 -> order1
        order2.accept()  # Boşta kurye yok -> bekleme kuyruğu

        self.assertEqual(dispatcher.assignments[order1.id], "Kurye-1")
        self.assertNotIn(order2.id, dispatcher.assignments)
        self.assertEqual(len(dispatcher.waiting_queue), 1)

        order1.hand_over()
        order1.complete()  # Kurye-1 boşa çıkar -> otomatik olarak order2'ye atanır

        self.assertNotIn(order1.id, dispatcher.assignments)
        self.assertEqual(dispatcher.assignments[order2.id], "Kurye-1")
        self.assertEqual(len(dispatcher.waiting_queue), 0)

    def test_audit_log_observer_records_full_transition_history_with_timestamps(self) -> None:
        audit = AuditLogObserver()
        order = self._new_order()
        order.attach(audit)

        CheckoutService(KolayPayAdapter(KolayPayClient())).checkout(order, PickupDelivery())
        order.accept()
        order.hand_over()
        order.complete()

        history = audit.history_for(order.id)
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["from"], "ÖDEME BEKLİYOR")
        self.assertEqual(history[-1]["to"], "TESLİM EDİLDİ")
        self.assertIsNotNone(history[0]["timestamp"])

    def test_analytics_observer_tracks_counts_and_delivered_revenue(self) -> None:
        analytics = AnalyticsObserver()
        gateway = KolayPayAdapter(KolayPayClient())
        checkout = CheckoutService(gateway)

        o1 = self._new_order()
        o2 = self._new_order()
        o1.attach(analytics)
        o2.attach(analytics)

        b1 = checkout.checkout(o1, PickupDelivery())
        checkout.checkout(o2, PickupDelivery())
        o1.accept()
        o1.hand_over()
        o1.complete()
        o2.cancel("Geç kalındı")

        self.assertEqual(analytics.total_received, 2)
        self.assertEqual(analytics.total_delivered, 1)
        self.assertEqual(analytics.total_cancelled, 1)
        self.assertEqual(analytics.delivered_revenue, b1.total)
        self.assertEqual(analytics.cancellation_reasons, ["Geç kalındı"])

    def test_cancelled_waiting_order_is_removed_from_courier_queue(self) -> None:
        dispatcher = CourierDispatcher(["Kurye-1"], output=lambda _: None)
        checkout = CheckoutService(KolayPayAdapter(KolayPayClient()))
        o1 = self._new_order()
        o2 = self._new_order()
        o1.attach(dispatcher)
        o2.attach(dispatcher)

        checkout.checkout(o1, StandardDelivery())
        checkout.checkout(o2, StandardDelivery())
        o1.accept()
        o2.accept()  # Kuyruğa girdi
        o2.cancel("Vazgeçtim")  # Kuyruktan temizlenmeli

        self.assertEqual(len(dispatcher.waiting_queue), 0)


class TestEndToEndSixPatternsIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()
        self.customer = Customer(id="C-99", name="Deniz Arslan", phone="05359998877")

    def test_all_six_patterns_end_to_end_with_failover_and_observers(self) -> None:
        # 1. Decorator: GlutenFreeBase + ExtraCheese + LargePortion
        custom_pizza = LargePortion(ExtraCheese(GlutenFreeBase(self.catalog["pizza"])))
        # 2. Builder: Bireysel sipariş + kupon
        order = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(custom_pizza, quantity=1)
            .deliver_to("Caddebostan Sahil No:12", 5.0)
            .with_coupon("HOSGELDIN10")
            .build()
        )

        # 3. Adapter: KolayPay limiti düşük (100 TL), Failover otomatik GlobalCard'a geçer
        gateway = FailoverPaymentGateway(
            KolayPayAdapter(KolayPayClient(islem_limiti_kurus=10_000)),
            GlobalCardAdapter(GlobalCardSDK(max_amount=5000.0)),
        )

        # 4. Observer: 6 bağımsız dinleyiciyi ekle
        logs: list[str] = []
        panel = RestaurantPanel(output=logs.append)
        dispatcher = CourierDispatcher(["Ali"], output=logs.append)
        audit = AuditLogObserver()
        analytics = AnalyticsObserver()
        for obs in (
            CustomerNotifier(output=logs.append),
            panel,
            dispatcher,
            RefundHandler(gateway, output=logs.append),
            audit,
            analytics,
        ):
            order.attach(obs)

        # 5. Strategy + Checkout: ScheduledDelivery
        breakdown = CheckoutService(gateway).checkout(order, ScheduledDelivery(slot_minutes=60))
        self.assertTrue(order.transaction_id is not None and order.transaction_id.startswith("gc_"))
        self.assertIn(order.id, panel.active_orders)

        # 6. State: Yaşam döngüsü sonuna kadar ilerlet
        order.accept()
        order.hand_over()
        order.complete()

        self.assertIsInstance(order.state, DeliveredState)
        self.assertNotIn(order.id, panel.active_orders)
        self.assertEqual(dispatcher.available, ["Ali"])
        self.assertEqual(len(audit.history_for(order.id)), 4)
        self.assertEqual(analytics.delivered_revenue, breakdown.total)

    def test_mid_preparation_cancellation_triggers_50_percent_failover_refund(self) -> None:
        order = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog["pizza"], quantity=2)  # 480.00 TL
            .deliver_to("Suadiye No:4", 3.0)
            .build()
        )
        gateway = FailoverPaymentGateway(
            KolayPayAdapter(KolayPayClient(islem_limiti_kurus=10_000)),
            GlobalCardAdapter(GlobalCardSDK(max_amount=5000.0)),
        )
        refund_handler = RefundHandler(gateway, output=lambda _: None)
        dispatcher = CourierDispatcher(["Veli"], output=lambda _: None)
        order.attach(refund_handler)
        order.attach(dispatcher)

        breakdown = CheckoutService(gateway).checkout(order, StandardDelivery())
        order.accept()
        order.cancel("Müşteri iptal etti")

        self.assertIsInstance(order.state, CancelledState)
        self.assertEqual(refund_handler.refunded[order.id], Decimal("240.00"))
        self.assertEqual(breakdown.total, Decimal("480.00"))
        self.assertEqual(dispatcher.available, ["Veli"])

    def test_corporate_office_lunch_pickup_flow_requires_no_courier(self) -> None:
        director = OrderDirector(self.catalog)
        builder = (
            CorporateOrderBuilder()
            .for_customer(self.customer)
            .with_invoice("Teknoloji A.Ş.", "1234567890", tax_office="Maslak")
        )
        director.make_office_lunch(builder, headcount=4)
        order = builder.build()

        dispatcher = CourierDispatcher(["Kurye-A"], output=lambda _: None)
        order.attach(dispatcher)

        CheckoutService(KolayPayAdapter(KolayPayClient())).checkout(order, PickupDelivery())
        order.accept()
        self.assertEqual(dispatcher.assignments, {})
        order.hand_over()
        self.assertIsInstance(order.state, ReadyForPickupState)
        order.complete()
        self.assertIsInstance(order.state, DeliveredState)


if __name__ == "__main__":
    unittest.main()
