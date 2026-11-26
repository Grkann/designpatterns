"""Grkann/designpatterns 2. Aşama (Decorator & Strategy) ek testleri ve regresyon doğrulamaları."""

from __future__ import annotations

from decimal import Decimal
import unittest

from siparis.builder import IndividualOrderBuilder
from siparis.delivery import (
    BadWeatherExpressDelivery,
    ExpressDelivery,
    PickupDelivery,
    PriceCalculator,
    ScheduledDelivery,
    StandardDelivery,
)
from siparis.menu import (
    Dish,
    DoubleMeat,
    DrinkUpgrade,
    ExtraCheese,
    ExtraDip,
    ExtraSauce,
    GlutenFreeBase,
    LargePortion,
    default_catalog,
)
from siparis.order import Customer


class TestAsama2DecoratorIyilestirmeleri(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()

    def test_dish_rejects_empty_name_and_negative_price(self) -> None:
        with self.assertRaises(ValueError):
            Dish("   ", "50.00")
        with self.assertRaises(ValueError):
            Dish("Çorba", "-10.00")

    def test_item_extra_rejects_non_menu_item(self) -> None:
        with self.assertRaises(TypeError):
            ExtraCheese("sadece metin")  # type: ignore[arg-type]

    def test_new_decorators_compose_and_track_extras_chain(self) -> None:
        pizza = self.catalog["pizza"]  # 240.00 TL
        decorated = ExtraDip(GlutenFreeBase(ExtraCheese(pizza)))

        # 240 + 25 + 30 + 12.50 = 307.50 TL
        self.assertEqual(decorated.price(), Decimal("307.50"))
        self.assertEqual(
            decorated.extras_chain(),
            ["ekstra peynir", "glütensiz taban", "özel dip sos"],
        )
        self.assertIn("glütensiz taban", decorated.description())

    def test_drink_upgrade_decorator(self) -> None:
        upgraded = DrinkUpgrade(self.catalog["kola"])  # 45 + 15 = 60.00 TL
        self.assertEqual(upgraded.price(), Decimal("60.00"))
        self.assertEqual(upgraded.extras_chain(), ["büyük içecek"])

    def test_wrapping_order_with_large_portion_changes_total(self) -> None:
        burger = self.catalog["burger"]  # 180.00 TL
        # Önce DoubleMeat (+60 = 240), sonra LargePortion (+%30 = +72 -> 312.00)
        meat_then_large = LargePortion(DoubleMeat(burger))
        # Önce LargePortion (180 * 1.30 = 234), sonra DoubleMeat (+60 -> 294.00)
        large_then_meat = DoubleMeat(LargePortion(burger))

        self.assertEqual(meat_then_large.price(), Decimal("312.00"))
        self.assertEqual(large_then_meat.price(), Decimal("294.00"))
        self.assertNotEqual(meat_then_large.price(), large_then_meat.price())

    def test_plain_dish_has_empty_extras_chain(self) -> None:
        self.assertEqual(self.catalog["ayran"].extras_chain(), [])


class TestAsama2StrategyIyilestirmeleri(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()
        self.customer = Customer(id="C-10", name="Kerem Aydın", phone="05320001122")

    def _make_order(self, item_key: str, qty: int, distance_km: float, coupon: str | None = None):
        builder = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog[item_key], quantity=qty)
            .deliver_to("Bağdat Cad. No:50", distance_km)
        )
        if coupon:
            builder.with_coupon(coupon)
        return builder.build()

    def test_negative_distance_and_invalid_strategy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            StandardDelivery().fee(Decimal("100.00"), -1.0)
        with self.assertRaises(TypeError):
            PriceCalculator("not_a_strategy")  # type: ignore[arg-type]

    def test_scheduled_delivery_fee_threshold_and_slot_validation(self) -> None:
        with self.assertRaises(ValueError):
            ScheduledDelivery(slot_minutes=20)

        strategy = ScheduledDelivery(slot_minutes=90)
        # 350 TL altı ve 5 km -> 15 + (5 - 3) * 4 = 23.00 TL
        self.assertEqual(strategy.fee(Decimal("200.00"), 5.0), Decimal("23.00"))
        # 350 TL ve üzeri -> ücretsiz
        self.assertEqual(strategy.fee(Decimal("350.00"), 8.0), Decimal("0.00"))
        self.assertEqual(strategy.estimated_minutes(8.0), 90)

    def test_bad_weather_express_delivery_surge_and_validation(self) -> None:
        with self.assertRaises(ValueError):
            BadWeatherExpressDelivery(surge_multiplier="0.90")

        strategy = BadWeatherExpressDelivery(surge_multiplier="1.25")
        # Taban ekspres (5 km): 45 + 8 * 5 = 85.00; * 1.25 = 106.25 TL
        self.assertEqual(strategy.fee(Decimal("200.00"), 5.0), Decimal("106.25"))
        # Süre: 22 + ceil(5 * 2) = 32 dk
        self.assertEqual(strategy.estimated_minutes(5.0), 32)

    def test_price_calculator_compare_sorts_by_total_and_preserves_active_strategy(self) -> None:
        order = self._make_order("burger", qty=1, distance_km=5.0)  # 180.00 TL
        initial = ExpressDelivery()
        calc = PriceCalculator(initial)

        ranked = calc.compare(
            order,
            [
                BadWeatherExpressDelivery(),
                ExpressDelivery(),
                StandardDelivery(),
                ScheduledDelivery(),
                PickupDelivery(),
            ],
        )

        self.assertIs(calc.strategy, initial)
        self.assertEqual(ranked[0].method_name, "Gel-al")
        self.assertEqual(ranked[-1].method_name, "Yağışlı hava ekspres")
        totals = [item.total for item in ranked]
        self.assertEqual(totals, sorted(totals))

    def test_coupon_applied_before_free_delivery_threshold(self) -> None:
        # 2x Pizza = 480.00 TL; OGRENCI15 (%15) -> 72.00 TL indirim -> net 408.00 TL (>= 400 ücretsiz)
        order_free = self._make_order("pizza", qty=2, distance_km=4.0, coupon="OGRENCI15")
        bd_free = PriceCalculator(StandardDelivery()).calculate(order_free)
        self.assertEqual(bd_free.delivery_fee, Decimal("0.00"))
        self.assertEqual(bd_free.total, Decimal("408.00"))

        # 2x Burger + Patates = 420.00 TL; OGRENCI15 (%15) -> 63.00 indirim -> net 357.00 TL (< 400 ücretli)
        order_paid = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(self.catalog["burger"], quantity=2)
            .add_item(self.catalog["patates"], quantity=1)
            .deliver_to("Moda Cad. No:12", 4.0)
            .with_coupon("OGRENCI15")
            .build()
        )
        bd_paid = PriceCalculator(StandardDelivery()).calculate(order_paid)
        # 4 km -> 20 + (4 - 2) * 5 = 30.00 TL
        self.assertEqual(bd_paid.delivery_fee, Decimal("30.00"))
        self.assertEqual(bd_paid.total, Decimal("387.00"))

    def test_extra_sauce_and_runtime_strategy_swap(self) -> None:
        order = (
            IndividualOrderBuilder()
            .for_customer(self.customer)
            .add_item(ExtraSauce(self.catalog["burger"]))  # 190.00 TL
            .deliver_to("Kadıköy Rıhtım", 3.0)
            .build()
        )
        calc = PriceCalculator(StandardDelivery())
        std = calc.calculate(order)
        calc.set_strategy(PickupDelivery())
        pickup = calc.calculate(order)

        self.assertGreater(std.total, pickup.total)
        self.assertTrue(std.requires_courier)
        self.assertFalse(pickup.requires_courier)


if __name__ == "__main__":
    unittest.main()
