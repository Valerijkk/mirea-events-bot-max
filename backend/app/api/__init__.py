"""REST API: префикс `/api/v1/...`. Версия в URL — на случай несовместимых изменений (v2 без слома клиентов)."""
from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.broadcasts import router as broadcasts_router
from app.api.v1.events import router as events_router
from app.api.v1.health import router as health_router
from app.api.v1.integration import router as integration_router
from app.api.v1.organizers import router as organizers_router
from app.api.v1.registrations import router as registrations_router
from app.api.v1.scan import router as scan_router
from app.api.v1.slots import router as slots_router
from app.api.v1.stats import router as stats_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(slots_router)
api_v1_router.include_router(registrations_router)
api_v1_router.include_router(organizers_router)
api_v1_router.include_router(scan_router)
api_v1_router.include_router(broadcasts_router)
api_v1_router.include_router(stats_router)
api_v1_router.include_router(integration_router)
api_v1_router.include_router(audit_router)

__all__ = ["api_v1_router"]
