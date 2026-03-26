import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from app.repositories.agent_repo import AgentRepository
from app.repositories.evaluation_repo import (
    TestSuiteRepository,
    TestCaseRepository,
    EvaluationRunRepository,
    EvaluationResultRepository,
)
from app.repositories.thread_repo import ThreadRepository, ThreadMessageRepository

logger = logging.getLogger(__name__)

_agent_repo = AgentRepository()
_suite_repo = TestSuiteRepository()
_case_repo = TestCaseRepository()
_run_repo = EvaluationRunRepository()
_result_repo = EvaluationResultRepository()
_thread_repo = ThreadRepository()
_message_repo = ThreadMessageRepository()


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Simple word-overlap Jaccard similarity."""
    if not text_a or not text_b:
        return 0.0
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _keyword_match_rate(actual: str, keywords: List[str]) -> float:
    """Fraction of expected keywords found in actual output."""
    if not keywords:
        return 1.0
    actual_lower = actual.lower()
    matched = sum(1 for kw in keywords if kw.lower() in actual_lower)
    return matched / len(keywords)


class EvaluationService:
    """Manages test suites and runs evaluations against agents."""

    @staticmethod
    async def run_evaluation(
        test_suite_id: str,
        tenant_id: str,
    ) -> str:
        # Load test suite
        suite = await _suite_repo.get(tenant_id, test_suite_id)
        if not suite:
            raise ValueError("Test suite not found")

        # Load agent
        agent = await _agent_repo.get(tenant_id, suite["agent_id"])
        if not agent:
            raise ValueError("Agent not found for test suite")

        # Load test cases
        cases = await _case_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.test_suite_id = @sid ORDER BY c.order_index",
            [{"name": "@sid", "value": test_suite_id}],
        )
        if not cases:
            raise ValueError("Test suite has no test cases")

        # Create evaluation run
        run_id = str(uuid4())
        run = {
            "id": run_id,
            "test_suite_id": test_suite_id,
            "agent_id": suite["agent_id"],
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
        }
        await _run_repo.create(tenant_id, run)

        total_score = 0.0
        passed = 0
        failed = 0
        total_latency = 0.0

        # Import agent execution lazily to avoid circular deps
        from app.services.agent_execution import AgentExecutionService
        execution_service = AgentExecutionService()

        for case in cases:
            start_time = time.monotonic()
            try:
                # Create a temporary thread
                temp_thread_id = str(uuid4())
                temp_thread = {
                    "id": temp_thread_id,
                    "agent_id": suite["agent_id"],
                    "user_id": None,
                    "tenant_id": tenant_id,
                    "title": f"eval-{run_id}-{case['id']}",
                }
                await _thread_repo.create(tenant_id, temp_thread)

                # Execute agent (collect all SSE chunks into response)
                actual_output = ""
                async for chunk in execution_service.execute(
                    agent=agent,
                    user_message=case["input_message"],
                    tenant_id=tenant_id,
                    thread_id=temp_thread_id,
                ):
                    import json as _json
                    if chunk.startswith("data: "):
                        try:
                            data = _json.loads(chunk[6:].strip())
                            if "content" in data and data.get("content"):
                                actual_output += data["content"]
                        except _json.JSONDecodeError:
                            pass

                latency_ms = int((time.monotonic() - start_time) * 1000)

                # Compute metrics
                similarity = _jaccard_similarity(actual_output, case.get("expected_output")) if case.get("expected_output") else None
                kw_rate = _keyword_match_rate(actual_output, case.get("expected_keywords") or []) if case.get("expected_keywords") else None

                # Composite score
                scores = [s for s in [similarity, kw_rate] if s is not None]
                score = sum(scores) / len(scores) if scores else (1.0 if actual_output else 0.0)

                status = "passed" if score >= 0.5 else "failed"
                if status == "passed":
                    passed += 1
                else:
                    failed += 1
                total_score += score
                total_latency += latency_ms

                eval_result = {
                    "id": str(uuid4()),
                    "run_id": run_id,
                    "test_case_id": case["id"],
                    "actual_output": actual_output,
                    "score": round(score, 4),
                    "metrics": {
                        "similarity_score": round(similarity, 4) if similarity is not None else None,
                        "keyword_match_rate": round(kw_rate, 4) if kw_rate is not None else None,
                        "latency_ms": latency_ms,
                    },
                    "status": status,
                    "tenant_id": tenant_id,
                }
                await _result_repo.create(tenant_id, eval_result)

                # Clean up temp thread
                await _thread_repo.delete(tenant_id, temp_thread_id)

            except Exception as e:
                logger.error("Evaluation error for case %s: %s", case["id"], str(e))
                failed += 1
                eval_result = {
                    "id": str(uuid4()),
                    "run_id": run_id,
                    "test_case_id": case["id"],
                    "actual_output": None,
                    "score": 0.0,
                    "status": "error",
                    "error_message": str(e),
                    "tenant_id": tenant_id,
                }
                await _result_repo.create(tenant_id, eval_result)

        # Update run summary
        total_cases = len(cases)
        run["status"] = "completed"
        run["completed_at"] = datetime.now(timezone.utc).isoformat()
        run["summary"] = {
            "total_cases": total_cases,
            "passed": passed,
            "failed": failed,
            "avg_score": round(total_score / max(total_cases, 1), 4),
            "avg_latency_ms": round(total_latency / max(total_cases, 1), 1),
        }
        await _run_repo.update(tenant_id, run_id, run)

        return run_id

    @staticmethod
    async def compare_runs(
        run_ids: List[str], tenant_id: str,
    ) -> Dict[str, Any]:
        runs_data = []
        for run_id in run_ids:
            run = await _run_repo.get(tenant_id, run_id)
            if not run:
                continue
            runs_data.append({
                "run_id": run["id"],
                "config_version_id": run.get("config_version_id"),
                "status": run.get("status"),
                "summary": run.get("summary"),
                "started_at": run.get("started_at"),
                "completed_at": run.get("completed_at"),
            })

        # Per-case comparison
        per_case: Dict[str, Dict[str, Any]] = {}
        for run_id in run_ids:
            results = await _result_repo.query(
                tenant_id,
                "SELECT * FROM c WHERE c.run_id = @rid",
                [{"name": "@rid", "value": run_id}],
            )
            for result in results:
                case_id = result["test_case_id"]
                case = await _case_repo.get(tenant_id, case_id)
                if case_id not in per_case:
                    per_case[case_id] = {
                        "test_case_id": case_id,
                        "input_message": case["input_message"] if case else "",
                        "results_by_run": {},
                    }
                per_case[case_id]["results_by_run"][run_id] = {
                    "score": result.get("score"),
                    "status": result.get("status"),
                    "metrics": result.get("metrics"),
                }

        return {"runs": runs_data, "per_case": list(per_case.values())}

    @staticmethod
    async def get_run_results(
        run_id: str, tenant_id: str,
    ) -> List[Dict[str, Any]]:
        results = await _result_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.run_id = @rid",
            [{"name": "@rid", "value": run_id}],
        )
        output = []
        for result in results:
            case = await _case_repo.get(tenant_id, result["test_case_id"])
            output.append({
                "id": result["id"],
                "test_case_id": result["test_case_id"],
                "input_message": case["input_message"] if case else "",
                "expected_output": case.get("expected_output") if case else "",
                "actual_output": result.get("actual_output"),
                "score": result.get("score"),
                "metrics": result.get("metrics"),
                "status": result.get("status"),
                "error_message": result.get("error_message"),
            })
        return output
