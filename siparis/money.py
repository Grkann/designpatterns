from decimal import Decimal, ROUND_HALF_UP


def to_money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt(value):
    return f"{to_money(value):.2f} TL"
