from decimal import Decimal

import pytest

from siparis.builder import CorporateOrderBuilder, IndividualOrderBuilder, OrderBuildError, OrderDirector
from siparis.menu import DoubleMeat, ExtraCheese, ExtraSauce, ItemExtra, LargePortion


def test_extras_add_price_and_description(menu):
    item = ExtraSauce(DoubleMeat(menu["burger"]))
    assert item.price() == Decimal("250.00")
    assert item.description() == "Klasik Burger + duble et + acı sos"


def test_wrapping_order_matters(menu):
    a = LargePortion(ExtraCheese(menu["pizza"]))
    b = ExtraCheese(LargePortion(menu["pizza"]))
    assert a.price() == Decimal("344.50")
    assert b.price() == Decimal("337.00")


def test_item_extra_is_abstract(menu):
    with pytest.raises(TypeError):
        ItemExtra(menu["burger"])


def test_individual_order(menu, customer):
    order = (IndividualOrderBuilder()
             .for_customer(customer)
             .add_item(menu["kola"], 3)
             .with_coupon("ogrenci15")
             .build())
    assert len(order.items) == 3
    assert order.coupon_rate == Decimal("0.15")
    assert order.invoice is None


def test_missing_customer(menu):
    builder = IndividualOrderBuilder().add_item(menu["kola"])
    with pytest.raises(OrderBuildError, match="Müşteri"):
        builder.build()


def test_empty_order(customer):
    builder = IndividualOrderBuilder().for_customer(customer)
    with pytest.raises(OrderBuildError, match="en az bir ürün"):
        builder.build()


def test_invalid_coupon(customer):
    with pytest.raises(OrderBuildError, match="Geçersiz kupon"):
        IndividualOrderBuilder().for_customer(customer).with_coupon("YOK")


def test_address_too_far(customer):
    with pytest.raises(OrderBuildError, match="hizmet alanı"):
        IndividualOrderBuilder().for_customer(customer).deliver_to("Uzak", 40)


def test_builder_resets_after_build(menu, customer):
    builder = IndividualOrderBuilder().for_customer(customer).add_item(menu["kola"])
    builder.build()
    with pytest.raises(OrderBuildError):
        builder.build()


def test_corporate_rules(menu, customer):
    b = CorporateOrderBuilder().for_customer(customer)
    with pytest.raises(OrderBuildError, match="kupon"):
        b.with_coupon("OGRENCI15")
    with pytest.raises(OrderBuildError, match="10 haneli"):
        b.with_invoice("X A.Ş.", "123")

    b.add_item(menu["kola"], 3)
    with pytest.raises(OrderBuildError, match="fatura"):
        b.build()

    b = CorporateOrderBuilder().for_customer(customer).with_invoice("X A.Ş.", "1234567890")
    b.add_item(menu["kola"], 2)
    with pytest.raises(OrderBuildError, match="en az 3"):
        b.build()


def test_director_with_both_builders(menu, customer):
    director = OrderDirector(menu)

    ind = IndividualOrderBuilder().for_customer(customer)
    director.make_student_menu(ind)
    assert ind.build().subtotal() == Decimal("270.00")

    corp = CorporateOrderBuilder().for_customer(customer).with_invoice("X A.Ş.", "1234567890")
    director.make_office_lunch(corp, headcount=5)
    order = corp.build()
    assert len(order.items) == 17
    assert order.subtotal() == Decimal("1270.00")
