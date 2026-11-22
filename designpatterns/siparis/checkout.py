from .delivery import PriceCalculator
from .order import PaymentRecord


class PaymentFailedError(Exception):
    pass


class CheckoutService:
    def __init__(self, gateway):
        self.gateway = gateway

    def quote_options(self, order, strategies):
        calculator = PriceCalculator(strategies[0])
        quotes = []
        for strategy in strategies:
            calculator.set_strategy(strategy)
            quotes.append(calculator.calculate(order))
        return quotes

    def checkout(self, order, strategy):
        if strategy.requires_courier and order.address is None:
            raise ValueError(f"'{strategy.name}' için teslimat adresi gerekli.")

        breakdown = PriceCalculator(strategy).calculate(order)
        result = self.gateway.charge(breakdown.total, order.customer.id)
        if not result.success:
            raise PaymentFailedError(f"{self.gateway.provider_name}: {result.message}")

        order.record_payment(PaymentRecord(result.transaction_id, self.gateway.provider_name, breakdown))
        return breakdown
