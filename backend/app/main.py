from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.agent import router as agent_router
from app.api.audit import router as audit_router
from app.api.attachments import router as attachments_router
from app.api.bootstrap import router as bootstrap_router
from app.api.bills import router as bills_router
from app.api.chat import router as chat_router
from app.api.data import router as data_router
from app.api.dashboard import router as dashboard_router
from app.api.diagnostics import router as diagnostics_router
from app.api.health import router as health_router
from app.api.ocr import router as ocr_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.core.error_handlers import register_exception_handlers
from app.core.config import settings
from app.core.request_middleware import register_request_middleware


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    register_request_middleware(app)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(bootstrap_router)
    app.include_router(audit_router)
    app.include_router(agent_router)
    app.include_router(attachments_router)
    app.include_router(dashboard_router)
    app.include_router(bills_router)
    app.include_router(tasks_router)
    app.include_router(chat_router)
    app.include_router(settings_router)
    app.include_router(data_router)
    app.include_router(diagnostics_router)
    app.include_router(ocr_router)
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if (frontend_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app


app = create_app()
