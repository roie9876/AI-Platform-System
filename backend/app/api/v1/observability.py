from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.cost_config import ModelPricing, CostAlert
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


@router.get("/dashboard", response_model=DashboardSummaryResponse)
async def get_dashboard(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_dashboard_summary(
        db, UUID(tenant_id), time_range, agent_id
    )
    return DashboardSummaryResponse(**data)


@router.get("/tokens")
async def get_token_usage(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    granularity: str = Query(default="1h", pattern=r"^(1h|6h|1d)$"),
    agent_id: Optional[UUID] = None,
    model_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_token_usage_over_time(
        db, UUID(tenant_id), time_range, granularity, agent_id, model_name
    )
    return {"data": data}


@router.get("/costs")
async def get_cost_breakdown(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    group_by: str = Query(default="agent", pattern=r"^(agent|model)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_cost_breakdown(
        db, UUID(tenant_id), time_range, group_by
    )
    return {"data": data}


@router.get("/costs/top-agents")
async def get_top_agents(
    time_range: str = Query(default="7d", pattern=r"^(1h|24h|7d|30d)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.get_top_agents(
        db, UUID(tenant_id), time_range, limit
    )
    return {"data": data}


@router.get("/logs")
async def get_execution_logs(
    agent_id: Optional[UUID] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    time_range: Optional[str] = Query(default=None, pattern=r"^(1h|24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    return await ObservabilityService.get_execution_logs(
        db, UUID(tenant_id), agent_id, limit, offset, time_range
    )


@router.get("/alerts")
async def get_triggered_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data = await ObservabilityService.check_cost_alerts(db, UUID(tenant_id))
    return {"alerts": data}


@router.get("/pricing", response_model=list[ModelPricingResponse])
async def list_pricing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ModelPricing).where(
            ModelPricing.is_active == True,
            (ModelPricing.tenant_id == UUID(tenant_id)) | (ModelPricing.tenant_id.is_(None)),
        )
    )
    return list(result.scalars().all())


@router.post("/pricing", response_model=ModelPricingResponse, status_code=201)
async def create_pricing(
    body: ModelPricingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    pricing = ModelPricing(
        model_name=body.model_name,
        provider_type=body.provider_type,
        input_price_per_1k=body.input_price_per_1k,
        output_price_per_1k=body.output_price_per_1k,
        currency=body.currency,
        tenant_id=UUID(tenant_id),
    )
    db.add(pricing)
    await db.commit()
    await db.refresh(pricing)
    return pricing


@router.put("/pricing/{pricing_id}", response_model=ModelPricingResponse)
async def update_pricing(
    pricing_id: UUID,
    body: ModelPricingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ModelPricing).where(ModelPricing.id == pricing_id)
    )
    pricing = result.scalar_one_or_none()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing not found")
    pricing.model_name = body.model_name
    pricing.provider_type = body.provider_type
    pricing.input_price_per_1k = body.input_price_per_1k
    pricing.output_price_per_1k = body.output_price_per_1k
    pricing.currency = body.currency
    await db.commit()
    await db.refresh(pricing)
    return pricing


@router.delete("/pricing/{pricing_id}", status_code=204)
async def delete_pricing(
    pricing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await db.execute(delete(ModelPricing).where(ModelPricing.id == pricing_id))
    await db.commit()


@router.get("/cost-alerts", response_model=list[CostAlertResponse])
async def list_cost_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(CostAlert).where(CostAlert.tenant_id == UUID(tenant_id))
    )
    return list(result.scalars().all())


@router.post("/cost-alerts", response_model=CostAlertResponse, status_code=201)
async def create_cost_alert(
    body: CostAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    alert = CostAlert(
        name=body.name,
        alert_type=body.alert_type,
        threshold_amount=body.threshold_amount,
        period=body.period,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        tenant_id=UUID(tenant_id),
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.put("/cost-alerts/{alert_id}", response_model=CostAlertResponse)
async def update_cost_alert(
    alert_id: UUID,
    body: CostAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(CostAlert).where(
            CostAlert.id == alert_id,
            CostAlert.tenant_id == UUID(tenant_id),
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Cost alert not found")
    alert.name = body.name
    alert.alert_type = body.alert_type
    alert.threshold_amount = body.threshold_amount
    alert.period = body.period
    alert.scope_type = body.scope_type
    alert.scope_id = body.scope_id
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/cost-alerts/{alert_id}", status_code=204)
async def delete_cost_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await db.execute(
        delete(CostAlert).where(
            CostAlert.id == alert_id,
            CostAlert.tenant_id == UUID(tenant_id),
        )
    )
    await db.commit()
