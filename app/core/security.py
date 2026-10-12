import hashlib
import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings


def compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def verify_webhook_signature(
    request: Request,
    x_signature: Annotated[str | None, Header()] = None,
) -> None:
    secret = settings.webhook_secret
    if secret is None:
        return

    body = await request.body()
    expected = compute_signature(secret, body).encode()
    provided = (x_signature or "").encode()

    if not hmac.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )