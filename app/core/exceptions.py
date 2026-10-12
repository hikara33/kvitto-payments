from app.enums import PaymentStatus


class DomainError(Exception):
    pass


class UnknownPromoCodeError(DomainError):
    def __init__(self, code: str) -> None:
        super().__init__(f"Unknown promo code: {code!r}")
        self.code = code


class TariffNotFoundError(DomainError):
    def __init__(self, tariff_id: int) -> None:
        super().__init__(f"Tariff {tariff_id} not found")
        self.tariff_id = tariff_id


class PaymentNotFoundError(DomainError):
    def __init__(self, payment_id: int) -> None:
        super().__init__(f"Payment {payment_id} not found")
        self.payment_id = payment_id


class InvalidTransitionError(DomainError):
    def __init__(
        self,
        current: PaymentStatus,
        new: PaymentStatus,
    ) -> None:
        super().__init__(f"Transition {current} -> {new} is not allowed")
        self.current = current
        self.new = new