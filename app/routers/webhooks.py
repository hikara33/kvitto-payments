from fastapi import APIRouter, Depends

from app.core.deps import DbSession
from app.core.security import verify_webhook_signature
from app.schemas import ErrorOut, WebhookIn, WebhookOut
from app.services import payments as payments_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/bank",
    response_model=WebhookOut,
    dependencies=[Depends(verify_webhook_signature)],
    responses={
        401: {"description": "Неверная или отсутствующая подпись X-Signature"},
        404: {"description": "Платёж не найден"},
        409: {"model": ErrorOut, "description": "Запрещённый переход статуса"},
    },
)
def bank_webhook(body: WebhookIn, db: DbSession) -> WebhookOut:
    payments_service.apply_bank_status(db, body.payment_id, body.status)
    return WebhookOut()