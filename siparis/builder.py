# Builder (Yaratımsal) — 1. Aşama İyileştirilmiş Sürüm
# Builder: OrderBuilder
# ConcreteBuilder: IndividualOrderBuilder, CorporateOrderBuilder
# Director: OrderDirector
# Product: Order

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from decimal import Decimal

from .menu import ExtraCheese, LargePortion
from .order import Customer, InvoiceInfo, Order

COUPONS: dict[str, Decimal] = {
    "OGRENCI15": Decimal("0.15"),
    "HOSGELDIN10": Decimal("0.10"),
}
MAX_DISTANCE_KM = 15
MAX_NOTE_LENGTH = 200


class OrderBuildError(ValueError):
    """Sipariş kurulumu veya doğrulama kuralları ihlal edildiğinde fırlatılır."""


class OrderBuilder(ABC):
    next_id = 1001

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.customer: Customer | None = None
        self.items: list = []
        self.address: str | None = None
        self.distance_km: float = 0.0
        self.note: str = ""
        self.coupon_code: str | None = None
        self.coupon_rate: Decimal = Decimal("0")

    def for_customer(self, customer: Customer) -> OrderBuilder:
        if customer is None:
            raise OrderBuildError("Müşteri nesnesi boş olamaz.")
        if not customer.name or not customer.name.strip():
            raise OrderBuildError("Müşteri adı boş olamaz.")
        if not customer.phone or not customer.phone.strip():
            raise OrderBuildError("Müşteri telefon numarası boş olamaz.")
        self.customer = customer
        return self

    def add_item(self, item, quantity: int = 1) -> OrderBuilder:
        if quantity < 1:
            raise OrderBuildError("Adet en az 1 olmalı.")
        for _ in range(quantity):
            self.items.append(item)
        return self

    def clear_items(self) -> OrderBuilder:
        """Sepetteki ürünleri temizler (akıcı arayüzle yeniden seçim için)."""
        self.items = []
        return self

    def deliver_to(self, address: str, distance_km: float) -> OrderBuilder:
        if not address or address.strip() == "":
            raise OrderBuildError("Adres boş olamaz.")
        if distance_km <= 0 or distance_km > MAX_DISTANCE_KM:
            raise OrderBuildError(f"Adres hizmet alanı dışında (en fazla {MAX_DISTANCE_KM} km).")
        self.address = address.strip()
        self.distance_km = distance_km
        return self

    def with_note(self, note: str) -> OrderBuilder:
        if len(note) > MAX_NOTE_LENGTH:
            raise OrderBuildError(f"Not en fazla {MAX_NOTE_LENGTH} karakter olabilir.")
        self.note = note.strip()
        return self

    @abstractmethod
    def with_coupon(self, code: str) -> OrderBuilder:
        pass

    @abstractmethod
    def validate(self) -> None:
        pass

    @abstractmethod
    def get_invoice(self) -> InvoiceInfo | None:
        pass

    def build(self) -> Order:
        if self.customer is None:
            raise OrderBuildError("Müşteri belirtilmedi.")
        if len(self.items) == 0:
            raise OrderBuildError("Sipariş en az bir ürün içermeli.")
        self.validate()

        order = Order(
            order_id=OrderBuilder.next_id,
            customer=self.customer,
            items=self.items,
            address=self.address,
            distance_km=self.distance_km,
            note=self.note,
            coupon_code=self.coupon_code,
            coupon_rate=self.coupon_rate,
            invoice=self.get_invoice(),
        )
        OrderBuilder.next_id += 1
        self.reset()
        return order


class IndividualOrderBuilder(OrderBuilder):
    def with_coupon(self, code: str) -> IndividualOrderBuilder:
        normalized = code.strip().upper()
        if normalized not in COUPONS:
            raise OrderBuildError(f"Geçersiz kupon: {normalized}")
        self.coupon_code = normalized
        self.coupon_rate = COUPONS[normalized]
        return self

    def validate(self) -> None:
        pass

    def get_invoice(self) -> InvoiceInfo | None:
        return None


class CorporateOrderBuilder(OrderBuilder):
    MIN_ITEMS = 3

    def reset(self) -> None:
        super().reset()
        self.invoice: InvoiceInfo | None = None

    def with_invoice(
        self,
        company_name: str,
        tax_number: str,
        tax_office: str = "",
    ) -> CorporateOrderBuilder:
        cleaned_company = company_name.strip()
        cleaned_tax = tax_number.strip()
        if not cleaned_company:
            raise OrderBuildError("Şirket ünvanı boş olamaz.")
        if len(cleaned_tax) != 10 or not cleaned_tax.isdigit():
            raise OrderBuildError("Vergi numarası 10 haneli olmalı.")
        self.invoice = InvoiceInfo(cleaned_company, cleaned_tax, tax_office.strip())
        return self

    def with_coupon(self, code: str) -> CorporateOrderBuilder:
        raise OrderBuildError("Kurumsal siparişlerde kupon kullanılamaz.")

    def validate(self) -> None:
        if self.invoice is None:
            raise OrderBuildError("Kurumsal sipariş için fatura bilgisi zorunlu.")
        if len(self.items) < self.MIN_ITEMS:
            raise OrderBuildError(f"Kurumsal sipariş en az {self.MIN_ITEMS} ürün içermeli.")

    def get_invoice(self) -> InvoiceInfo | None:
        return self.invoice


class OrderDirector:
    def __init__(self, catalog: dict) -> None:
        self.catalog = catalog

    def _require(self, key: str):
        if key not in self.catalog:
            raise OrderBuildError(f"Katalogda '{key}' ürünü bulunamadı.")
        return self.catalog[key]

    def make_student_menu(self, builder: OrderBuilder) -> None:
        builder.add_item(self._require("burger"))
        builder.add_item(self._require("patates"))
        builder.add_item(self._require("ayran"))

    def make_pizza_night(self, builder: OrderBuilder) -> None:
        builder.add_item(LargePortion(ExtraCheese(self._require("pizza"))), quantity=2)
        builder.add_item(self._require("kola"), quantity=2)

    def make_office_lunch(self, builder: OrderBuilder, headcount: int) -> None:
        if headcount < 1:
            raise OrderBuildError("Kişi sayısı en az 1 olmalı.")
        builder.add_item(self._require("lahmacun"), quantity=2 * headcount)
        builder.add_item(self._require("ayran"), quantity=headcount)
        builder.add_item(self._require("salata"), quantity=math.ceil(headcount / 4))

    def make_family_feast(self, builder: OrderBuilder) -> None:
        """Yeni reçete: 4 kişilik aile menüsü (2 büyük peynirli pizza, 2 burger, 2 patates, 4 ayran)."""
        builder.add_item(LargePortion(ExtraCheese(self._require("pizza"))), quantity=2)
        builder.add_item(self._require("burger"), quantity=2)
        builder.add_item(self._require("patates"), quantity=2)
        builder.add_item(self._require("ayran"), quantity=4)
