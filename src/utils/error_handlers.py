"""
Centralized error handling for FastAPI
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
from datetime import datetime
from typing import Union
import traceback

from src.exceptions import SetsAIException
from src.utils.logging import StructuredLogger, get_request_context

logger = StructuredLogger(__name__)


async def sets_ai_exception_handler(request: Request, exc: SetsAIException) -> JSONResponse:
    """Handle custom SetsAI exceptions"""
    context = get_request_context()

    logger.error(
        f"Application error: {exc.error_code.value}",
        error_code=exc.error_code.value,
        error_message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        path=request.url.path,
        method=request.method,
        cause=str(exc.cause) if exc.cause else None,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.to_dict(),
            "request_id": context.get("request_id", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path,
        },
    )


async def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, PydanticValidationError]
) -> JSONResponse:
    """Handle Pydantic validation errors"""
    context = get_request_context()

    # Extract validation error details
    errors = []
    if hasattr(exc, "errors"):
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
            errors.append(
                {
                    "field": field_path,
                    "message": error.get("msg", "Validation error"),
                    "type": error.get("type", "validation_error"),
                    "input": error.get("input"),
                }
            )

    logger.warning(
        "Validation error occurred",
        error_type="validation_error",
        validation_errors=errors,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"validation_errors": errors},
            },
            "request_id": context.get("request_id", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions"""
    context = get_request_context()

    # Map HTTP status codes to error codes
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")

    logger.warning(
        f"HTTP exception: {exc.status_code}",
        error_code=error_code,
        error_message=exc.detail,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": error_code, "message": exc.detail, "status_code": exc.status_code},
            "request_id": context.get("request_id", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path,
        },
    )


async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle Starlette HTTP exceptions"""
    context = get_request_context()

    logger.warning(
        f"Starlette HTTP exception: {exc.status_code}",
        error_message=exc.detail,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": "HTTP_ERROR", "message": exc.detail, "status_code": exc.status_code},
            "request_id": context.get("request_id", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    context = get_request_context()

    # Get traceback for debugging
    tb_str = traceback.format_exc()

    logger.error(
        "Unhandled exception occurred",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
        method=request.method,
        traceback=tb_str,
        exc_info=True,
    )

    # Don't expose internal error details in production
    error_message = "An unexpected error occurred"
    details = {}

    # In development, include more details
    if context.get("service") == "test" or request.headers.get("X-Debug") == "true":
        error_message = str(exc)
        details = {
            "exception_type": type(exc).__name__,
            "traceback": tb_str.split("\n")[-10:],  # Last 10 lines
        }

    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "INTERNAL_ERROR", "message": error_message, "details": details},
            "request_id": context.get("request_id", "unknown"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path,
        },
    )


def register_error_handlers(app):
    """Register all error handlers with the FastAPI app"""

    # Custom application exceptions
    app.add_exception_handler(SetsAIException, sets_ai_exception_handler)

    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, validation_exception_handler)

    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)

    # Catch-all for unexpected exceptions
    app.add_exception_handler(Exception, general_exception_handler)
