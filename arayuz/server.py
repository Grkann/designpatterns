"""Yalnızca standart kütüphaneyle çalışan küçük HTTP sunucusu: statik sayfa + JSON API."""

from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from siparis.order_state import InvalidTransitionError

from .app import DemoApp, DemoError

STATIC_DIR = Path(__file__).parent / "static"
USER_ERRORS = (DemoError, ValueError, TypeError, InvalidTransitionError)


class DemoServer(HTTPServer):
    def __init__(self, address) -> None:
        super().__init__(address, Handler)
        self.app = DemoApp()


class Handler(BaseHTTPRequestHandler):
    server: DemoServer

    def log_message(self, format, *args) -> None:  # konsolu sessiz tut
        pass

    # ------------------------------------------------------------ yardımcılar
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:
        app = self.server.app
        if self.path == "/api/catalog":
            return self._json(200, app.catalog_info())
        if self.path == "/api/state":
            return self._json(200, app.snapshot())

        name = "index.html" if self.path in ("/", "") else self.path.lstrip("/").split("?")[0]
        file = (STATIC_DIR / name).resolve()
        if STATIC_DIR.resolve() not in file.parents or not file.is_file():
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, file.read_bytes(), ctype)

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:
        try:
            data = self._body()
            result = self._route(self.path, data)
        except USER_ERRORS as e:
            return self._json(400, {"error": str(e), "kind": type(e).__name__})
        except Exception as e:  # beklenmeyen hata: sayfada görünür olsun
            return self._json(500, {"error": f"Sunucu hatası: {e}", "kind": type(e).__name__})
        self._json(200, {"result": result, "state": self.server.app.snapshot()})

    def _route(self, path: str, d: dict):
        app = self.server.app
        if path == "/api/reset":
            self.server.app = DemoApp()
            return None
        if path == "/api/preview":
            return app.preview(d["product"], d.get("extras", []))
        if path == "/api/cart/add":
            return app.cart_add(d["product"], d.get("extras", []), d.get("qty", 1))
        if path == "/api/cart/remove":
            return app.cart_remove(int(d["index"]))
        if path == "/api/cart/clear":
            return app.cart_clear()
        if path == "/api/cart/preset":
            return app.cart_preset(d["key"], d.get("headcount", 4))
        if path == "/api/orders":
            return app.build_order(d)

        m = re.fullmatch(r"/api/orders/(\d+)/(quotes|checkout|action)", path)
        if m:
            order_id, what = int(m.group(1)), m.group(2)
            slot, surge = d.get("slot", 60), d.get("surge", "1.25")
            if what == "quotes":
                return app.quotes(order_id, slot, surge)
            if what == "checkout":
                return app.checkout(order_id, d["strategy"], d["gateway"], slot, surge)
            return app.action(order_id, d["action"], d.get("reason", ""))
        raise DemoError(f"Bilinmeyen adres: {path}")
