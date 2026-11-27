"""Strategy & Decorator düzeltmeleri: açıklama biçimi, kategori/tekrar kuralları,
teslimat uygunluğu, compare'in durumsuz çalışması ve BadWeather'ın Express'i yeniden kullanması."""

from decimal import Decimal

import pytest

from siparis.builder import IndividualOrderBuilder
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
from siparis.external.kolaypay import KolayPayClient
from siparis.menu import (
    Category,
    DoubleMeat,
    DrinkUpgrade,
    ExtraCheese,
    ExtraNotApplicableError,
    ItemExtra,
    LargePortion,
    apply_extras,
)
from siparis.payment import KolayPayAdapter


def _order(menu, customer, distance_km=3.0, address="Test Sok. 1"):
    b = IndividualOrderBuilder().for_customer(customer).add_item(menu["burger"])
    if address:
        b.deliver_to(address, distance_km)
    return b.build()


# ------------------------------------------------------------------ Decorator
def test_description_lists_extras_in_wrapping_order(menu):
    item = LargePortion(ExtraCheese(menu["pizza"]))
    assert item.description() == "Margarita Pizza + ekstra peynir + büyük boy"


def test_food_extra_cannot_wrap_a_drink(menu):
    with pytest.raises(ExtraNotApplicableError, match="içecek"):
        DoubleMeat(menu["kola"])


def test_drink_upgrade_cannot_wrap_food(menu):
    with pytest.raises(ExtraNotApplicableError):
        DrinkUpgrade(menu["burger"])


def test_non_stackable_extra_only_once_but_stackable_repeats(menu):
    with pytest.raises(ExtraNotApplicableError, match="bir kez"):
        LargePortion(ExtraCheese(LargePortion(menu["pizza"])))
    double_cheese = ExtraCheese(ExtraCheese(menu["pizza"]))
    assert double_cheese.price() == Decimal("290.00")


def test_decorated_item_keeps_category_of_wrapped_item(menu):
    assert DrinkUpgrade(menu["kola"]).category() is Category.DRINK
    assert ExtraCheese(menu["burger"]).category() is Category.FOOD


def test_apply_extras_wraps_in_given_order(menu):
    item = apply_extras(menu["burger"], ["duble_et", "buyuk_boy"])
    assert isinstance(item, LargePortion) and isinstance(item.item, DoubleMeat)
    assert item.price() == Decimal("312.00")
    with pytest.raises(ExtraNotApplicableError, match="Bilinmeyen"):
        apply_extras(menu["burger"], ["altin_varak"])


def test_new_extra_needs_no_change_elsewhere(menu):
    class Truffle(ItemExtra):
        label = "trüf"

        def extra_cost(self):
            return Decimal("99.00")

    assert Truffle(menu["pizza"]).price() == Decimal("339.00")


# ------------------------------------------------------------------- Strategy
def test_express_not_available_beyond_max_distance(menu, customer):
    far = _order(menu, customer, distance_km=12.0)
    assert ExpressDelivery().unavailable_reason(far) is not None
    assert BadWeatherExpressDelivery().unavailable_reason(far) is not None  # Express'ten miras
    with pytest.raises(DeliveryUnavailableError, match="km"):
        PriceCalculator(ExpressDelivery()).calculate(far)


def test_compare_skips_unavailable_and_keeps_active_strategy(menu, customer):
    far = _order(menu, customer, distance_km=12.0)
    active = StandardDelivery()
    calc = PriceCalculator(active)
    names = [q.method_name for q in calc.compare(far, [ExpressDelivery(), StandardDelivery(), PickupDelivery()])]
    assert names == ["Gel-al", "Standart teslimat"]
    assert calc.strategy is active


def test_order_without_address_only_gets_pickup(menu, customer):
    no_address = _order(menu, customer, address=None)
    quotes = CheckoutService(KolayPayAdapter(KolayPayClient())).quote_options(
        no_address, [StandardDelivery(), ScheduledDelivery(), PickupDelivery()]
    )
    assert [q.method_name for q in quotes] == ["Gel-al"]


def test_bad_weather_reuses_express_pricing(menu, customer):
    express, storm = ExpressDelivery(), BadWeatherExpressDelivery("1.50")
    assert storm.fee(Decimal("0"), 4.0) == express.fee(Decimal("0"), 4.0) * Decimal("1.50")
    assert storm.estimated_minutes(4.0) == express.estimated_minutes(4.0) + 10


def test_new_strategy_works_without_touching_calculator(menu, customer):
    class DroneDelivery(DeliveryStrategy):
        name = "Drone"

        def fee(self, subtotal, distance_km):
            return Decimal("99.00")

        def estimated_minutes(self, distance_km):
            return 8

    q = PriceCalculator(DroneDelivery()).calculate(_order(menu, customer))
    assert (q.method_name, q.delivery_fee, q.estimated_minutes) == ("Drone", Decimal("99.00"), 8)


def test_quote_options_requires_at_least_one_strategy(menu, customer):
    with pytest.raises(ValueError):
        CheckoutService(KolayPayAdapter(KolayPayClient())).quote_options(_order(menu, customer), [])
