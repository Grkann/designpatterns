from .delivery import DeliveryStrategy, PriceBreakdown, PriceCalculator
from .order import PaymentRecord
from .order_state import InvalidTransitionError


class PaymentFailedError(Exception):
    pass


class CheckoutService:
    def __init__(self, gateway):
        self.gateway = gateway

    def quote_options(self, order, strategies: list[DeliveryStrategy]) -> list[PriceBreakdown]:
        """Siparişe uygun teslimat seçeneklerini ucuzdan pahalıya listeler."""
        if not strategies:
            raise ValueError("En az bir teslimat seçeneği verilmeli.")
        return PriceCalculator(strategies[0]).compare(order, strategies)

    def checkout(self, order, strategy: DeliveryStrategy) -> PriceBreakdown:
        # Ödenmiş ya da iptal edilmiş siparişten tekrar para çekilmesin: kararı siparişin durumu (State) verir.
        if "mark_paid" not in order.state.allowed_actions():
            raise InvalidTransitionError(f"'{order.state.name}' durumundaki sipariş için ödeme alınamaz.")
        # Yöntemin bu siparişe uygun olup olmadığına strateji karar verir (adres, mesafe sınırı...).
        breakdown = PriceCalculator(strategy).calculate(order)
        result = self.gateway.charge(breakdown.total, order.customer.id)
        if not result.success:
            raise PaymentFailedError(f"{self.gateway.provider_name}: {result.message}")

        order.record_payment(PaymentRecord(result.transaction_id, self.gateway.provider_name, breakdown))
        return breakdown
