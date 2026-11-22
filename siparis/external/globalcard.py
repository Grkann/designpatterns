class GlobalCardSDK:
    def __init__(self, max_amount=5000.0):
        self.max_amount = max_amount
        self.counter = 0
        self.charges = {}

    def create_charge(self, amount, currency, metadata):
        if currency != "TRY":
            return 400, ""
        if amount <= 0 or amount > self.max_amount:
            return 402, ""
        self.counter += 1
        charge_id = f"gc_{self.counter:04d}"
        self.charges[charge_id] = amount
        return 200, charge_id

    def reverse(self, charge_id, amount):
        if charge_id not in self.charges:
            return 404
        if amount <= 0 or amount > self.charges[charge_id] + 0.001:
            return 422
        self.charges[charge_id] -= amount
        return 200
