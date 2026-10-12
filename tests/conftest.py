import hashlib
import hmac
import json
import os
from collections.abc import Callable, Iterator
from typing import Any

os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "kvitto_test")
os.environ["WEBHOOK_SECRET"] = "test-secret"

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import func, select, text

from app import models
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.models import Payment

WEBHOOK_SECRET = "test-secret"


def _ensure_test_database() -> None:
    name = settings.postgres_db
    assert name.endswith("_test"), "Тесты должны идти на отдельной базе с суффиксом _test"
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
        autocommit=True,
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    _ensure_test_database()
    Base.metadata.drop_all(engine)
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def api(client: TestClient) -> TestClient:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE payments RESTART IDENTITY"))
    return client


@pytest.fixture
def create_payment(api: TestClient) -> Callable[..., Any]:
    tariff_ids = {t["title"]: t["id"] for t in api.get("/tariffs").json()}

    def _create(*, tariff: str = "standard", headers: dict | None = None, **fields: Any):
        payload = {
            "tariff_id": tariff_ids[tariff],
            "email": "student@example.com",
            "method": "card",
            **fields,
        }
        return api.post("/payments", json=payload, headers=headers)

    return _create


@pytest.fixture
def webhook(api: TestClient) -> Callable[..., Any]:
    def _send(payment_id: int, status: str, signature: str | bytes | None = "auto"):
        body = json.dumps({"payment_id": payment_id, "status": status}).encode()
        headers = {"Content-Type": "application/json"}
        if signature == "auto":
            headers["X-Signature"] = hmac.new(
                WEBHOOK_SECRET.encode(), body, hashlib.sha256
            ).hexdigest()
        elif signature is not None:
            headers["X-Signature"] = signature
        return api.post("/webhooks/bank", content=body, headers=headers)

    return _send


@pytest.fixture
def payment_status() -> Callable[[int], str | None]:
    def _get(payment_id: int) -> str | None:
        with SessionLocal() as db:
            payment = db.get(Payment, payment_id)
            return payment.status if payment else None

    return _get


@pytest.fixture
def payment_count() -> Callable[[], int]:
    def _count() -> int:
        with SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(Payment)) or 0

    return _count