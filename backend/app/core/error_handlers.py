from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)


def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    content = _error_content(
        status_code=exc.status_code,
        code=_code_for_status(exc.status_code),
        message=_message_for_detail(detail, exc.status_code),
        path=request.url.path,
        detail=detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(content),
        headers=exc.headers,
    )


def _validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    content = _error_content(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="Request validation failed",
        path=request.url.path,
        detail=errors,
        issues=errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(content),
    )


def _error_content(
    *,
    status_code: int,
    code: str,
    message: str,
    path: str,
    detail: Any,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "status_code": status_code,
        "path": path,
    }
    if issues is not None:
        error["issues"] = issues
    return {
        "detail": detail,
        "error": error,
    }


def _code_for_status(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "payload_too_large",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    }.get(status_code, f"http_{status_code}")


def _message_for_detail(detail: Any, status_code: int) -> str:
    if isinstance(detail, str):
        return detail
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP error"
