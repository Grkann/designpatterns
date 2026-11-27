"""Arayüzün arkasındaki uygulama katmanı.

Bu modül yeni bir tasarım kalıbı eklemez; tarayıcıdan gelen istekleri projedeki
kalıplara (Builder, Decorator, Strategy, Adapter, State, Observer) yönlendirir ve
sonuçları JSON'a çevrilebilir sözlüklere dönüştürür. HTTP katmanından bağımsızdır,
bu yüzden testlerde doğrudan çağrılabilir.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from siparis.builder import COUPONS, CorporateOrderBuilder, IndividualOrderBuilder, OrderBuilder, OrderDirector
from siparis.checkout import CheckoutService
from siparis.delivery import (
    BadWeatherExpressDelivery,
    DeliveryStrategy,
    DeliveryUnavailableError,
    ExpressDelivery,
    PickupDelivery,
    PriceCalculator,
    ScheduledDelivery,
    StandardDelivery,
)
from siparis.external.globalcard import GlobalCardSDK
from siparis.external.kolaypay import KolayPayClient
from siparis.menu import EXTRAS, ItemExtra, MenuItem, apply_extras, default_catalog
from siparis.money import to_money
from siparis.notifications import OrderEvent, OrderObserver
from siparis.observers import (
    AnalyticsObserver,
    AuditLogObserver,
    CourierDispatcher,
    CustomerNotifier,
    RefundHandler,
    RestaurantPanel,
)
from siparis.order import Customer, Order
from siparis.payment import FailoverPaymentGateway, GlobalCardAdapter, KolayPayAdapter, PaymentGateway

GLOBALCARD_DEMO_LIMIT = 500.0  # Demo için düşük tutuldu: büyük siparişte yedekli ödemenin devreye girdiği görülsün.


class DemoError(Exception):
    """Arayüze kullanıcı hatası olarak gösterilecek durum."""


def money(value: Decimal) -> str:
    return f"{value:.2f}"


# --------------------------------------------------- Adaptee çağrılarını izlemek
# Adapter'ın yaptığı çeviriyi ekranda göstermek için dış servis sınıflarının
# aynı arayüzle çalışan, yaptığı çağrıları kaydeden alt sınıfları.
class RecordingKolayPayClient(KolayPayClient):
    def __init__(self, record) -> None:
        super().__init__()
        self._record = record

    def odeme_al(self, tutar_kurus, musteri_no):
        resp = super().odeme_al(tutar_kurus, musteri_no)
        self._record("KolayPayClient", f"odeme_al(tutar_kurus={tutar_kurus}, musteri_no={musteri_no!r})", resp)
        return resp

    def iade_et(self, islem_no, tutar_kurus):
        resp = super().iade_et(islem_no, tutar_kurus)
        self._record("KolayPayClient", f"iade_et(islem_no={islem_no!r}, tutar_kurus={tutar_kurus})", resp)
        return resp


class RecordingGlobalCardSDK(GlobalCardSDK):
    def __init__(self, record) -> None:
        super().__init__(max_amount=GLOBALCARD_DEMO_LIMIT)
        self._record = record

    def create_charge(self, amount, currency, metadata):
        resp = super().create_charge(amount, currency, metadata)
        self._record("GlobalCardSDK", f"create_charge(amount={amount}, currency={currency!r}, metadata={metadata})", resp)
        return resp

    def reverse(self, charge_id, amount):
        resp = super().reverse(charge_id, amount)
        self._record("GlobalCardSDK", f"reverse(charge_id={charge_id!r}, amount={amount})", resp)
        return resp


# ------------------------------------------------- Arayüzün kendi dinleyicisi
class LiveFeedObserver(OrderObserver):
    """Durum geçişlerini canlı akışa yazar. Order'a dokunmadan eklenen bir ConcreteObserver daha."""

    def __init__(self, log) -> None:
        self.log = log

    def update(self, event: OrderEvent) -> None:
        self.log("Order", f"#{event.order.id}: {event.old_state.name} → {event.new_state.name}", event.order.id)


# --------------------------------------------------------------- Seçenekler
PRESETS = {
    "ogrenci": ("Öğrenci menüsü", "make_student_menu"),
    "pizza": ("Pizza gecesi", "make_pizza_night"),
    "ofis": ("Ofis öğle yemeği", "make_office_lunch"),
    "aile": ("Aile ziyafeti", "make_family_feast"),
}

STRATEGY_KEYS = ["standart", "ekspres", "gelal", "planli", "yagisli"]

GATEWAYS = {
    "kolaypay": "KolayPay",
    "globalcard": "GlobalCard",
    "yedekli": "Yedekli (GlobalCard → KolayPay)",
}

ACTIONS = {
    "accept": "Restoran onayladı",
    "hand_over": "Teslimata çıktı",
    "complete": "Teslim edildi",
    "cancel": "İptal et",
}


def make_strategy(key: str, slot_minutes: int = 60, surge: str = "1.25") -> DeliveryStrategy:
    if key == "standart":
        return StandardDelivery()
    if key == "ekspres":
        return ExpressDelivery()
    if key == "gelal":
        return PickupDelivery()
    if key == "planli":
        return ScheduledDelivery(slot_minutes=int(slot_minutes))
    if key == "yagisli":
        return BadWeatherExpressDelivery(surge_multiplier=str(surge))
    raise DemoError(f"Bilinmeyen teslimat yöntemi: {key}")


def item_code(item: MenuItem) -> str:
    if isinstance(item, ItemExtra):
        return f"{type(item).__name__}({item_code(item.item)})"
    return f'Dish("{item.description()}")'


def item_layers(item: MenuItem) -> list[dict]:
    """İçten dışa doğru her katmanın sınıfı, eklediği tutar ve o katmandaki fiyat."""
    layers = []
    current = item
    while isinstance(current, ItemExtra):
        layers.append(
            {
                "cls": type(current).__name__,
                "label": current.label,
                "extra": money(current.extra_cost()),
                "price": money(current.price()),
            }
        )
        current = current.item
    layers.append({"cls": "Dish", "label": current.description(), "extra": None, "price": money(current.price())})
    return list(reversed(layers))


def item_dict(item: MenuItem) -> dict:
    return {
        "description": item.description(),
        "price": money(item.price()),
        "category": item.category().value,
        "code": item_code(item),
        "layers": item_layers(item),
    }


class DemoApp:
    def __init__(self) -> None:
        OrderBuilder.next_id = 1001  # "Sıfırla" sonrası sipariş numaraları yeniden #1001'den başlasın
        self.catalog = default_catalog()
        self.director = OrderDirector(self.catalog)
        self.cart: list[MenuItem] = []
        self.orders: dict[int, Order] = {}
        self.meta: dict[int, dict] = {}
        self.events: list[dict] = []
        self.adaptee_calls: list[dict] = []

        self.panel = RestaurantPanel(output=self._out("RestaurantPanel"))
        self.couriers = CourierDispatcher(["Ahmet", "Zeynep"], output=self._out("CourierDispatcher"))
        self.audit = AuditLogObserver()
        self.analytics = AnalyticsObserver()
        self.feed = LiveFeedObserver(self._log)

        kolaypay = KolayPayAdapter(RecordingKolayPayClient(self._record_adaptee))
        globalcard = GlobalCardAdapter(RecordingGlobalCardSDK(self._record_adaptee))
        self.gateways: dict[str, PaymentGateway] = {
            "kolaypay": kolaypay,
            "globalcard": globalcard,
            "yedekli": FailoverPaymentGateway(globalcard, kolaypay),
        }

    # ------------------------------------------------------------ kayıtlar
    def _log(self, source: str, text: str, order_id: int | None = None) -> None:
        self.events.append(
            {
                "n": len(self.events) + 1,
                "time": datetime.now().strftime("%H:%M:%S"),
                "source": source,
                "text": text,
                "order_id": order_id,
            }
        )

    def _out(self, source: str):
        return lambda text: self._log(source, text)

    def _record_adaptee(self, adaptee: str, call: str, response) -> None:
        self.adaptee_calls.append({"adaptee": adaptee, "call": call, "response": repr(response)})

    # ------------------------------------------------------------- katalog
    def catalog_info(self) -> dict:
        return {
            "products": [
                {"key": k, "name": d.name, "price": money(d.price()), "category": d.category().value}
                for k, d in self.catalog.items()
            ],
            "extras": [
                {
                    "key": k,
                    "cls": cls.__name__,
                    "label": cls.label,
                    "categories": sorted(c.value for c in cls.allowed_categories),
                    "stackable": cls.stackable,
                }
                for k, cls in EXTRAS.items()
            ],
            "presets": [{"key": k, "name": name, "method": m} for k, (name, m) in PRESETS.items()],
            "coupons": {k: f"%{int(v * 100)}" for k, v in COUPONS.items()},
            "gateways": GATEWAYS,
            "actions": ACTIONS,
            "globalcard_limit": money(Decimal(str(GLOBALCARD_DEMO_LIMIT))),
        }

    # ------------------------------------------------------ Decorator: sepet
    def _product(self, key: str) -> MenuItem:
        if key not in self.catalog:
            raise DemoError(f"Katalogda '{key}' yok.")
        return self.catalog[key]

    def preview(self, product: str, extras: list[str]) -> dict:
        return item_dict(apply_extras(self._product(product), list(extras)))

    def cart_add(self, product: str, extras: list[str], qty: int = 1) -> None:
        qty = int(qty)
        if qty < 1 or qty > 50:
            raise DemoError("Adet 1 ile 50 arasında olmalı.")
        item = apply_extras(self._product(product), list(extras))
        self.cart.extend([item] * qty)

    def cart_remove(self, index: int) -> None:
        if not 0 <= index < len(self.cart):
            raise DemoError("Sepette böyle bir satır yok.")
        del self.cart[index]

    def cart_clear(self) -> None:
        self.cart = []

    def cart_preset(self, key: str, headcount: int = 4) -> None:
        """Director hazır menüyü bir builder'a kurar; kurulan ürünler sepete aktarılır."""
        if key not in PRESETS:
            raise DemoError(f"Bilinmeyen hazır menü: {key}")
        scratch = IndividualOrderBuilder()
        method = getattr(self.director, PRESETS[key][1])
        if key == "ofis":
            method(scratch, headcount=int(headcount))
        else:
            method(scratch)
        self.cart.extend(scratch.items)

    def cart_info(self) -> dict:
        groups: list[dict] = []
        for index, item in enumerate(self.cart):
            if groups and groups[-1]["item"] is item:
                groups[-1]["qty"] += 1
                groups[-1]["indexes"].append(index)
            else:
                groups.append({"item": item, "qty": 1, "indexes": [index]})
        subtotal = sum((i.price() for i in self.cart), Decimal("0"))
        return {
            "lines": [
                {**item_dict(g["item"]), "qty": g["qty"], "index": g["indexes"][-1],
                 "line_total": money(g["item"].price() * g["qty"])}
                for g in groups
            ],
            "count": len(self.cart),
            "subtotal": money(subtotal),
        }

    # ----------------------------------------------------- Builder: sipariş
    def build_order(self, data: dict) -> int:
        corporate = data.get("type") == "kurumsal"
        builder: OrderBuilder = CorporateOrderBuilder() if corporate else IndividualOrderBuilder()
        builder.for_customer(Customer(f"C-{OrderBuilder.next_id}", data.get("name", ""), data.get("phone", "")))
        for item in self.cart:
            builder.add_item(item)
        if not data.get("pickup_only"):
            builder.deliver_to(data.get("address", ""), float(data.get("distance") or 0))
        if data.get("coupon"):
            builder.with_coupon(data["coupon"])
        if data.get("note"):
            builder.with_note(data["note"])
        if corporate:
            builder.with_invoice(data.get("company", ""), data.get("tax_number", ""))
        order = builder.build()

        self.orders[order.id] = order
        self.meta[order.id] = {"type": "Kurumsal" if corporate else "Bireysel", "refund": None, "payments": []}
        for observer in (
            self.feed,
            CustomerNotifier(output=self._out("CustomerNotifier")),
            self.panel,
            self.couriers,
            self.audit,
            self.analytics,
        ):
            order.attach(observer)
        self.cart = []
        self._log("OrderBuilder", f"{type(builder).__name__}.build() → Sipariş #{order.id} oluşturuldu", order.id)
        return order.id

    def _order(self, order_id: int) -> Order:
        if order_id not in self.orders:
            raise DemoError(f"#{order_id} numaralı sipariş yok.")
        return self.orders[order_id]

    # --------------------------------------------------- Strategy: teslimat
    def quotes(self, order_id: int, slot_minutes: int = 60, surge: str = "1.25") -> dict:
        order = self._order(order_id)
        strategies = [make_strategy(k, slot_minutes, surge) for k in STRATEGY_KEYS]
        calculator = PriceCalculator(strategies[0])
        options = []
        for key, strategy in zip(STRATEGY_KEYS, strategies):
            calculator.set_strategy(strategy)
            option = {"key": key, "cls": type(strategy).__name__, "name": strategy.name}
            try:
                q = calculator.calculate(order)
            except DeliveryUnavailableError as e:
                option.update({"available": False, "reason": str(e)})
            else:
                option.update(
                    {
                        "available": True,
                        "fee": money(q.delivery_fee),
                        "total": money(q.total),
                        "minutes": q.estimated_minutes,
                        "courier": q.requires_courier,
                    }
                )
            options.append(option)
        ranked = calculator.compare(order, strategies)
        subtotal = order.subtotal()
        discount = to_money(subtotal * order.coupon_rate)
        return {
            "options": options,
            "cheapest": ranked[0].method_name if ranked else None,
            "fastest": min(ranked, key=lambda b: b.estimated_minutes).method_name if ranked else None,
            "subtotal": money(subtotal),
            "discount": money(discount),
        }

    # ---------------------------------------------------- Adapter: ödeme
    def checkout(self, order_id: int, strategy_key: str, gateway_key: str,
                 slot_minutes: int = 60, surge: str = "1.25") -> dict:
        order = self._order(order_id)
        if gateway_key not in self.gateways:
            raise DemoError(f"Bilinmeyen ödeme sağlayıcısı: {gateway_key}")
        gateway = self.gateways[gateway_key]
        strategy = make_strategy(strategy_key, slot_minutes, surge)

        meta = self.meta[order_id]
        start = len(self.adaptee_calls)
        trace = {"gateway": gateway_key, "gateway_cls": type(gateway).__name__, "strategy": strategy.name}
        try:
            breakdown = CheckoutService(gateway).checkout(order, strategy)
        except Exception as e:
            trace.update({"success": False, "error": str(e), "calls": self.adaptee_calls[start:]})
            meta["payments"].append(trace)
            if not self.adaptee_calls[start:]:
                raise
            return trace
        # İptalde parayı, ödemenin alındığı sağlayıcı üzerinden geri veren dinleyici.
        meta["refund"] = RefundHandler(gateway, output=self._out("RefundHandler"))
        order.attach(meta["refund"])
        trace.update(
            {
                "success": True,
                "amount": money(breakdown.total),
                "transaction_id": order.transaction_id,
                "provider": order.payment_provider,
                "calls": self.adaptee_calls[start:],
            }
        )
        meta["payments"].append(trace)
        return trace

    # -------------------------------------------------------- State: takip
    def action(self, order_id: int, action: str, reason: str = "") -> None:
        order = self._order(order_id)
        if action not in ACTIONS:
            raise DemoError(f"Bilinmeyen işlem: {action}")
        if action == "cancel":
            order.cancel(reason or "Müşteri vazgeçti")
        else:
            getattr(order, action)()

    # --------------------------------------------------------- görünüm
    def order_info(self, order: Order) -> dict:
        meta = self.meta[order.id]
        price = order.price
        refund = meta["refund"].refunded.get(order.id) if meta["refund"] else None
        return {
            "id": order.id,
            "type": meta["type"],
            "customer": order.customer.name,
            "phone": order.customer.phone,
            "address": order.address,
            "distance": order.distance_km,
            "items": order.item_descriptions(),
            "subtotal": money(order.subtotal()),
            "coupon": order.coupon_code,
            "invoice": order.invoice.company_name if order.invoice else None,
            "state": order.state.name,
            "state_cls": type(order.state).__name__,
            "is_final": order.state.is_final,
            "allowed": [a for a in order.state.allowed_actions() if a in ACTIONS],
            "paid": price is not None,
            "method": price.method_name if price else None,
            "total": money(price.total) if price else None,
            "minutes": price.estimated_minutes if price else None,
            "courier_needed": order.requires_courier,
            "courier": self.couriers.assignments.get(order.id),
            "provider": order.payment_provider,
            "transaction_id": order.transaction_id,
            "refund": money(refund) if refund is not None else None,
            "cancel_reason": getattr(order.state, "reason", None),
            "refund_if_cancel": (
                f"%{int(order.state.cancellation_refund_ratio * 100)}" if order.state.can_cancel and order.price else None
            ),
            "history": [
                {"from": h["from"], "to": h["to"], "time": h["timestamp"].astimezone().strftime("%H:%M:%S")}
                for h in self.audit.history_for(order.id)
            ],
        }

    def snapshot(self) -> dict:
        a = self.analytics
        return {
            "cart": self.cart_info(),
            "orders": [self.order_info(o) for o in self.orders.values()],
            "events": self.events,
            "panel": sorted(self.panel.active_orders),
            "couriers": {
                "available": list(self.couriers.available),
                "assignments": {str(k): v for k, v in self.couriers.assignments.items()},
                "queue": [o.id for o in self.couriers.waiting_queue],
            },
            "analytics": {
                "received": a.total_received,
                "delivered": a.total_delivered,
                "cancelled": a.total_cancelled,
                "revenue": money(a.delivered_revenue),
            },
        }
