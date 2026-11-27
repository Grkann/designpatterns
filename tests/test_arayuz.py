"""Arayüz katmanı: DemoApp akışları ve HTTP sunucusunun JSON uç noktaları."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from arayuz.app import DemoApp
from arayuz.server import DemoServer
from siparis.order_state import InvalidTransitionError


INDIVIDUAL = {"name": "Ayşe", "phone": "0555", "address": "Kampüs", "distance": "4.5", "coupon": "OGRENCI15"}
CORPORATE = {"type": "kurumsal", "name": "Mehmet", "phone": "0532", "address": "Teknopark", "distance": "1.5",
             "company": "Kaya A.Ş.", "tax_number": "1234567890"}


def test_preview_shows_decorator_layers_inside_out():
    p = DemoApp().preview("pizza", ["peynir", "buyuk_boy"])
    assert p["code"] == 'LargePortion(ExtraCheese(Dish("Margarita Pizza")))'
    assert [layer["cls"] for layer in p["layers"]] == ["Dish", "ExtraCheese", "LargePortion"]
    assert p["price"] == "344.50"


def test_director_preset_fills_cart_and_build_clears_it():
    app = DemoApp()
    app.cart_preset("ofis", headcount=2)
    assert app.cart_info()["count"] == 7
    order_id = app.build_order(CORPORATE)
    assert app.cart == [] and app.orders[order_id].invoice.company_name == "Kaya A.Ş."


def test_quotes_mark_unavailable_strategies():
    app = DemoApp()
    app.cart_add("burger", [])
    order_id = app.build_order({"name": "Can", "phone": "0544", "pickup_only": True})
    options = {o["key"]: o["available"] for o in app.quotes(order_id)["options"]}
    assert options == {"standart": False, "ekspres": False, "gelal": True, "planli": False, "yagisli": False}


def test_failover_payment_then_cancel_refunds_half_and_notifies_observers():
    app = DemoApp()
    app.cart_preset("ofis", headcount=6)  # 1480 TL > GlobalCard demo limiti
    order_id = app.build_order(CORPORATE)

    declined = app.checkout(order_id, "standart", "globalcard")
    assert declined["success"] is False and "402" in declined["calls"][0]["response"]

    paid = app.checkout(order_id, "standart", "yedekli")
    assert paid["success"] is True
    assert [c["adaptee"] for c in paid["calls"]] == ["GlobalCardSDK", "KolayPayClient"]

    app.action(order_id, "accept")
    app.action(order_id, "cancel", "Toplantı iptal")
    info = app.order_info(app.orders[order_id])
    assert info["state"] == "İPTAL EDİLDİ" and info["refund"] == "740.00"
    sources = {e["source"] for e in app.events}
    assert {"Order", "CustomerNotifier", "RestaurantPanel", "CourierDispatcher", "RefundHandler"} <= sources


def test_paid_order_cannot_be_charged_twice():
    app = DemoApp()
    app.cart_add("burger", [])
    order_id = app.build_order(INDIVIDUAL)
    app.checkout(order_id, "ekspres", "kolaypay")
    calls_before = len(app.adaptee_calls)
    with pytest.raises(InvalidTransitionError):
        app.checkout(order_id, "ekspres", "kolaypay")
    assert len(app.adaptee_calls) == calls_before  # sağlayıcıya ikinci istek gitmedi


@pytest.fixture
def server():
    srv = DemoServer(("127.0.0.1", 0))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _post(base, path, body):
    req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_http_api_serves_page_and_reports_user_errors(server):
    with urllib.request.urlopen(server + "/") as r:
        assert "Tasarım Kalıpları" in r.read().decode("utf-8")
    status, body = _post(server, "/api/preview", {"product": "kola", "extras": ["duble_et"]})
    assert status == 400 and body["kind"] == "ExtraNotApplicableError"
    status, body = _post(server, "/api/cart/add", {"product": "burger", "extras": ["duble_et"], "qty": 2})
    assert status == 200 and body["state"]["cart"]["count"] == 2
