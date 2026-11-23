# Adapter (Yapısal) — 1. Aşama İyileştirilmiş Sürüm
# Target: PaymentGateway
# Adapter: KolayPayAdapter, GlobalCardAdapter, FailoverPaymentGateway
# Adaptee: KolayPayClient, GlobalCardSDK
# Client: CheckoutService, RefundHandler

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from .money import to_money


@dataclass
class PaymentResult:
    success: bool
    transaction_id: str | None
    message: str = ""
    provider: str = ""


class PaymentGateway(ABC):
    provider_name = ""

    @abstractmethod
    def charge(self, amount: Decimal | int | float, customer_id: str) -> PaymentResult:
        pass

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal | int | float) -> PaymentResult:
        pass


class KolayPayAdapter(PaymentGateway):
    provider_name = "KolayPay"

    def __init__(self, client) -> None:
        self.client = client

    def charge(self, amount: Decimal | int | float, customer_id: str) -> PaymentResult:
        resp = self.client.odeme_al(self.to_kurus(amount), customer_id)
        return self.convert(resp)

    def refund(self, transaction_id: str, amount: Decimal | int | float) -> PaymentResult:
        if not transaction_id:
            return PaymentResult(False, None, "Geçersiz işlem numarası", self.provider_name)
        resp = self.client.iade_et(transaction_id, self.to_kurus(amount))
        return self.convert(resp)

    def to_kurus(self, amount: Decimal | int | float) -> int:
        # Decimal tabanlı to_money ile ikili float yuvarlama hatalarını önler
        return int(to_money(amount) * 100)

    def convert(self, resp: dict) -> PaymentResult:
        ok = resp["durum"] == "BASARILI"
        return PaymentResult(
            success=ok,
            transaction_id=resp.get("islem_no"),
            message=resp.get("aciklama", "Onaylandı"),
            provider=self.provider_name,
        )


class GlobalCardAdapter(PaymentGateway):
    provider_name = "GlobalCard"
    messages = {
        200: "Approved",
        400: "Unsupported currency",
        402: "Card declined",
        404: "Charge not found",
        422: "Invalid refund amount",
    }

    def __init__(self, sdk) -> None:
        self.sdk = sdk

    def charge(self, amount: Decimal | int | float, customer_id: str) -> PaymentResult:
        normalized = float(to_money(amount))
        status, charge_id = self.sdk.create_charge(normalized, "TRY", {"customer": customer_id})
        if status != 200:
            charge_id = None
        return PaymentResult(
            success=status == 200,
            transaction_id=charge_id,
            message=self.messages.get(status, str(status)),
            provider=self.provider_name,
        )

    def refund(self, transaction_id: str, amount: Decimal | int | float) -> PaymentResult:
        if not transaction_id:
            return PaymentResult(False, None, "Charge not found", self.provider_name)
        normalized = float(to_money(amount))
        status = self.sdk.reverse(transaction_id, normalized)
        tx = transaction_id if status == 200 else None
        return PaymentResult(
            success=status == 200,
            transaction_id=tx,
            message=self.messages.get(status, str(status)),
            provider=self.provider_name,
        )


class FailoverPaymentGateway(PaymentGateway):
    """Yeni özellik: Birincil ödeme sağlayıcısı başarısız olursa otomatik yedek sağlayıcıya geçer.

    PaymentGateway arayüzünü uyguladığı için CheckoutService ve RefundHandler
    değiştirilmeden yedekli ödeme desteği kazanır (Açık/Kapalı Prensibi).
    """

    def __init__(self, primary: PaymentGateway, secondary: PaymentGateway) -> None:
        self.primary = primary
        self.secondary = secondary
        self.provider_name = f"{primary.provider_name}->{secondary.provider_name}"
        self._tx_owner: dict[str, PaymentGateway] = {}

    def charge(self, amount: Decimal | int | float, customer_id: str) -> PaymentResult:
        first = self.primary.charge(amount, customer_id)
        if first.success and first.transaction_id:
            self._tx_owner[first.transaction_id] = self.primary
            return first

        second = self.secondary.charge(amount, customer_id)
        if second.success and second.transaction_id:
            self._tx_owner[second.transaction_id] = self.secondary
        return second

    def refund(self, transaction_id: str, amount: Decimal | int | float) -> PaymentResult:
        owner = self._tx_owner.get(transaction_id)
        if owner is not None:
            return owner.refund(transaction_id, amount)

        # Kayıtta yoksa önce birincil, başarısızsa ikincil denenir
        first = self.primary.refund(transaction_id, amount)
        if first.success:
            return first
        return self.secondary.refund(transaction_id, amount)
