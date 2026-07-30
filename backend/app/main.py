from fastapi import FastAPI

from app.api.bills import router as bills_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(bills_router)
    app.include_router(tasks_router)
    return app


app = create_app()
