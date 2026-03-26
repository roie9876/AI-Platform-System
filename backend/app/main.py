from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router
from app.middleware.tenant import TenantMiddleware
from app.repositories.cosmos_client import close_cosmos_client


@asynccontextmanager
async def lifespan(app):
    yield
    await close_cosmos_client()


app = FastAPI(
    title="AI Agent Platform",
    description="Multi-tenant AI Agent Platform as a Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
