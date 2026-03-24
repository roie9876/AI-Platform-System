from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.middleware.tenant import get_tenant_id
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.evaluation import TestSuite, TestCase, EvaluationRun, EvaluationResult
from app.services.evaluation_service import EvaluationService
from app.api.v1.schemas import (
    TestSuiteCreate,
    TestSuiteResponse,
    TestCaseCreate,
    TestCaseResponse,
    EvaluationRunResponse,
    EvaluationResultResponse,
)

router = APIRouter()


# --- Test Suite CRUD ---

@router.get("/test-suites", response_model=list[TestSuiteResponse])
async def list_test_suites(
    agent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    query = select(TestSuite).where(TestSuite.tenant_id == UUID(tenant_id))
    if agent_id:
        query = query.where(TestSuite.agent_id == agent_id)
    result = await db.execute(query.order_by(TestSuite.created_at.desc()))
    suites = list(result.scalars().all())
    return suites


@router.post("/test-suites", response_model=TestSuiteResponse, status_code=201)
async def create_test_suite(
    body: TestSuiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    suite = TestSuite(
        name=body.name,
        description=body.description,
        agent_id=body.agent_id,
        tenant_id=UUID(tenant_id),
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return suite


@router.get("/test-suites/{suite_id}", response_model=TestSuiteResponse)
async def get_test_suite(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(TestSuite).where(
            TestSuite.id == suite_id,
            TestSuite.tenant_id == UUID(tenant_id),
        )
    )
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return suite


@router.put("/test-suites/{suite_id}", response_model=TestSuiteResponse)
async def update_test_suite(
    suite_id: UUID,
    body: TestSuiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(TestSuite).where(
            TestSuite.id == suite_id,
            TestSuite.tenant_id == UUID(tenant_id),
        )
    )
    suite = result.scalar_one_or_none()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    suite.name = body.name
    suite.description = body.description
    suite.agent_id = body.agent_id
    await db.commit()
    await db.refresh(suite)
    return suite


@router.delete("/test-suites/{suite_id}", status_code=204)
async def delete_test_suite(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await db.execute(
        delete(TestSuite).where(
            TestSuite.id == suite_id,
            TestSuite.tenant_id == UUID(tenant_id),
        )
    )
    await db.commit()


# --- Test Cases ---

@router.post("/test-suites/{suite_id}/cases", response_model=TestCaseResponse, status_code=201)
async def add_test_case(
    suite_id: UUID,
    body: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    # Verify suite exists and belongs to tenant
    result = await db.execute(
        select(TestSuite).where(
            TestSuite.id == suite_id,
            TestSuite.tenant_id == UUID(tenant_id),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test suite not found")

    case = TestCase(
        test_suite_id=suite_id,
        input_message=body.input_message,
        expected_output=body.expected_output,
        expected_keywords=body.expected_keywords,
        metadata_=body.metadata_,
        order_index=body.order_index,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.put("/test-suites/{suite_id}/cases/{case_id}", response_model=TestCaseResponse)
async def update_test_case(
    suite_id: UUID,
    case_id: UUID,
    body: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(TestCase).where(TestCase.id == case_id, TestCase.test_suite_id == suite_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    case.input_message = body.input_message
    case.expected_output = body.expected_output
    case.expected_keywords = body.expected_keywords
    case.metadata_ = body.metadata_
    case.order_index = body.order_index
    await db.commit()
    await db.refresh(case)
    return case


@router.delete("/test-suites/{suite_id}/cases/{case_id}", status_code=204)
async def delete_test_case(
    suite_id: UUID,
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await db.execute(
        delete(TestCase).where(TestCase.id == case_id, TestCase.test_suite_id == suite_id)
    )
    await db.commit()


# --- Evaluation Runs ---

@router.post("/test-suites/{suite_id}/run", response_model=EvaluationRunResponse)
async def trigger_evaluation_run(
    suite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    try:
        run_id = await EvaluationService.run_evaluation(db, suite_id, UUID(tenant_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id == run_id)
    )
    return result.scalar_one()


@router.get("/runs", response_model=list[EvaluationRunResponse])
async def list_runs(
    agent_id: Optional[UUID] = None,
    suite_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    query = select(EvaluationRun).where(EvaluationRun.tenant_id == UUID(tenant_id))
    if agent_id:
        query = query.where(EvaluationRun.agent_id == agent_id)
    if suite_id:
        query = query.where(EvaluationRun.test_suite_id == suite_id)
    result = await db.execute(query.order_by(EvaluationRun.created_at.desc()))
    return list(result.scalars().all())


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    result = await db.execute(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.tenant_id == UUID(tenant_id),
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@router.get("/runs/{run_id}/results")
async def get_run_results(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    results = await EvaluationService.get_run_results(db, run_id)
    return {"results": results}


# --- Comparison ---

class CompareRequest(BaseModel):
    run_ids: List[UUID]


@router.post("/compare")
async def compare_runs(
    body: CompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if len(body.run_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")
    return await EvaluationService.compare_runs(db, body.run_ids)
