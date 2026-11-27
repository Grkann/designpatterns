# Decorator (Yapısal)
# Component: MenuItem
# ConcreteComponent: Dish
# Decorator: ItemExtra
# ConcreteDecorator: ExtraCheese, ExtraSauce, DoubleMeat, LargePortion,
#                    GlutenFreeBase, DrinkUpgrade, ExtraDip
#
# Her ekstra bir MenuItem'ı sarar ve kendisi de bir MenuItem'dır; bu yüzden
# ekstralar istenen sırada ve sayıda üst üste eklenebilir. Yeni ekstra eklemek
# Dish'e ya da diğer ekstralara dokunmadan yeni bir ItemExtra alt sınıfı yazmaktır.

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum

from .money import to_money


class Category(Enum):
    FOOD = "yemek"
    DRINK = "içecek"


class ExtraNotApplicableError(ValueError):
    """Ekstra, sarılmak istenen ürüne uygulanamadığında fırlatılır."""


# ---------------------------------------------------------------- Component
class MenuItem(ABC):
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def price(self) -> Decimal:
        pass

    @abstractmethod
    def category(self) -> Category:
        pass

    def extras_chain(self) -> list[str]:
        """Ürüne eklenen ekstraları uygulanma sırasıyla listeler."""
        return []

    def has_extra(self, extra_type: type[ItemExtra]) -> bool:
        """Zincirde verilen türde bir ekstra var mı?"""
        return False


# -------------------------------------------------------- ConcreteComponent
class Dish(MenuItem):
    def __init__(
        self,
        name: str,
        price: Decimal | int | float | str,
        category: Category = Category.FOOD,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("Ürün adı boş olamaz.")
        normalized_price = to_money(price)
        if normalized_price < Decimal("0.00"):
            raise ValueError("Ürün fiyatı negatif olamaz.")
        self.name = name.strip()
        self._price = normalized_price
        self._category = category

    def description(self) -> str:
        return self.name

    def price(self) -> Decimal:
        return self._price

    def category(self) -> Category:
        return self._category


# ---------------------------------------------------------------- Decorator
class ItemExtra(MenuItem):
    label = ""
    # Ekstranın eklenebileceği ürün kategorileri (ör. içeceğe "duble et" eklenemez).
    allowed_categories: frozenset[Category] = frozenset({Category.FOOD})
    # False ise aynı ekstra bir ürüne yalnızca bir kez eklenebilir.
    stackable = True

    def __init__(self, item: MenuItem) -> None:
        if not isinstance(item, MenuItem):
            raise TypeError("ItemExtra yalnızca bir MenuItem nesnesini sarabilir.")
        if item.category() not in self.allowed_categories:
            raise ExtraNotApplicableError(
                f"'{self.label}' ekstrası {item.category().value} ürününe eklenemez ({item.description()})."
            )
        if not self.stackable and item.has_extra(type(self)):
            raise ExtraNotApplicableError(f"'{self.label}' aynı ürüne yalnızca bir kez eklenebilir.")
        self.item = item

    @abstractmethod
    def extra_cost(self) -> Decimal:
        pass

    def description(self) -> str:
        return f"{self.item.description()} + {self.label}"

    def price(self) -> Decimal:
        return to_money(self.item.price() + self.extra_cost())

    def category(self) -> Category:
        return self.item.category()

    def extras_chain(self) -> list[str]:
        return self.item.extras_chain() + [self.label]

    def has_extra(self, extra_type: type[ItemExtra]) -> bool:
        return isinstance(self, extra_type) or self.item.has_extra(extra_type)


# -------------------------------------------------------- ConcreteDecorator
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
    stackable = False

    def extra_cost(self) -> Decimal:
        return Decimal("60.00")


class LargePortion(ItemExtra):
    """Fiyatın %30'u kadar ekler; o ana kadarki ekstraları da büyüttüğü için sarma sırası sonucu değiştirir."""

    label = "büyük boy"
    stackable = False
    RATE = Decimal("0.30")

    def extra_cost(self) -> Decimal:
        return to_money(self.item.price() * self.RATE)


class GlutenFreeBase(ItemExtra):
    label = "glütensiz taban"
    stackable = False

    def extra_cost(self) -> Decimal:
        return Decimal("30.00")


class DrinkUpgrade(ItemExtra):
    label = "büyük içecek"
    allowed_categories = frozenset({Category.DRINK})
    stackable = False

    def extra_cost(self) -> Decimal:
        return Decimal("15.00")


class ExtraDip(ItemExtra):
    label = "özel dip sos"

    def extra_cost(self) -> Decimal:
        return Decimal("12.50")


# Arayüzün ve testlerin ekstraları adıyla seçebilmesi için kayıt tablosu.
EXTRAS: dict[str, type[ItemExtra]] = {
    "peynir": ExtraCheese,
    "aci_sos": ExtraSauce,
    "duble_et": DoubleMeat,
    "buyuk_boy": LargePortion,
    "glutensiz": GlutenFreeBase,
    "buyuk_icecek": DrinkUpgrade,
    "dip_sos": ExtraDip,
}


def apply_extras(item: MenuItem, extra_keys: list[str]) -> MenuItem:
    """Ekstraları verilen sırayla üst üste sarar: ["peynir", "buyuk_boy"] -> LargePortion(ExtraCheese(item))."""
    for key in extra_keys:
        if key not in EXTRAS:
            raise ExtraNotApplicableError(f"Bilinmeyen ekstra: {key}")
        item = EXTRAS[key](item)
    return item


def default_catalog() -> dict[str, Dish]:
    return {
        "burger": Dish("Klasik Burger", "180.00"),
        "pizza": Dish("Margarita Pizza", "240.00"),
        "lahmacun": Dish("Lahmacun", "90.00"),
        "salata": Dish("Mevsim Salata", "110.00"),
        "patates": Dish("Patates Kızartması", "60.00"),
        "ayran": Dish("Ayran", "30.00", Category.DRINK),
        "kola": Dish("Kola", "45.00", Category.DRINK),
    }
