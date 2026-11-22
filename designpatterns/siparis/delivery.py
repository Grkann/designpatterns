# Strategy
# Strategy: DeliveryStrategy
# ConcreteStrategy: StandardDelivery, ExpressDelivery, PickupDelivery
# Context: PriceCalculator

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from .money import to_money


class DeliveryStrategy(ABC):
    name = ""
    requires_courier = True

    @abstractmethod
    def fee(self, subtotal, distance_km):
        pass

    @abstractmethod
    def estimated_minutes(self, distance_km):
        pass


class StandardDelivery(DeliveryStrategy):
    name = "Standart teslimat"

    def fee(self, subtotal, distance_km):
        if subtotal >= Decimal("400"):
            return Decimal("0.00")
        extra_km = max(0, distance_km - 2)
        return to_money(Decimal("20") + Decimal("5") * Decimal(str(extra_km)))

    def estimated_minutes(self, distance_km):
        return 25 + math.ceil(distance_km * 4)


class ExpressDelivery(DeliveryStrategy):
    name = "Ekspres teslimat"

    def fee(self, subtotal, distance_km):
        return to_money(Decimal("45") + Decimal("8") * Decimal(str(distance_km)))

    def estimated_minutes(self, distance_km):
        return 12 + math.ceil(distance_km * 2)


class PickupDelivery(DeliveryStrategy):
    name = "Gel-al"
    requires_courier = False

    def fee(self, subtotal, distance_km):
        return Decimal("0.00")

    def estimated_minutes(self, distance_km):
        return 15


@dataclass
class PriceBreakdown:
    method_name: str
    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    total: Decimal
    estimated_minutes: int
    requires_courier: bool


class PriceCalculator:
    def __init__(self, strategy):
        self.strategy = strategy

    def set_strategy(self, strategy):
        self.strategy = strategy

    def calculate(self, order):
        subtotal = order.subtotal()
        discount = to_money(subtotal * order.coupon_rate)
        net = subtotal - discount
        fee = self.strategy.fee(net, order.distance_km)
        return PriceBreakdown(
            method_name=self.strategy.name,
            subtotal=subtotal,
            discount=discount,
            delivery_fee=fee,
            total=to_money(net + fee),
            estimated_minutes=self.strategy.estimated_minutes(order.distance_km),
            requires_courier=self.strategy.requires_courier,
        )
