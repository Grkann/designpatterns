# Decorator
# Component: MenuItem, ConcreteComponent: Dish
# Decorator: ItemExtra, ConcreteDecorator: ExtraCheese, ExtraSauce, DoubleMeat, LargePortion

from abc import ABC, abstractmethod
from decimal import Decimal

from .money import to_money


class MenuItem(ABC):
    @abstractmethod
    def description(self):
        pass

    @abstractmethod
    def price(self):
        pass


class Dish(MenuItem):
    def __init__(self, name, price):
        self.name = name
        self._price = to_money(price)

    def description(self):
        return self.name

    def price(self):
        return self._price


class ItemExtra(MenuItem):
    label = ""

    def __init__(self, item):
        self.item = item

    @abstractmethod
    def extra_cost(self):
        pass

    def description(self):
        return self.item.description() + " + " + self.label

    def price(self):
        return self.item.price() + self.extra_cost()


class ExtraCheese(ItemExtra):
    label = "ekstra peynir"

    def extra_cost(self):
        return Decimal("25.00")


class ExtraSauce(ItemExtra):
    label = "acı sos"

    def extra_cost(self):
        return Decimal("10.00")


class DoubleMeat(ItemExtra):
    label = "duble et"

    def extra_cost(self):
        return Decimal("60.00")


class LargePortion(ItemExtra):
    label = "büyük boy"

    # fiyatın %30'u eklendiği için sarma sırası sonucu değiştirir
    def extra_cost(self):
        return to_money(self.item.price() * Decimal("0.30"))


def default_catalog():
    return {
        "burger": Dish("Klasik Burger", "180.00"),
        "pizza": Dish("Margarita Pizza", "240.00"),
        "lahmacun": Dish("Lahmacun", "90.00"),
        "salata": Dish("Mevsim Salata", "110.00"),
        "patates": Dish("Patates Kızartması", "60.00"),
        "ayran": Dish("Ayran", "30.00"),
        "kola": Dish("Kola", "45.00"),
    }
