# Observer (Davranışsal) — 4. Aşama İyileştirilmiş Sürüm
# Subject: OrderSubject, ConcreteSubject: Order
# Observer: OrderObserver, ConcreteObserver: observers.py içindeki sınıflar

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OrderEvent:
    order: object
    old_state: object
    new_state: object
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrderObserver(ABC):
    @abstractmethod
    def update(self, event: OrderEvent) -> None:
        pass


class OrderSubject(ABC):
    def __init__(self) -> None:
        self.observers: list[OrderObserver] = []

    def attach(self, observer: OrderObserver) -> None:
        if not isinstance(observer, OrderObserver):
            raise TypeError("Dinleyici OrderObserver alt sınıfı olmalıdır.")
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer: OrderObserver) -> None:
        if observer in self.observers:
            self.observers.remove(observer)

    def notify(self, event: OrderEvent) -> None:
        # Anlık kopya üzerinden dönülerek bildirim sırasında güvenli detach desteklenir
        for observer in list(self.observers):
            observer.update(event)
