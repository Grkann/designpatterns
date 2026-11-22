# Builder
# Builder: OrderBuilder
# ConcreteBuilder: IndividualOrderBuilder, CorporateOrderBuilder
# Director: OrderDirector
# Product: Order

import math
from abc import ABC, abstractmethod
from decimal import Decimal

from .menu import ExtraCheese, LargePortion
from .order import InvoiceInfo, Order

COUPONS = {
    "OGRENCI15": Decimal("0.15"),
    "HOSGELDIN10": Decimal("0.10"),
}
MAX_DISTANCE_KM = 15


class OrderBuildError(ValueError):
    pass


class OrderBuilder(ABC):
    next_id = 1001

    def __init__(self):
        self.reset()

    def reset(self):
        self.customer = None
        self.items = []
        self.address = None
        self.distance_km = 0.0
        self.note = ""
        self.coupon_code = None
        self.coupon_rate = Decimal("0")

    def for_customer(self, customer):
        self.customer = customer
        return self

    def add_item(self, item, quantity=1):
        if quantity < 1:
            raise OrderBuildError("Adet en az 1 olmalı.")
        for _ in range(quantity):
            self.items.append(item)
        return self

    def deliver_to(self, address, distance_km):
        if address.strip() == "":
            raise OrderBuildError("Adres boş olamaz.")
        if distance_km <= 0 or distance_km > MAX_DISTANCE_KM:
            raise OrderBuildError(f"Adres hizmet alanı dışında (en fazla {MAX_DISTANCE_KM} km).")
        self.address = address
        self.distance_km = distance_km
        return self

    def with_note(self, note):
        if len(note) > 200:
            raise OrderBuildError("Not en fazla 200 karakter olabilir.")
        self.note = note
        return self

    @abstractmethod
    def with_coupon(self, code):
        pass

    @abstractmethod
    def validate(self):
        pass

    @abstractmethod
    def get_invoice(self):
        pass

    def build(self):
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
    def with_coupon(self, code):
        code = code.strip().upper()
        if code not in COUPONS:
            raise OrderBuildError(f"Geçersiz kupon: {code}")
        self.coupon_code = code
        self.coupon_rate = COUPONS[code]
        return self

    def validate(self):
        pass

    def get_invoice(self):
        return None


class CorporateOrderBuilder(OrderBuilder):
    MIN_ITEMS = 3

    def reset(self):
        super().reset()
        self.invoice = None

    def with_invoice(self, company_name, tax_number):
        if len(tax_number) != 10 or not tax_number.isdigit():
            raise OrderBuildError("Vergi numarası 10 haneli olmalı.")
        self.invoice = InvoiceInfo(company_name, tax_number)
        return self

    def with_coupon(self, code):
        raise OrderBuildError("Kurumsal siparişlerde kupon kullanılamaz.")

    def validate(self):
        if self.invoice is None:
            raise OrderBuildError("Kurumsal sipariş için fatura bilgisi zorunlu.")
        if len(self.items) < self.MIN_ITEMS:
            raise OrderBuildError(f"Kurumsal sipariş en az {self.MIN_ITEMS} ürün içermeli.")

    def get_invoice(self):
        return self.invoice


class OrderDirector:
    def __init__(self, catalog):
        self.catalog = catalog

    def make_student_menu(self, builder):
        builder.add_item(self.catalog["burger"])
        builder.add_item(self.catalog["patates"])
        builder.add_item(self.catalog["ayran"])

    def make_pizza_night(self, builder):
        builder.add_item(LargePortion(ExtraCheese(self.catalog["pizza"])), quantity=2)
        builder.add_item(self.catalog["kola"], quantity=2)

    def make_office_lunch(self, builder, headcount):
        if headcount < 1:
            raise OrderBuildError("Kişi sayısı en az 1 olmalı.")
        builder.add_item(self.catalog["lahmacun"], quantity=2 * headcount)
        builder.add_item(self.catalog["ayran"], quantity=headcount)
        builder.add_item(self.catalog["salata"], quantity=math.ceil(headcount / 4))
