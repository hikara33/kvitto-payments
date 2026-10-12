import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.core.handlers import register_exception_handlers
from app.routers import payments, tariffs, webhooks
from app.seed import seed_tariffs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_tariffs(db)
    if settings.webhook_secret is None:
        logger.warning("WEBHOOK_SECRET не задан: подпись вебхуков банка не проверяется")
    yield


app = FastAPI(title="Kvitto Payments", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(tariffs.router)
app.include_router(payments.router)
app.include_router(webhooks.router)