from dataclasses import dataclass
from decimal import Decimal

from .money import to_money
from .notifications import OrderEvent, OrderSubject
from .order_state import AwaitingPaymentState


@dataclass
class Customer:
    id: str
    name: str
    phone: str


@dataclass
class InvoiceInfo:
    company_name: str
    tax_number: str
    tax_office: str = ""


@dataclass
class PaymentRecord:
    transaction_id: str
    provider: str
    breakdown: object


# Builder'ın Product'ı, State'in Context'i, Observer'ın ConcreteSubject'i
class Order(OrderSubject):
    def __init__(
        self,
        order_id: int,
        customer: Customer,
        items: list,
        address: str | None,
        distance_km: float,
        note: str = "",
        coupon_code: str | None = None,
        coupon_rate: Decimal = Decimal("0"),
        invoice: InvoiceInfo | None = None,
    ) -> None:
        super().__init__()
        self.id = order_id
        self.customer = customer
        self.items = list(items)
        self.address = address
        self.distance_km = distance_km
        self.note = note
        self.coupon_code = coupon_code
        self.coupon_rate = coupon_rate
        self.invoice = invoice
        self.state = AwaitingPaymentState()
        self.transaction_id: str | None = None
        self.payment_provider: str | None = None
        self.price = None

    def item_descriptions(self) -> list[str]:
        counts: dict[str, int] = {}
        for item in self.items:
            desc = item.description()
            counts[desc] = counts.get(desc, 0) + 1
        result = []
        for desc, n in counts.items():
            result.append(f"{n}x {desc}" if n > 1 else desc)
        return result

    def subtotal(self) -> Decimal:
        total = Decimal("0")
        for item in self.items:
            total += item.price()
        return to_money(total)

    @property
    def requires_courier(self) -> bool:
        if self.price is None:
            return True
        return self.price.requires_courier

    @property
    def paid_amount(self) -> Decimal:
        if self.price is None:
            return Decimal("0.00")
        return self.price.total

    def record_payment(self, payment: PaymentRecord) -> None:
        self.state.mark_paid(self, payment)

    def accept(self) -> None:
        self.state.accept(self)

    def hand_over(self) -> None:
        self.state.hand_over(self)

    def complete(self) -> None:
        self.state.complete(self)

    def cancel(self, reason: str) -> None:
        self.state.cancel(self, reason)

    def apply_payment(self, payment: PaymentRecord) -> None:
        self.transaction_id = payment.transaction_id
        self.payment_provider = payment.provider
        self.price = payment.breakdown

    def change_state(self, new_state) -> None:
        old_state = self.state
        self.state = new_state
        self.notify(OrderEvent(self, old_state, new_state))

    def __repr__(self) -> str:
        return f"Order(#{self.id}, {self.customer.name}, {self.state.name})"
