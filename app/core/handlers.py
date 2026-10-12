from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    InvalidTransitionError,
    PaymentNotFoundError,
    TariffNotFoundError,
    UnknownPromoCodeError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownPromoCodeError)
    async def unknown_promo_code(
        request: Request,
        exc: UnknownPromoCodeError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(TariffNotFoundError)
    async def tariff_not_found(
        request: Request,
        exc: TariffNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(PaymentNotFoundError)
    async def payment_not_found(
        request: Request,
        exc: PaymentNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidTransitionError)
    async def invalid_transition(
        request: Request,
        exc: InvalidTransitionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "invalid_transition"},
        )
