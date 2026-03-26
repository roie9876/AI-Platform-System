"""Workflow Engine microservice — routes for workflows."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middleware.tenant import TenantMiddleware
from app.repositories.cosmos_client import close_cosmos_client
from app.health import health_router

from app.api.v1.workflows import router as workflows_router


@asynccontextmanager
async def lifespan(app):
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - Workflow Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(workflows_router, prefix="/api/v1/workflows", tags=["workflows"])
