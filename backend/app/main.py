from fastapi import FastAPI

from app.api.agent import router as agent_router
from app.api.attachments import router as attachments_router
from app.api.bills import router as bills_router
from app.api.chat import router as chat_router
from app.api.data import router as data_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health_router)
    app.include_router(agent_router)
    app.include_router(attachments_router)
    app.include_router(dashboard_router)
    app.include_router(bills_router)
    app.include_router(tasks_router)
    app.include_router(chat_router)
    app.include_router(settings_router)
    app.include_router(data_router)
    return app


app = create_app()
