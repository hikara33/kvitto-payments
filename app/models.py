from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.enums import PaymentStatus, PaymentMethod


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50), unique=True)
    price: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False
    )
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id"))
    amount: Mapped[int] = mapped_column(Integer)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), nullable=False
    )
    installment_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    email: Mapped[str] = mapped_column(String(255))

    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )