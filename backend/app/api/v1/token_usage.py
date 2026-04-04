"""Token usage and budget management API endpoints."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, Query

from app.middleware.tenant import get_tenant_id
from app.repositories.token_log_repository import TokenLogRepository

router = APIRouter(prefix="/token-usage", tags=["token-usage"])
_repo = TokenLogRepository()


@router.get("")
async def get_token_usage(
    request: Request,
    start: str = Query(None, description="ISO 8601 start date"),
    end: str = Query(None, description="ISO 8601 end date"),
    agent_id: str = Query(None, description="Filter by agent ID"),
):
    """Get token usage logs for the current tenant."""
    tenant_id = get_tenant_id(request)
    if not start:
        start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    if not end:
        end = datetime.now(timezone.utc).isoformat()
    logs = await _repo.get_usage_by_date_range(tenant_id, start, end)
    if agent_id:
        logs = [log for log in logs if log.get("agent_id") == agent_id]
    return {"usage": logs, "count": len(logs)}


@router.get("/summary")
async def get_token_usage_summary(
    request: Request,
    start: str = Query(None, description="ISO 8601 start date"),
    end: str = Query(None, description="ISO 8601 end date"),
):
    """Get aggregated token usage summary for the current tenant."""
    tenant_id = get_tenant_id(request)
    if not start:
        start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    if not end:
        end = datetime.now(timezone.utc).isoformat()
    total = await _repo.get_tenant_total_tokens(tenant_id, start, end)
    logs = await _repo.get_usage_by_date_range(tenant_id, start, end)
    return {
        "tenant_id": tenant_id,
        "period": {"start": start, "end": end},
        "total_tokens": total,
        "request_count": len(logs),
    }
