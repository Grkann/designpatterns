# Observer
# Subject: OrderSubject, ConcreteSubject: Order
# Observer: OrderObserver, ConcreteObserver: observers.py içindeki sınıflar

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OrderEvent:
    order: object
    old_state: object
    new_state: object


class OrderObserver(ABC):
    @abstractmethod
    def update(self, event):
        pass


class OrderSubject(ABC):
    def __init__(self):
        self.observers = []

    def attach(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer):
        self.observers.remove(observer)

    def notify(self, event):
        for observer in self.observers:
            observer.update(event)
