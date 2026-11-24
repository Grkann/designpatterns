# Strategy (Davranışsal) — 2. Aşama İyileştirilmiş Sürüm
# Strategy: DeliveryStrategy
# ConcreteStrategy: StandardDelivery, ExpressDelivery, PickupDelivery,
#                   ScheduledDelivery, BadWeatherExpressDelivery
# Context: PriceCalculator

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from .money import to_money


def _validate_distance(distance_km: float) -> None:
    if distance_km < 0:
        raise ValueError("Teslimat mesafesi negatif olamaz.")


class DeliveryStrategy(ABC):
    name = ""
    requires_courier = True

    @abstractmethod
    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        pass

    @abstractmethod
    def estimated_minutes(self, distance_km: float) -> int:
        pass


class StandardDelivery(DeliveryStrategy):
    name = "Standart teslimat"

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        if subtotal >= Decimal("400"):
            return Decimal("0.00")
        extra_km = max(0, distance_km - 2)
        return to_money(Decimal("20") + Decimal("5") * Decimal(str(extra_km)))

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 25 + math.ceil(distance_km * 4)


class ExpressDelivery(DeliveryStrategy):
    name = "Ekspres teslimat"

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        _ = subtotal
        return to_money(Decimal("45") + Decimal("8") * Decimal(str(distance_km)))

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 12 + math.ceil(distance_km * 2)


class PickupDelivery(DeliveryStrategy):
    name = "Gel-al"
    requires_courier = False

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        _ = subtotal
        return Decimal("0.00")

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 15


class ScheduledDelivery(DeliveryStrategy):
    """Yeni strateji: İleri saatli planlı teslimat (350 TL üzeri ücretsiz, düşük km ücreti)."""

    name = "Planlı teslimat"
    FREE_THRESHOLD = Decimal("350.00")

    def __init__(self, slot_minutes: int = 60) -> None:
        if slot_minutes < 30:
            raise ValueError("Planlı teslimat süresi en az 30 dakika olmalıdır.")
        self.slot_minutes = slot_minutes

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        if subtotal >= self.FREE_THRESHOLD:
            return Decimal("0.00")
        extra_km = max(0, distance_km - 3)
        return to_money(Decimal("15") + Decimal("4") * Decimal(str(extra_km)))

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return self.slot_minutes


class BadWeatherExpressDelivery(DeliveryStrategy):
    """Yeni strateji: Yağışlı / yoğun hava koşullarında çarpanlı ekspres teslimat."""

    name = "Yağışlı hava ekspres"

    def __init__(self, surge_multiplier: Decimal | str | float = Decimal("1.25")) -> None:
        multiplier = Decimal(str(surge_multiplier))
        if multiplier < Decimal("1.00"):
            raise ValueError("Yoğunluk çarpanı 1.00'dan küçük olamaz.")
        self.surge_multiplier = multiplier

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        _ = subtotal
        base = Decimal("45") + Decimal("8") * Decimal(str(distance_km))
        return to_money(base * self.surge_multiplier)

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 22 + math.ceil(distance_km * 2)


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
    def __init__(self, strategy: DeliveryStrategy) -> None:
        self._validate_strategy(strategy)
        self.strategy = strategy

    @staticmethod
    def _validate_strategy(strategy: DeliveryStrategy) -> None:
        if not isinstance(strategy, DeliveryStrategy):
            raise TypeError("Strateji DeliveryStrategy alt sınıfı olmalıdır.")

    def set_strategy(self, strategy: DeliveryStrategy) -> None:
        self._validate_strategy(strategy)
        self.strategy = strategy

    def calculate(self, order) -> PriceBreakdown:
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

    def compare(self, order, strategies: list[DeliveryStrategy]) -> list[PriceBreakdown]:
        """Aktif stratejiyi değiştirmeden verilen teslimat seçeneklerini toplam tutara göre sıralar."""
        original = self.strategy
        results: list[PriceBreakdown] = []
        try:
            for strategy in strategies:
                self.set_strategy(strategy)
                results.append(self.calculate(order))
        finally:
            self.strategy = original
        return sorted(results, key=lambda b: b.total)
