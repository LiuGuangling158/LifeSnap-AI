from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"


def register_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _request_id_from_header(request) or uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _request_id_from_header(request: Request) -> str | None:
    value = request.headers.get(REQUEST_ID_HEADER)
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:128]
