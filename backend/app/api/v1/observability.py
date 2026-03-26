from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.config_repo import ModelPricingRepository, CostAlertRepository
from app.services.observability_service import ObservabilityService
from app.api.v1.schemas import (
    DashboardSummaryResponse,
    TokenTimeSeriesResponse,
    CostBreakdownResponse,
    ExecutionLogListResponse,
    ModelPricingCreate,
    ModelPricingResponse,
    CostAlertCreate,
    CostAlertResponse,
)

router = APIRouter()
pricing_repo = ModelPricingRepository()
alert_repo = CostAlertRepository()


@router.get("/dashboard", response_model=DashboardSummaryResponse)
async def get_dashboard(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    agent_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_dashboard_summary(
        tenant_id, time_range, agent_id
    )
    return DashboardSummaryResponse(**data)


@router.get("/tokens")
async def get_token_usage(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    granularity: str = Query(default="1h", pattern=r"^(1h|6h|1d)$"),
    agent_id: Optional[str] = None,
    model_name: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_token_usage_over_time(
        tenant_id, time_range, granularity, agent_id, model_name
    )
    return {"data": data}


@router.get("/costs")
async def get_cost_breakdown(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    group_by: str = Query(default="agent", pattern=r"^(agent|model)$"),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_cost_breakdown(
        tenant_id, time_range, group_by
    )
    return {"data": data}


@router.get("/costs/top-agents")
async def get_top_agents(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_top_agents(
        tenant_id, time_range, limit
    )
    return {"data": data}


@router.get("/logs")
async def get_execution_logs(
    agent_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    time_range: Optional[str] = Query(default=None, pattern=r"^(1h|24h|7d|30d)$"),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    return await ObservabilityService.get_execution_logs(
        tenant_id, agent_id, limit, offset, time_range
    )


@router.get("/alerts")
async def get_triggered_alerts(
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.check_cost_alerts(tenant_id)
    return {"alerts": data}


@router.get("/pricing", response_model=list[ModelPricingResponse])
async def list_pricing(
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    items = await pricing_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.is_active = true AND (c.tenant_id = @tid OR NOT IS_DEFINED(c.tenant_id))",
        [{"name": "@tid", "value": tenant_id}],
    )
    return items


@router.post("/pricing", response_model=ModelPricingResponse, status_code=201)
async def create_pricing(
    body: ModelPricingCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    item = {
        "id": str(uuid4()),
        "model_name": body.model_name,
        "provider_type": body.provider_type,
        "input_price_per_1k": body.input_price_per_1k,
        "output_price_per_1k": body.output_price_per_1k,
        "currency": body.currency,
        "is_active": True,
        "tenant_id": tenant_id,
    }
    created = await pricing_repo.create(tenant_id, item)
    return created


@router.put("/pricing/{pricing_id}", response_model=ModelPricingResponse)
async def update_pricing(
    pricing_id: str,
    body: ModelPricingCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    pricing = await pricing_repo.get(tenant_id, pricing_id)
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing not found")
    pricing["model_name"] = body.model_name
    pricing["provider_type"] = body.provider_type
    pricing["input_price_per_1k"] = body.input_price_per_1k
    pricing["output_price_per_1k"] = body.output_price_per_1k
    pricing["currency"] = body.currency
    updated = await pricing_repo.update(tenant_id, pricing_id, pricing)
    return updated


@router.delete("/pricing/{pricing_id}", status_code=204)
async def delete_pricing(
    pricing_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await pricing_repo.delete(tenant_id, pricing_id)


@router.get("/cost-alerts", response_model=list[CostAlertResponse])
async def list_cost_alerts(
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    return await alert_repo.list_by_tenant(tenant_id)


@router.post("/cost-alerts", response_model=CostAlertResponse, status_code=201)
async def create_cost_alert(
    body: CostAlertCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    item = {
        "id": str(uuid4()),
        "name": body.name,
        "alert_type": body.alert_type,
        "threshold_amount": body.threshold_amount,
        "period": body.period,
        "scope_type": body.scope_type,
        "scope_id": body.scope_id,
        "tenant_id": tenant_id,
    }
    created = await alert_repo.create(tenant_id, item)
    return created


@router.put("/cost-alerts/{alert_id}", response_model=CostAlertResponse)
async def update_cost_alert(
    alert_id: str,
    body: CostAlertCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    alert = await alert_repo.get(tenant_id, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Cost alert not found")
    alert["name"] = body.name
    alert["alert_type"] = body.alert_type
    alert["threshold_amount"] = body.threshold_amount
    alert["period"] = body.period
    alert["scope_type"] = body.scope_type
    alert["scope_id"] = body.scope_id
    updated = await alert_repo.update(tenant_id, alert_id, alert)
    return updated


@router.delete("/cost-alerts/{alert_id}", status_code=204)
async def delete_cost_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await alert_repo.delete(tenant_id, alert_id)
