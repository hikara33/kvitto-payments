from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidTransitionError,
    PaymentNotFoundError,
    TariffNotFoundError,
)
from app.enums import PaymentMethod, PaymentStatus
from app.models import Payment, Tariff
from app.services.pricing import build_schedule, calculate_discount
from app.services.statuses import can_transition


def find_by_idempotency_key(db: Session, key: str) -> Payment | None:
    return db.scalars(select(Payment).where(Payment.idempotency_key == key)).first()


def create_payment(
    db: Session,
    *,
    tariff_id: int,
    email: str,
    method: PaymentMethod,
    installment_months: int | None,
    promo_code: str | None,
    idempotency_key: str | None,
) -> tuple[Payment, bool]:
    if idempotency_key is not None:
        existing = find_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing, False

    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        raise TariffNotFoundError(tariff_id)

    discount = calculate_discount(tariff.price, promo_code)
    amount = tariff.price - discount
    is_installment = method is PaymentMethod.INSTALLMENT
    schedule = (
        build_schedule(amount, installment_months)
        if is_installment and installment_months is not None
        else None
    )

    payment = Payment(
        status=PaymentStatus.PENDING.value,
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=method.value,
        installment_months=installment_months if is_installment else None,
        schedule=schedule,
        email=email,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key is not None:
            existing = find_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return existing, False
        raise
    return payment, True


def get_payment(db: Session, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise PaymentNotFoundError(payment_id)
    return payment


def list_payments(
    db: Session,
    *,
    email: str | None,
    status: PaymentStatus | None,
    limit: int,
    offset: int,
) -> Sequence[Payment]:
    query = select(Payment).order_by(Payment.id)
    if email is not None:
        query = query.where(func.lower(Payment.email) == email.strip().lower())
    if status is not None:
        query = query.where(Payment.status == status.value)
    return db.scalars(query.limit(limit).offset(offset)).all()


def apply_bank_status(db: Session, payment_id: int, new_status: PaymentStatus) -> Payment:
    payment = db.scalars(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).one_or_none()
    if payment is None:
        raise PaymentNotFoundError(payment_id)

    current = payment.status
    if not can_transition(current, new_status):
        db.rollback()
        raise InvalidTransitionError(current, new_status)

    payment.status = new_status
    db.commit()
    return payment