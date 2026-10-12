from app.core.exceptions import UnknownPromoCodeError

PROMO_CODES: dict[str, int] = {"KVITTO10": 10}


def calculate_discount(price: int, promo_code: str | None) -> int:
    if promo_code is None:
        return 0
    percent = PROMO_CODES.get(promo_code.strip().upper())
    if percent is None:
        raise UnknownPromoCodeError(promo_code)
    return price * percent // 100


def build_schedule(amount: int, months: int) -> list[int]:
    if months <= 0:
        raise ValueError("months must be positive")
    base, extra = divmod(amount, months)
    return [base + 1 if i < extra else base for i in range(months)]