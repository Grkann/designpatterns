# Strategy (Davranışsal)
# Strategy: DeliveryStrategy
# ConcreteStrategy: StandardDelivery, ExpressDelivery, PickupDelivery,
#                   ScheduledDelivery, BadWeatherExpressDelivery
# Context: PriceCalculator
#
# Teslimat ücreti, tahmini süre ve "bu yöntem bu siparişe uygun mu?" kuralı her
# yöntemin kendi sınıfındadır. PriceCalculator hangi yöntemle çalıştığını bilmez;
# yeni bir teslimat türü eklemek PriceCalculator'ı ve CheckoutService'i değiştirmez.

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from .money import to_money


class DeliveryUnavailableError(ValueError):
    """Seçilen teslimat yöntemi bu sipariş için kullanılamadığında fırlatılır."""


def _validate_distance(distance_km: float) -> None:
    if distance_km < 0:
        raise ValueError("Teslimat mesafesi negatif olamaz.")


def _km(distance_km: float) -> Decimal:
    return Decimal(str(distance_km))


# ----------------------------------------------------------------- Strategy
class DeliveryStrategy(ABC):
    name = ""
    requires_courier = True

    @abstractmethod
    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        pass

    @abstractmethod
    def estimated_minutes(self, distance_km: float) -> int:
        pass

    def unavailable_reason(self, order) -> str | None:
        """Yöntem bu sipariş için kullanılamıyorsa nedenini, kullanılabiliyorsa None döndürür."""
        if self.requires_courier and not order.address:
            return f"'{self.name}' için teslimat adresi gerekli."
        return None


# --------------------------------------------------------- ConcreteStrategy
class StandardDelivery(DeliveryStrategy):
    name = "Standart teslimat"
    FREE_THRESHOLD = Decimal("400.00")
    BASE_FEE = Decimal("20")
    PER_KM = Decimal("5")
    INCLUDED_KM = 2

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        if subtotal >= self.FREE_THRESHOLD:
            return Decimal("0.00")
        extra_km = max(0, distance_km - self.INCLUDED_KM)
        return to_money(self.BASE_FEE + self.PER_KM * _km(extra_km))

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 25 + math.ceil(distance_km * 4)


class ExpressDelivery(DeliveryStrategy):
    name = "Ekspres teslimat"
    BASE_FEE = Decimal("45")
    PER_KM = Decimal("8")
    MAX_DISTANCE_KM = 8

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        return to_money(self.BASE_FEE + self.PER_KM * _km(distance_km))

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 12 + math.ceil(distance_km * 2)

    def unavailable_reason(self, order) -> str | None:
        reason = super().unavailable_reason(order)
        if reason is None and order.distance_km > self.MAX_DISTANCE_KM:
            reason = f"'{self.name}' en fazla {self.MAX_DISTANCE_KM} km mesafeye yapılır."
        return reason


class PickupDelivery(DeliveryStrategy):
    name = "Gel-al"
    requires_courier = False

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        return Decimal("0.00")

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return 15


class ScheduledDelivery(DeliveryStrategy):
    """İleri saatli planlı teslimat: 350 TL üzeri ücretsiz, km ücreti düşük, süre seçilen dilim kadar."""

    name = "Planlı teslimat"
    FREE_THRESHOLD = Decimal("350.00")
    BASE_FEE = Decimal("15")
    PER_KM = Decimal("4")
    INCLUDED_KM = 3

    def __init__(self, slot_minutes: int = 60) -> None:
        if slot_minutes < 30:
            raise ValueError("Planlı teslimat süresi en az 30 dakika olmalıdır.")
        self.slot_minutes = slot_minutes

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        _validate_distance(distance_km)
        if subtotal >= self.FREE_THRESHOLD:
            return Decimal("0.00")
        extra_km = max(0, distance_km - self.INCLUDED_KM)
        return to_money(self.BASE_FEE + self.PER_KM * _km(extra_km))

    def estimated_minutes(self, distance_km: float) -> int:
        _validate_distance(distance_km)
        return self.slot_minutes


class BadWeatherExpressDelivery(ExpressDelivery):
    """Yağışlı / yoğun havada ekspres: ekspres ücretini çarpanla büyütür, süreye 10 dk ekler."""

    name = "Yağışlı hava ekspres"
    EXTRA_MINUTES = 10

    def __init__(self, surge_multiplier: Decimal | str | float = Decimal("1.25")) -> None:
        multiplier = Decimal(str(surge_multiplier))
        if multiplier < Decimal("1.00"):
            raise ValueError("Yoğunluk çarpanı 1.00'dan küçük olamaz.")
        self.surge_multiplier = multiplier

    def fee(self, subtotal: Decimal, distance_km: float) -> Decimal:
        return to_money(super().fee(subtotal, distance_km) * self.surge_multiplier)

    def estimated_minutes(self, distance_km: float) -> int:
        return super().estimated_minutes(distance_km) + self.EXTRA_MINUTES


# ------------------------------------------------------------------ Context
@dataclass(frozen=True)
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
        self.set_strategy(strategy)

    @staticmethod
    def _validate_strategy(strategy: DeliveryStrategy) -> None:
        if not isinstance(strategy, DeliveryStrategy):
            raise TypeError("Strateji DeliveryStrategy alt sınıfı olmalıdır.")

    def set_strategy(self, strategy: DeliveryStrategy) -> None:
        self._validate_strategy(strategy)
        self.strategy = strategy

    def calculate(self, order) -> PriceBreakdown:
        return self._quote(order, self.strategy)

    def compare(self, order, strategies: list[DeliveryStrategy]) -> list[PriceBreakdown]:
        """Bu siparişe uygun teslimat seçeneklerini toplam tutara göre sıralar; aktif strateji değişmez."""
        for strategy in strategies:
            self._validate_strategy(strategy)
        usable = [s for s in strategies if s.unavailable_reason(order) is None]
        return sorted((self._quote(order, s) for s in usable), key=lambda b: b.total)

    @staticmethod
    def _quote(order, strategy: DeliveryStrategy) -> PriceBreakdown:
        reason = strategy.unavailable_reason(order)
        if reason is not None:
            raise DeliveryUnavailableError(reason)
        subtotal = order.subtotal()
        discount = to_money(subtotal * order.coupon_rate)
        net = subtotal - discount
        fee = strategy.fee(net, order.distance_km)
        return PriceBreakdown(
            method_name=strategy.name,
            subtotal=subtotal,
            discount=discount,
            delivery_fee=fee,
            total=to_money(net + fee),
            estimated_minutes=strategy.estimated_minutes(order.distance_km),
            requires_courier=strategy.requires_courier,
        )
