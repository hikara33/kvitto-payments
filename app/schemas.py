from datetime import datetime
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
    EmailStr
)

from app.enums import PaymentMethod, PaymentStatus


InstallmentMonths = Literal[3, 6, 12]

class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: int


class PaymentCreate(BaseModel):
    tariff_id: int
    email: EmailStr
    method: PaymentMethod
    installment_months: InstallmentMonths | None = None
    promo_code: str | None = None

    @field_validator("promo_code")
    @classmethod
    def blank_promo_code_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def check_installment_months(self) -> Self:
        if self.method is PaymentMethod.INSTALLMENT:
            if self.installment_months is None:
                raise ValueError(
                    "installment_months is required for installment and must be 3, 6 or 12"
                )
        elif self.installment_months is not None:
            raise ValueError("installment_months is allowed only for installment")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PaymentStatus
    tariff_id: int
    amount: int  # копейки, уже со скидкой
    discount: int
    method: PaymentMethod
    installment_months: InstallmentMonths | None
    schedule: list[int] | None
    email: str
    created_at: datetime


class WebhookIn(BaseModel):
    payment_id: int
    status: PaymentStatus


class WebhookOut(BaseModel):
    result: Literal["ok"] = "ok"


class ErrorOut(BaseModel):
    error: str