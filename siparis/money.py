from decimal import Decimal, ROUND_HALF_UP


def to_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt(value: Decimal | int | float | str) -> str:
    return f"{to_money(value):.2f} TL"
