import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.evaluation import TestSuite, TestCase, EvaluationRun, EvaluationResult
from app.models.thread import Thread
from app.models.thread_message import ThreadMessage

logger = logging.getLogger(__name__)


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
        db: AsyncSession,
        test_suite_id: UUID,
        tenant_id: UUID,
    ) -> UUID:
        # Load test suite
        suite_result = await db.execute(
            select(TestSuite).where(
                TestSuite.id == test_suite_id,
                TestSuite.tenant_id == tenant_id,
            )
        )
        suite = suite_result.scalar_one_or_none()
        if not suite:
            raise ValueError("Test suite not found")

        # Load agent
        agent_result = await db.execute(
            select(Agent).where(Agent.id == suite.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found for test suite")

        # Load test cases
        cases_result = await db.execute(
            select(TestCase)
            .where(TestCase.test_suite_id == test_suite_id)
            .order_by(TestCase.order_index)
        )
        cases = list(cases_result.scalars().all())
        if not cases:
            raise ValueError("Test suite has no test cases")

        # Create evaluation run
        run = EvaluationRun(
            test_suite_id=test_suite_id,
            agent_id=suite.agent_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            tenant_id=tenant_id,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        total_score = 0.0
        passed = 0
        failed = 0
        total_latency = 0.0
        total_input_tokens = 0
        total_output_tokens = 0

        # Import agent execution lazily to avoid circular deps
        from app.services.agent_execution import AgentExecutionService
        execution_service = AgentExecutionService()

        for case in cases:
            start_time = time.monotonic()
            try:
                # Create a temporary thread
                temp_thread = Thread(
                    agent_id=suite.agent_id,
                    user_id=None,
                    tenant_id=tenant_id,
                    title=f"eval-{run.id}-{case.id}",
                )
                db.add(temp_thread)
                await db.commit()
                await db.refresh(temp_thread)

                # Execute agent (collect all SSE chunks into response)
                actual_output = ""
                async for chunk in execution_service.execute(
                    agent=agent,
                    user_message=case.input_message,
                    db=db,
                    thread_id=temp_thread.id,
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
                similarity = _jaccard_similarity(actual_output, case.expected_output) if case.expected_output else None
                kw_rate = _keyword_match_rate(actual_output, case.expected_keywords or []) if case.expected_keywords else None

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

                eval_result = EvaluationResult(
                    run_id=run.id,
                    test_case_id=case.id,
                    actual_output=actual_output,
                    score=round(score, 4),
                    metrics={
                        "similarity_score": round(similarity, 4) if similarity is not None else None,
                        "keyword_match_rate": round(kw_rate, 4) if kw_rate is not None else None,
                        "latency_ms": latency_ms,
                        "input_tokens": 0,
                        "output_tokens": 0,
                    },
                    status=status,
                )
                db.add(eval_result)

                # Clean up temp thread
                await db.execute(
                    select(ThreadMessage).where(ThreadMessage.thread_id == temp_thread.id)
                )
                await db.delete(temp_thread)
                await db.commit()

            except Exception as e:
                logger.error("Evaluation error for case %s: %s", case.id, str(e))
                failed += 1
                eval_result = EvaluationResult(
                    run_id=run.id,
                    test_case_id=case.id,
                    actual_output=None,
                    score=0.0,
                    status="error",
                    error_message=str(e),
                )
                db.add(eval_result)
                await db.commit()

        # Update run summary
        total_cases = len(cases)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.summary = {
            "total_cases": total_cases,
            "passed": passed,
            "failed": failed,
            "avg_score": round(total_score / max(total_cases, 1), 4),
            "avg_latency_ms": round(total_latency / max(total_cases, 1), 1),
            "total_tokens": total_input_tokens + total_output_tokens,
        }
        await db.commit()

        return run.id

    @staticmethod
    async def compare_runs(
        db: AsyncSession, run_ids: List[UUID]
    ) -> Dict[str, Any]:
        runs_data = []
        for run_id in run_ids:
            run_result = await db.execute(
                select(EvaluationRun).where(EvaluationRun.id == run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run:
                continue
            runs_data.append({
                "run_id": str(run.id),
                "config_version_id": str(run.config_version_id) if run.config_version_id else None,
                "status": run.status,
                "summary": run.summary,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            })

        # Per-case comparison
        per_case: Dict[str, Dict[str, Any]] = {}
        for run_id in run_ids:
            results_result = await db.execute(
                select(EvaluationResult, TestCase)
                .join(TestCase, TestCase.id == EvaluationResult.test_case_id)
                .where(EvaluationResult.run_id == run_id)
            )
            for result, case in results_result.all():
                case_key = str(case.id)
                if case_key not in per_case:
                    per_case[case_key] = {
                        "test_case_id": case_key,
                        "input_message": case.input_message,
                        "results_by_run": {},
                    }
                per_case[case_key]["results_by_run"][str(run_id)] = {
                    "score": result.score,
                    "status": result.status,
                    "metrics": result.metrics,
                }

        return {"runs": runs_data, "per_case": list(per_case.values())}

    @staticmethod
    async def get_run_results(
        db: AsyncSession, run_id: UUID
    ) -> List[Dict[str, Any]]:
        results_result = await db.execute(
            select(EvaluationResult, TestCase)
            .join(TestCase, TestCase.id == EvaluationResult.test_case_id)
            .where(EvaluationResult.run_id == run_id)
        )
        return [
            {
                "id": str(result.id),
                "test_case_id": str(case.id),
                "input_message": case.input_message,
                "expected_output": case.expected_output,
                "actual_output": result.actual_output,
                "score": result.score,
                "metrics": result.metrics,
                "status": result.status,
                "error_message": result.error_message,
            }
            for result, case in results_result.all()
        ]
