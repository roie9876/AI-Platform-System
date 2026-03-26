from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.evaluation_repo import (
    TestSuiteRepository,
    TestCaseRepository,
    EvaluationRunRepository,
    EvaluationResultRepository,
)
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

suite_repo = TestSuiteRepository()
case_repo = TestCaseRepository()
run_repo = EvaluationRunRepository()
result_repo = EvaluationResultRepository()


# --- Test Suite CRUD ---

@router.get("/test-suites", response_model=list[TestSuiteResponse])
async def list_test_suites(
    agent_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if agent_id:
        suites = await suite_repo.list_by_agent(tenant_id, agent_id)
    else:
        suites = await suite_repo.list_all(tenant_id)
    return suites


@router.post("/test-suites", response_model=TestSuiteResponse, status_code=201)
async def create_test_suite(
    body: TestSuiteCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    suite_data = {
        "name": body.name,
        "description": body.description,
        "agent_id": str(body.agent_id) if body.agent_id else None,
    }
    suite = await suite_repo.create(tenant_id, suite_data)
    return suite


@router.get("/test-suites/{suite_id}", response_model=TestSuiteResponse)
async def get_test_suite(
    suite_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    suite = await suite_repo.get(tenant_id, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return suite


@router.put("/test-suites/{suite_id}", response_model=TestSuiteResponse)
async def update_test_suite(
    suite_id: str,
    body: TestSuiteCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    suite = await suite_repo.get(tenant_id, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    suite["name"] = body.name
    suite["description"] = body.description
    suite["agent_id"] = str(body.agent_id) if body.agent_id else None
    updated = await suite_repo.update(tenant_id, suite_id, suite)
    return updated


@router.delete("/test-suites/{suite_id}", status_code=204)
async def delete_test_suite(
    suite_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await suite_repo.delete(tenant_id, suite_id)


# --- Test Cases ---

@router.post("/test-suites/{suite_id}/cases", response_model=TestCaseResponse, status_code=201)
async def add_test_case(
    suite_id: str,
    body: TestCaseCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    suite = await suite_repo.get(tenant_id, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    case_data = {
        "test_suite_id": suite_id,
        "input_message": body.input_message,
        "expected_output": body.expected_output,
        "expected_keywords": body.expected_keywords,
        "metadata_": body.metadata_,
        "order_index": body.order_index,
    }
    case = await case_repo.create(tenant_id, case_data)
    return case


@router.put("/test-suites/{suite_id}/cases/{case_id}", response_model=TestCaseResponse)
async def update_test_case(
    suite_id: str,
    case_id: str,
    body: TestCaseCreate,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    case = await case_repo.get(tenant_id, case_id)
    if not case or case.get("test_suite_id") != suite_id:
        raise HTTPException(status_code=404, detail="Test case not found")
    case["input_message"] = body.input_message
    case["expected_output"] = body.expected_output
    case["expected_keywords"] = body.expected_keywords
    case["metadata_"] = body.metadata_
    case["order_index"] = body.order_index
    updated = await case_repo.update(tenant_id, case_id, case)
    return updated


@router.delete("/test-suites/{suite_id}/cases/{case_id}", status_code=204)
async def delete_test_case(
    suite_id: str,
    case_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    await case_repo.delete(tenant_id, case_id)


# --- Evaluation Runs ---

@router.post("/test-suites/{suite_id}/run", response_model=EvaluationRunResponse)
async def trigger_evaluation_run(
    suite_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    try:
        run_id = await EvaluationService.run_evaluation(suite_id, tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run = await run_repo.get(tenant_id, run_id)
    return run


@router.get("/runs", response_model=list[EvaluationRunResponse])
async def list_runs(
    agent_id: Optional[str] = None,
    suite_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if suite_id:
        runs = await run_repo.list_by_suite(tenant_id, suite_id)
    else:
        runs = await run_repo.list_all(tenant_id)
    if agent_id:
        runs = [r for r in runs if r.get("agent_id") == agent_id]
    return runs


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    run = await run_repo.get(tenant_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@router.get("/runs/{run_id}/results")
async def get_run_results(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    results = await EvaluationService.get_run_results(run_id, tenant_id)
    return {"results": results}


# --- Comparison ---

class CompareRequest(BaseModel):
    run_ids: List[str]


@router.post("/compare")
async def compare_runs(
    body: CompareRequest,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if len(body.run_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")
    return await EvaluationService.compare_runs(body.run_ids, tenant_id)
