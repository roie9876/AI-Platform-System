from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.agents import router as agents_router
from app.api.v1.model_endpoints import router as model_endpoints_router
from app.api.v1.chat import router as chat_router
from app.api.v1.tools import router as tools_router, agent_tools_router
from app.api.v1.data_sources import router as data_sources_router, agent_data_sources_router
from app.api.v1.ai_services import router as ai_services_router
from app.api.v1.azure_subscriptions import router as azure_subscriptions_router
from app.api.v1.azure_connections import router as azure_connections_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.knowledge import router as knowledge_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(model_endpoints_router, prefix="/model-endpoints", tags=["model-endpoints"])
api_router.include_router(chat_router, prefix="/agents", tags=["chat"])
api_router.include_router(tools_router, prefix="/tools", tags=["tools"])
api_router.include_router(agent_tools_router, prefix="/agents", tags=["agent-tools"])
api_router.include_router(data_sources_router, prefix="/data-sources", tags=["data-sources"])
api_router.include_router(agent_data_sources_router, prefix="/agents", tags=["agent-data-sources"])
api_router.include_router(ai_services_router, prefix="/ai-services", tags=["ai-services"])
api_router.include_router(azure_subscriptions_router, prefix="/azure", tags=["azure"])
api_router.include_router(azure_connections_router, prefix="/azure", tags=["azure-connections"])
api_router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])
