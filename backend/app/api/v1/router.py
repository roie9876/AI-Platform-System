from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.agents import router as agents_router
from app.api.v1.model_endpoints import router as model_endpoints_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(model_endpoints_router, prefix="/model-endpoints", tags=["model-endpoints"])
