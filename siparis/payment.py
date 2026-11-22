# Adapter
# Target: PaymentGateway
# Adapter: KolayPayAdapter, GlobalCardAdapter
# Adaptee: KolayPayClient, GlobalCardSDK
# Client: CheckoutService, RefundHandler

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PaymentResult:
    success: bool
    transaction_id: str
    message: str = ""


class PaymentGateway(ABC):
    provider_name = ""

    @abstractmethod
    def charge(self, amount, customer_id):
        pass

    @abstractmethod
    def refund(self, transaction_id, amount):
        pass


class KolayPayAdapter(PaymentGateway):
    provider_name = "KolayPay"

    def __init__(self, client):
        self.client = client

    def charge(self, amount, customer_id):
        resp = self.client.odeme_al(self.to_kurus(amount), customer_id)
        return self.convert(resp)

    def refund(self, transaction_id, amount):
        resp = self.client.iade_et(transaction_id, self.to_kurus(amount))
        return self.convert(resp)

    def to_kurus(self, amount):
        return int(round(amount * 100))

    def convert(self, resp):
        ok = resp["durum"] == "BASARILI"
        return PaymentResult(ok, resp.get("islem_no"), resp.get("aciklama", "Onaylandı"))


class GlobalCardAdapter(PaymentGateway):
    provider_name = "GlobalCard"
    messages = {
        200: "Approved",
        400: "Unsupported currency",
        402: "Card declined",
        404: "Charge not found",
        422: "Invalid refund amount",
    }

    def __init__(self, sdk):
        self.sdk = sdk

    def charge(self, amount, customer_id):
        status, charge_id = self.sdk.create_charge(float(amount), "TRY", {"customer": customer_id})
        if status != 200:
            charge_id = None
        return PaymentResult(status == 200, charge_id, self.messages.get(status, str(status)))

    def refund(self, transaction_id, amount):
        status = self.sdk.reverse(transaction_id, float(amount))
        tx = transaction_id if status == 200 else None
        return PaymentResult(status == 200, tx, self.messages.get(status, str(status)))
