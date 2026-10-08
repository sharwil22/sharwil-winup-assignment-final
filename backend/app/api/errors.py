"""One error shape for every failure: {"error": {"code", "message", "retryable"}}.

Internal details (stack traces, SDK messages) are logged, never returned.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.llm.contracts import LLMNotConfigured, LLMUnavailable
from app.services.session_store import SessionNotFound, VersionConflict

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable


def error_response(status: int, code: str, message: str, retryable: bool = False) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "retryable": retryable}}
    return JSONResponse(status_code=status, content=body)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.retryable)

    @app.exception_handler(SessionNotFound)
    async def _not_found(_: Request, exc: SessionNotFound) -> JSONResponse:
        return error_response(404, "session_not_found", "This session does not exist.")

    @app.exception_handler(VersionConflict)
    async def _conflict(_: Request, exc: VersionConflict) -> JSONResponse:
        return error_response(
            409,
            "version_conflict",
            "This session changed in another request. Reload it and try again.",
            retryable=True,
        )

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'] if p != 'body')}: {err['msg']}"
            for err in exc.errors()[:5]
        )
        return error_response(422, "validation_error", problems or "Invalid request.")

    @app.exception_handler(LLMNotConfigured)
    async def _not_configured(_: Request, exc: LLMNotConfigured) -> JSONResponse:
        logger.warning("llm_not_configured: %s", exc)
        return error_response(
            503,
            "llm_not_configured",
            f"The AI model is not configured: {exc}. Set ANTHROPIC_API_KEY in backend/.env "
            "or use LLM_PROVIDER=mock.",
        )

    @app.exception_handler(LLMUnavailable)
    async def _unavailable(_: Request, exc: LLMUnavailable) -> JSONResponse:
        logger.warning("llm_unavailable: %s", exc)
        return error_response(
            503,
            "llm_unavailable",
            "The AI model is temporarily unavailable. Your answers are safe; please try again.",
            retryable=True,
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return error_response(500, "internal_error", "Something went wrong on our side.")
