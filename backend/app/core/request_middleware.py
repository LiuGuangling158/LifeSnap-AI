from uuid import uuid4
from time import perf_counter

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.services.observability_service import observability_service


REQUEST_ID_HEADER = "X-Request-ID"


def register_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _request_id_from_header(request) or uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            if request.url.path != "/metrics":
                observability_service.record_http(
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=(perf_counter() - started) * 1000,
                    request_id=request_id,
                    user_id=getattr(request.state, "user_id", None),
                )


def _request_id_from_header(request: Request) -> str | None:
    value = request.headers.get(REQUEST_ID_HEADER)
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:128]
