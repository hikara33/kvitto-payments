from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Header, Response, Query
from fastapi import status as http_status

from app.core.deps import DbSession
from app.models import Payment
from app.enums import PaymentStatus
from app.schemas import PaymentCreate, PaymentOut
from app.services import payments as payments_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentOut,
    status_code=http_status.HTTP_201_CREATED,
    responses={
        200: {"model": PaymentOut, "description": "Платёж с таким Idempotency-Key уже есть"}
    },
)
def create_payment(
    body: PaymentCreate,
    response: Response,
    db: DbSession,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=255)
    ] = None,
) -> Payment:
    payment, created = payments_service.create_payment(
        db,
        tariff_id=body.tariff_id,
        email=body.email,
        method=body.method,
        installment_months=body.installment_months,
        promo_code=body.promo_code,
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = http_status.HTTP_200_OK
    return payment


@router.get(
    "/{payment_id}",
    response_model=PaymentOut,
    responses={404: {"description": "Платёж не найден"}},
)
def get_payment(payment_id: int, db: DbSession) -> Payment:
    return payments_service.get_payment(db, payment_id)


@router.get("", response_model=list[PaymentOut])
def list_payments(
    db: DbSession,
    email: str | None = None,
    status: PaymentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Payment]:
    return payments_service.list_payments(
        db, email=email, status=status, limit=limit, offset=offset
    )