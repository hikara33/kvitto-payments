from app.enums import PaymentStatus


ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset({PaymentStatus.SUCCEEDED, PaymentStatus.FAILED}),
    PaymentStatus.SUCCEEDED: frozenset({PaymentStatus.REFUNDED}),
}


def can_transition(current: PaymentStatus, new: PaymentStatus) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())