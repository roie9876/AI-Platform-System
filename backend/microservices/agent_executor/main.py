"""Agent Executor microservice — routes for chat, threads, memories."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middleware.tenant import TenantMiddleware
from app.repositories.cosmos_client import close_cosmos_client
from app.health import health_router

from app.api.v1.chat import router as chat_router
from app.api.v1.threads import router as threads_router
from app.api.v1.memories import router as memories_router


@asynccontextmanager
async def lifespan(app):
    yield
    await close_cosmos_client()


app = FastAPI(title="AI Platform - Agent Executor", version="0.1.0", lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router, prefix="/api/v1/agents", tags=["chat"])
app.include_router(threads_router, prefix="/api/v1/threads", tags=["threads"])
app.include_router(memories_router, prefix="/api/v1/agents", tags=["agent-memories"])
