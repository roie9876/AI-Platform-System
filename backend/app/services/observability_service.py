import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import func, select, text, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution_log import ExecutionLog
from app.models.cost_config import ModelPricing, CostAlert
from app.models.thread import Thread

logger = logging.getLogger(__name__)

TIME_RANGE_MAP = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


class ObservabilityService:
    """Provides aggregation queries for observability dashboard."""

    @staticmethod
    async def get_dashboard_summary(
        db: AsyncSession,
        tenant_id: UUID,
        time_range: str = "7d",
        agent_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta

        query = (
            select(
                func.count(ExecutionLog.id).label("total_requests"),
                func.coalesce(
                    func.sum(
                        func.cast(ExecutionLog.token_count["input_tokens"].astext, type_=func.cast.type if False else None)
                    ), 0
                ).label("total_input_tokens"),
                func.avg(ExecutionLog.duration_ms).label("avg_latency_ms"),
            )
            .join(Thread, Thread.id == ExecutionLog.thread_id)
            .where(
                Thread.tenant_id == tenant_id,
                ExecutionLog.event_type == "model_response",
                ExecutionLog.created_at >= since,
            )
        )
        if agent_id:
            query = query.where(Thread.agent_id == agent_id)

        # Use raw SQL for JSONB aggregation which is easier with PostgreSQL
        raw_sql = text("""
            SELECT
                COUNT(el.id) AS total_requests,
                COALESCE(SUM(CAST(el.token_count->>'input_tokens' AS INTEGER)), 0) AS total_input_tokens,
                COALESCE(SUM(CAST(el.token_count->>'output_tokens' AS INTEGER)), 0) AS total_output_tokens,
                COALESCE(AVG(el.duration_ms), 0) AS avg_latency_ms,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY el.duration_ms), 0) AS p50_latency_ms,
                COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY el.duration_ms), 0) AS p95_latency_ms,
                COUNT(CASE WHEN el.event_type != 'error' THEN 1 END) AS success_count,
                COUNT(CASE WHEN el.event_type = 'error' THEN 1 END) AS error_count
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            WHERE t.tenant_id = :tenant_id
              AND el.event_type = 'model_response'
              AND el.created_at >= :since
        """ + (" AND t.agent_id = :agent_id" if agent_id else ""))

        params: Dict[str, Any] = {"tenant_id": str(tenant_id), "since": since}
        if agent_id:
            params["agent_id"] = str(agent_id)

        result = await db.execute(raw_sql, params)
        row = result.fetchone()

        if not row:
            return {
                "total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0,
                "total_tokens": 0, "total_cost": 0, "avg_latency_ms": 0,
                "p50_latency_ms": 0, "p95_latency_ms": 0,
                "success_count": 0, "error_count": 0,
                "requests_per_minute": 0,
            }

        total_input = int(row.total_input_tokens or 0)
        total_output = int(row.total_output_tokens or 0)
        total_requests = int(row.total_requests or 0)
        minutes = delta.total_seconds() / 60

        # Calculate total cost via model pricing lookup
        cost_sql = text("""
            SELECT COALESCE(SUM(
                (CAST(el.token_count->>'input_tokens' AS FLOAT) / 1000.0 * mp.input_price_per_1k) +
                (CAST(el.token_count->>'output_tokens' AS FLOAT) / 1000.0 * mp.output_price_per_1k)
            ), 0) AS total_cost
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            LEFT JOIN model_pricing mp ON mp.model_name = el.state_snapshot->>'model_name'
                AND mp.is_active = true AND (mp.tenant_id IS NULL OR mp.tenant_id = :tenant_id)
            WHERE t.tenant_id = :tenant_id
              AND el.event_type = 'model_response'
              AND el.created_at >= :since
        """ + (" AND t.agent_id = :agent_id" if agent_id else ""))

        cost_result = await db.execute(cost_sql, params)
        total_cost = float((cost_result.scalar() or 0))

        return {
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": round(total_cost, 6),
            "avg_latency_ms": round(float(row.avg_latency_ms or 0), 1),
            "p50_latency_ms": round(float(row.p50_latency_ms or 0), 1),
            "p95_latency_ms": round(float(row.p95_latency_ms or 0), 1),
            "success_count": int(row.success_count or 0),
            "error_count": int(row.error_count or 0),
            "requests_per_minute": round(total_requests / max(minutes, 1), 3),
        }

    @staticmethod
    async def get_token_usage_over_time(
        db: AsyncSession,
        tenant_id: UUID,
        time_range: str = "7d",
        granularity: str = "1h",
        agent_id: Optional[UUID] = None,
        model_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta

        interval_map = {"1h": "1 hour", "6h": "6 hours", "1d": "1 day"}
        interval = interval_map.get(granularity, "1 hour")

        sql = text(f"""
            SELECT
                date_trunc('hour', el.created_at) AS time_bucket,
                COALESCE(SUM(CAST(el.token_count->>'input_tokens' AS INTEGER)), 0) AS input_tokens,
                COALESCE(SUM(CAST(el.token_count->>'output_tokens' AS INTEGER)), 0) AS output_tokens
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            WHERE t.tenant_id = :tenant_id
              AND el.event_type = 'model_response'
              AND el.created_at >= :since
              {"AND t.agent_id = :agent_id" if agent_id else ""}
              {"AND el.state_snapshot->>'model_name' = :model_name" if model_name else ""}
            GROUP BY time_bucket
            ORDER BY time_bucket
        """)

        params: Dict[str, Any] = {"tenant_id": str(tenant_id), "since": since}
        if agent_id:
            params["agent_id"] = str(agent_id)
        if model_name:
            params["model_name"] = model_name

        result = await db.execute(sql, params)
        return [
            {
                "time": row.time_bucket.isoformat(),
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.input_tokens) + int(row.output_tokens),
            }
            for row in result.fetchall()
        ]

    @staticmethod
    async def get_cost_breakdown(
        db: AsyncSession,
        tenant_id: UUID,
        time_range: str = "7d",
        group_by: str = "agent",
    ) -> List[Dict[str, Any]]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta

        if group_by == "model":
            group_col = "el.state_snapshot->>'model_name'"
            name_col = "el.state_snapshot->>'model_name'"
        else:  # agent
            group_col = "t.agent_id"
            name_col = "a.name"

        sql = text(f"""
            SELECT
                {name_col} AS name,
                COALESCE(SUM(CAST(el.token_count->>'input_tokens' AS INTEGER) + CAST(el.token_count->>'output_tokens' AS INTEGER)), 0) AS total_tokens,
                COALESCE(SUM(
                    (CAST(el.token_count->>'input_tokens' AS FLOAT) / 1000.0 * COALESCE(mp.input_price_per_1k, 0)) +
                    (CAST(el.token_count->>'output_tokens' AS FLOAT) / 1000.0 * COALESCE(mp.output_price_per_1k, 0))
                ), 0) AS total_cost,
                COUNT(el.id) AS request_count
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            {"JOIN agents a ON a.id = t.agent_id" if group_by == "agent" else ""}
            LEFT JOIN model_pricing mp ON mp.model_name = el.state_snapshot->>'model_name'
                AND mp.is_active = true AND (mp.tenant_id IS NULL OR mp.tenant_id = :tenant_id)
            WHERE t.tenant_id = :tenant_id
              AND el.event_type = 'model_response'
              AND el.created_at >= :since
            GROUP BY {group_col}{", " + name_col if group_col != name_col else ""}
            ORDER BY total_cost DESC
        """)

        result = await db.execute(sql, {"tenant_id": str(tenant_id), "since": since})
        return [
            {
                "name": row.name or "Unknown",
                "total_tokens": int(row.total_tokens),
                "total_cost": round(float(row.total_cost), 6),
                "request_count": int(row.request_count),
            }
            for row in result.fetchall()
        ]

    @staticmethod
    async def get_top_agents(
        db: AsyncSession,
        tenant_id: UUID,
        time_range: str = "7d",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta

        sql = text("""
            SELECT
                t.agent_id,
                a.name AS agent_name,
                COALESCE(SUM(CAST(el.token_count->>'input_tokens' AS INTEGER) + CAST(el.token_count->>'output_tokens' AS INTEGER)), 0) AS total_tokens,
                COALESCE(SUM(
                    (CAST(el.token_count->>'input_tokens' AS FLOAT) / 1000.0 * COALESCE(mp.input_price_per_1k, 0)) +
                    (CAST(el.token_count->>'output_tokens' AS FLOAT) / 1000.0 * COALESCE(mp.output_price_per_1k, 0))
                ), 0) AS total_cost,
                COUNT(el.id) AS request_count
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            JOIN agents a ON a.id = t.agent_id
            LEFT JOIN model_pricing mp ON mp.model_name = el.state_snapshot->>'model_name'
                AND mp.is_active = true AND (mp.tenant_id IS NULL OR mp.tenant_id = :tenant_id)
            WHERE t.tenant_id = :tenant_id
              AND el.event_type = 'model_response'
              AND el.created_at >= :since
            GROUP BY t.agent_id, a.name
            ORDER BY total_tokens DESC
            LIMIT :limit
        """)

        result = await db.execute(sql, {"tenant_id": str(tenant_id), "since": since, "limit": limit})
        return [
            {
                "agent_id": str(row.agent_id),
                "agent_name": row.agent_name,
                "total_tokens": int(row.total_tokens),
                "total_cost": round(float(row.total_cost), 6),
                "request_count": int(row.request_count),
            }
            for row in result.fetchall()
        ]

    @staticmethod
    async def check_cost_alerts(
        db: AsyncSession, tenant_id: UUID
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(CostAlert).where(
                CostAlert.tenant_id == tenant_id,
                CostAlert.is_active == True,
            )
        )
        alerts = list(result.scalars().all())
        triggered: List[Dict[str, Any]] = []

        for alert in alerts:
            period_map = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}
            delta = period_map.get(alert.period, timedelta(days=30))
            since = datetime.now(timezone.utc) - delta

            # Skip if triggered recently (within 1 hour)
            if alert.last_triggered_at:
                if datetime.now(timezone.utc) - alert.last_triggered_at < timedelta(hours=1):
                    continue

            sql = text("""
                SELECT COALESCE(SUM(
                    (CAST(el.token_count->>'input_tokens' AS FLOAT) / 1000.0 * COALESCE(mp.input_price_per_1k, 0)) +
                    (CAST(el.token_count->>'output_tokens' AS FLOAT) / 1000.0 * COALESCE(mp.output_price_per_1k, 0))
                ), 0) AS total_cost
                FROM execution_logs el
                JOIN threads t ON t.id = el.thread_id
                LEFT JOIN model_pricing mp ON mp.model_name = el.state_snapshot->>'model_name'
                    AND mp.is_active = true AND (mp.tenant_id IS NULL OR mp.tenant_id = :tenant_id)
                WHERE t.tenant_id = :tenant_id
                  AND el.event_type = 'model_response'
                  AND el.created_at >= :since
            """)
            cost_result = await db.execute(sql, {"tenant_id": str(tenant_id), "since": since})
            current_cost = float(cost_result.scalar() or 0)

            if current_cost >= alert.threshold_amount:
                alert.last_triggered_at = datetime.now(timezone.utc)
                triggered.append({
                    "alert_id": str(alert.id),
                    "name": alert.name,
                    "alert_type": alert.alert_type,
                    "threshold_amount": alert.threshold_amount,
                    "current_amount": round(current_cost, 4),
                    "period": alert.period,
                    "scope_type": alert.scope_type,
                })

        if triggered:
            await db.commit()

        return triggered

    @staticmethod
    async def get_execution_logs(
        db: AsyncSession,
        tenant_id: UUID,
        agent_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
        time_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        sql_conditions = "WHERE t.tenant_id = :tenant_id"
        params: Dict[str, Any] = {"tenant_id": str(tenant_id), "limit": limit, "offset": offset}
        if agent_id:
            sql_conditions += " AND t.agent_id = :agent_id"
            params["agent_id"] = str(agent_id)
        if time_range:
            delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
            since = datetime.now(timezone.utc) - delta
            sql_conditions += " AND el.created_at >= :since"
            params["since"] = since

        count_sql = text(f"""
            SELECT COUNT(el.id)
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            {sql_conditions}
        """)
        total = (await db.execute(count_sql, params)).scalar() or 0

        sql = text(f"""
            SELECT
                el.id, el.thread_id, el.event_type, el.duration_ms, el.token_count,
                el.state_snapshot, el.created_at,
                el.state_snapshot->>'model_name' AS model_name,
                el.state_snapshot->'tool_calls' AS tool_calls,
                a.name AS agent_name,
                COALESCE(
                    (CAST(el.token_count->>'input_tokens' AS FLOAT) / 1000.0 * mp.input_price_per_1k) +
                    (CAST(el.token_count->>'output_tokens' AS FLOAT) / 1000.0 * mp.output_price_per_1k),
                    0
                ) AS estimated_cost
            FROM execution_logs el
            JOIN threads t ON t.id = el.thread_id
            LEFT JOIN agents a ON a.id = t.agent_id
            LEFT JOIN model_pricing mp ON mp.model_name = el.state_snapshot->>'model_name'
                AND mp.is_active = true
                AND (mp.tenant_id IS NULL OR mp.tenant_id = :tenant_id)
            {sql_conditions}
            ORDER BY el.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await db.execute(sql, params)
        rows = result.fetchall()

        return {
            "logs": [
                {
                    "id": str(row.id),
                    "thread_id": str(row.thread_id),
                    "event_type": row.event_type,
                    "duration_ms": row.duration_ms,
                    "token_count": row.token_count,
                    "model_name": row.model_name,
                    "tool_calls": row.tool_calls or [],
                    "estimated_cost": round(float(row.estimated_cost or 0), 6),
                    "state_snapshot": row.state_snapshot,
                    "agent_name": row.agent_name,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ],
            "total": total,
        }
