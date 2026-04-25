from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.readings import router as readings_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.traces import router as traces_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(readings_router)
api_router.include_router(sessions_router)
api_router.include_router(traces_router)
