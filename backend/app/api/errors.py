from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.api.common import ErrorResponse

logger = logging.getLogger("app.api.error")


class AppError(Exception):
    """Application-level exception that maps cleanly to the frozen API contract."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details
        self.retryable = retryable

    @classmethod
    def resource_not_found(cls, message: str, details: dict[str, Any] | None = None) -> "AppError":
        return cls(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            message=message,
            details=details,
            retryable=False,
        )

    @classmethod
    def dependency_unavailable(cls, message: str, details: dict[str, Any] | None = None) -> "AppError":
        return cls(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="DEPENDENCY_UNAVAILABLE",
            message=message,
            details=details,
            retryable=True,
        )

    @classmethod
    def invalid_state_transition(cls, message: str, details: dict[str, Any] | None = None) -> "AppError":
        return cls(
            status_code=status.HTTP_409_CONFLICT,
            error_code="INVALID_STATE_TRANSITION",
            message=message,
            details=details,
            retryable=False,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            retryable=exc.retryable,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_REQUEST",
            message="Request validation failed.",
            details={"errors": jsonable_encoder(exc.errors())},
            retryable=False,
        )


def _error_response(
    *,
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None,
    retryable: bool,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        trace_id=getattr(request.state, "request_id", None),
        retryable=retryable,
    )
    extra = {
        "request_id": payload.trace_id,
        "error_code": error_code,
        "status_code": status_code,
        "retryable": retryable,
        "path": request.url.path,
    }
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("api_error_response", extra=extra)
    else:
        logger.warning("api_error_response", extra=extra)
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
