# Decorator (Yapısal) — 2. Aşama İyileştirilmiş Sürüm
# Component: MenuItem, ConcreteComponent: Dish
# Decorator: ItemExtra
# ConcreteDecorator: ExtraCheese, ExtraSauce, DoubleMeat, LargePortion,
#                    GlutenFreeBase, DrinkUpgrade, ExtraDip

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .money import to_money


class MenuItem(ABC):
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def price(self) -> Decimal:
        pass

    def extras_chain(self) -> list[str]:
        """Ürüne eklenen ekstraları uygulanma sırasıyla listeler."""
        return []


class Dish(MenuItem):
    def __init__(self, name: str, price: Decimal | int | float | str) -> None:
        if not name or not name.strip():
            raise ValueError("Ürün adı boş olamaz.")
        normalized_price = to_money(price)
        if normalized_price < Decimal("0.00"):
            raise ValueError("Ürün fiyatı negatif olamaz.")
        self.name = name.strip()
        self._price = normalized_price

    def description(self) -> str:
        return self.name

    def price(self) -> Decimal:
        return self._price


class ItemExtra(MenuItem):
    label = ""

    def __init__(self, item: MenuItem) -> None:
        if not isinstance(item, MenuItem):
            raise TypeError("ItemExtra yalnızca bir MenuItem nesnesini sarabilir.")
        self.item = item

    @abstractmethod
    def extra_cost(self) -> Decimal:
        pass

    def description(self) -> str:
        return self.item.description() + " " + self.label

    def price(self) -> Decimal:
        return to_money(self.item.price() + self.extra_cost())

    def extras_chain(self) -> list[str]:
        return self.item.extras_chain() + [self.label]


class ExtraCheese(ItemExtra):
    label = "ekstra peynir"

    def extra_cost(self) -> Decimal:
        return Decimal("25.00")


class ExtraSauce(ItemExtra):
    label = "acı sos"

    def extra_cost(self) -> Decimal:
        return Decimal("10.00")


class DoubleMeat(ItemExtra):
    label = "duble et"

    def extra_cost(self) -> Decimal:
        return Decimal("60.00")


class LargePortion(ItemExtra):
    label = "büyük boy"

    # fiyatın %30'u eklendiği için sarma sırası sonucu değiştirir
    def extra_cost(self) -> Decimal:
        return to_money(self.item.price() * Decimal("0.30"))


class GlutenFreeBase(ItemExtra):
    """Yeni dekoratör: Glütensiz hamur / ekmek seçeneği."""

    label = "glütensiz taban"

    def extra_cost(self) -> Decimal:
        return Decimal("30.00")


class DrinkUpgrade(ItemExtra):
    """Yeni dekoratör: İçecek boyutu büyütme seçeneği."""

    label = "büyük içecek"

    def extra_cost(self) -> Decimal:
        return Decimal("15.00")


class ExtraDip(ItemExtra):
    """Yeni dekoratör: Özel dip sos eklentisi."""

    label = "özel dip sos"

    def extra_cost(self) -> Decimal:
        return Decimal("12.50")


def default_catalog() -> dict[str, Dish]:
    return {
        "burger": Dish("Klasik Burger", "180.00"),
        "pizza": Dish("Margarita Pizza", "240.00"),
        "lahmacun": Dish("Lahmacun", "90.00"),
        "salata": Dish("Mevsim Salata", "110.00"),
        "patates": Dish("Patates Kızartması", "60.00"),
        "ayran": Dish("Ayran", "30.00"),
        "kola": Dish("Kola", "45.00"),
    }
