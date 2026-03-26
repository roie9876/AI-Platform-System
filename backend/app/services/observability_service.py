import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.repositories.observability_repo import ExecutionLogRepository
from app.repositories.config_repo import ModelPricingRepository, CostAlertRepository
from app.repositories.agent_repo import AgentRepository

logger = logging.getLogger(__name__)

TIME_RANGE_MAP = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_log_repo = ExecutionLogRepository()
_pricing_repo = ModelPricingRepository()
_alert_repo = CostAlertRepository()
_agent_repo = AgentRepository()


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-format timestamp string to datetime."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _percentile(sorted_values: List[float], pct: float) -> float:
    """Compute percentile from a sorted list of values."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    k = (n - 1) * pct
    f = int(k)
    c = f + 1 if f + 1 < n else f
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])


def _compute_cost(log: dict, pricing_map: Dict[str, dict]) -> float:
    """Compute estimated cost of an execution log using pricing map."""
    tc = log.get("token_count") or {}
    ss = log.get("state_snapshot") or {}
    model = ss.get("model_name", "")
    pricing = pricing_map.get(model)
    if not pricing:
        return 0.0
    input_tokens = int(tc.get("input_tokens") or 0)
    output_tokens = int(tc.get("output_tokens") or 0)
    return (
        (input_tokens / 1000.0) * float(pricing.get("input_price_per_1k", 0))
        + (output_tokens / 1000.0) * float(pricing.get("output_price_per_1k", 0))
    )


async def _load_pricing_map(tenant_id: str) -> Dict[str, dict]:
    """Load active model pricing into a dict keyed by model_name."""
    all_pricing = await _pricing_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.is_active = true AND (c.tenant_id = @tid OR NOT IS_DEFINED(c.tenant_id))",
        [{"name": "@tid", "value": tenant_id}],
    )
    pmap: Dict[str, dict] = {}
    for p in all_pricing:
        name = p.get("model_name", "")
        if name:
            pmap[name] = p
    return pmap


class ObservabilityService:
    """Provides aggregation queries for observability dashboard.
    Uses Cosmos DB repos + client-side aggregation (no cross-container JOINs)."""

    @staticmethod
    async def get_dashboard_summary(
        tenant_id: str,
        time_range: str = "7d",
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta
        since_iso = since.isoformat()

        # Build query — execution_logs should have tenant_id denormalized
        conditions = "c.tenant_id = @tid AND c.event_type = 'model_response' AND c.created_at >= @since"
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@since", "value": since_iso},
        ]
        if agent_id:
            conditions += " AND c.agent_id = @aid"
            params.append({"name": "@aid", "value": agent_id})

        logs = await _log_repo.query(
            tenant_id,
            f"SELECT * FROM c WHERE {conditions}",
            params,
        )

        if not logs:
            return {
                "total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0,
                "total_tokens": 0, "total_cost": 0, "avg_latency_ms": 0,
                "p50_latency_ms": 0, "p95_latency_ms": 0,
                "success_count": 0, "error_count": 0,
                "requests_per_minute": 0,
            }

        pricing_map = await _load_pricing_map(tenant_id)

        total_input = 0
        total_output = 0
        latencies: List[float] = []
        success_count = 0
        error_count = 0
        total_cost = 0.0

        for log in logs:
            tc = log.get("token_count") or {}
            total_input += int(tc.get("input_tokens") or 0)
            total_output += int(tc.get("output_tokens") or 0)
            dur = log.get("duration_ms")
            if dur is not None:
                latencies.append(float(dur))
            if log.get("event_type") == "error":
                error_count += 1
            else:
                success_count += 1
            total_cost += _compute_cost(log, pricing_map)

        latencies.sort()
        total_requests = len(logs)
        minutes = delta.total_seconds() / 60

        return {
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": round(total_cost, 6),
            "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 1),
            "p50_latency_ms": round(_percentile(latencies, 0.5), 1),
            "p95_latency_ms": round(_percentile(latencies, 0.95), 1),
            "success_count": success_count,
            "error_count": error_count,
            "requests_per_minute": round(total_requests / max(minutes, 1), 3),
        }

    @staticmethod
    async def get_token_usage_over_time(
        tenant_id: str,
        time_range: str = "7d",
        granularity: str = "1h",
        agent_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta
        since_iso = since.isoformat()

        conditions = "c.tenant_id = @tid AND c.event_type = 'model_response' AND c.created_at >= @since"
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@since", "value": since_iso},
        ]
        if agent_id:
            conditions += " AND c.agent_id = @aid"
            params.append({"name": "@aid", "value": agent_id})
        if model_name:
            conditions += " AND c.state_snapshot.model_name = @mn"
            params.append({"name": "@mn", "value": model_name})

        logs = await _log_repo.query(
            tenant_id, f"SELECT * FROM c WHERE {conditions}", params,
        )

        # Group by hour bucket client-side
        granularity_hours = {"1h": 1, "6h": 6, "1d": 24}.get(granularity, 1)
        buckets: Dict[str, Dict[str, int]] = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0})

        for log in logs:
            created = _parse_iso(log.get("created_at"))
            if not created:
                continue
            # Truncate to hour, then to granularity bucket
            truncated = created.replace(minute=0, second=0, microsecond=0)
            bucket_hour = truncated.hour - (truncated.hour % granularity_hours)
            bucket_time = truncated.replace(hour=bucket_hour)
            key = bucket_time.isoformat()
            tc = log.get("token_count") or {}
            buckets[key]["input_tokens"] += int(tc.get("input_tokens") or 0)
            buckets[key]["output_tokens"] += int(tc.get("output_tokens") or 0)

        result = []
        for time_key in sorted(buckets.keys()):
            b = buckets[time_key]
            result.append({
                "time": time_key,
                "input_tokens": b["input_tokens"],
                "output_tokens": b["output_tokens"],
                "total_tokens": b["input_tokens"] + b["output_tokens"],
            })
        return result

    @staticmethod
    async def get_cost_breakdown(
        tenant_id: str,
        time_range: str = "7d",
        group_by: str = "agent",
    ) -> List[Dict[str, Any]]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta
        since_iso = since.isoformat()

        logs = await _log_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.event_type = 'model_response' AND c.created_at >= @since",
            [{"name": "@tid", "value": tenant_id}, {"name": "@since", "value": since_iso}],
        )

        pricing_map = await _load_pricing_map(tenant_id)

        # Aggregate by group key
        groups: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total_tokens": 0, "total_cost": 0.0, "request_count": 0, "name": "Unknown"}
        )

        if group_by == "model":
            for log in logs:
                model = (log.get("state_snapshot") or {}).get("model_name", "Unknown")
                tc = log.get("token_count") or {}
                tokens = int(tc.get("input_tokens") or 0) + int(tc.get("output_tokens") or 0)
                groups[model]["total_tokens"] += tokens
                groups[model]["total_cost"] += _compute_cost(log, pricing_map)
                groups[model]["request_count"] += 1
                groups[model]["name"] = model
        else:
            # Group by agent — need agent names
            agent_ids_seen: set = set()
            for log in logs:
                aid = log.get("agent_id", "Unknown")
                agent_ids_seen.add(aid)
                tc = log.get("token_count") or {}
                tokens = int(tc.get("input_tokens") or 0) + int(tc.get("output_tokens") or 0)
                groups[aid]["total_tokens"] += tokens
                groups[aid]["total_cost"] += _compute_cost(log, pricing_map)
                groups[aid]["request_count"] += 1

            # Resolve agent names
            for aid in agent_ids_seen:
                try:
                    agent = await _agent_repo.get(tenant_id, aid)
                    groups[aid]["name"] = agent.get("name", "Unknown") if agent else "Unknown"
                except Exception:
                    groups[aid]["name"] = "Unknown"

        result = [
            {
                "name": g["name"],
                "total_tokens": g["total_tokens"],
                "total_cost": round(g["total_cost"], 6),
                "request_count": g["request_count"],
            }
            for g in groups.values()
        ]
        result.sort(key=lambda x: x["total_cost"], reverse=True)
        return result

    @staticmethod
    async def get_top_agents(
        tenant_id: str,
        time_range: str = "7d",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
        since = datetime.now(timezone.utc) - delta
        since_iso = since.isoformat()

        logs = await _log_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.event_type = 'model_response' AND c.created_at >= @since",
            [{"name": "@tid", "value": tenant_id}, {"name": "@since", "value": since_iso}],
        )

        pricing_map = await _load_pricing_map(tenant_id)

        agent_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total_tokens": 0, "total_cost": 0.0, "request_count": 0}
        )

        for log in logs:
            aid = log.get("agent_id", "")
            if not aid:
                continue
            tc = log.get("token_count") or {}
            tokens = int(tc.get("input_tokens") or 0) + int(tc.get("output_tokens") or 0)
            agent_stats[aid]["total_tokens"] += tokens
            agent_stats[aid]["total_cost"] += _compute_cost(log, pricing_map)
            agent_stats[aid]["request_count"] += 1

        # Resolve agent names
        result = []
        for aid, stats in agent_stats.items():
            try:
                agent = await _agent_repo.get(tenant_id, aid)
                name = agent.get("name", "Unknown") if agent else "Unknown"
            except Exception:
                name = "Unknown"
            result.append({
                "agent_id": aid,
                "agent_name": name,
                "total_tokens": stats["total_tokens"],
                "total_cost": round(stats["total_cost"], 6),
                "request_count": stats["request_count"],
            })

        result.sort(key=lambda x: x["total_tokens"], reverse=True)
        return result[:limit]

    @staticmethod
    async def check_cost_alerts(tenant_id: str) -> List[Dict[str, Any]]:
        alerts = await _alert_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.is_active = true",
            [{"name": "@tid", "value": tenant_id}],
        )
        triggered: List[Dict[str, Any]] = []

        pricing_map = await _load_pricing_map(tenant_id)

        for alert in alerts:
            period_map = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}
            delta = period_map.get(alert.get("period", "monthly"), timedelta(days=30))
            since = datetime.now(timezone.utc) - delta
            since_iso = since.isoformat()

            # Skip if triggered recently (within 1 hour)
            last_triggered = _parse_iso(alert.get("last_triggered_at"))
            if last_triggered and (datetime.now(timezone.utc) - last_triggered) < timedelta(hours=1):
                continue

            logs = await _log_repo.query(
                tenant_id,
                "SELECT * FROM c WHERE c.tenant_id = @tid AND c.event_type = 'model_response' AND c.created_at >= @since",
                [{"name": "@tid", "value": tenant_id}, {"name": "@since", "value": since_iso}],
            )

            current_cost = sum(_compute_cost(log, pricing_map) for log in logs)

            threshold = float(alert.get("threshold_amount", 0))
            if current_cost >= threshold:
                alert["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
                await _alert_repo.update(tenant_id, alert["id"], alert)
                triggered.append({
                    "alert_id": alert["id"],
                    "name": alert.get("name", ""),
                    "alert_type": alert.get("alert_type", ""),
                    "threshold_amount": threshold,
                    "current_amount": round(current_cost, 4),
                    "period": alert.get("period", ""),
                    "scope_type": alert.get("scope_type", ""),
                })

        return triggered

    @staticmethod
    async def get_execution_logs(
        tenant_id: str,
        agent_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        time_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        conditions = "c.tenant_id = @tid"
        params = [{"name": "@tid", "value": tenant_id}]

        if agent_id:
            conditions += " AND c.agent_id = @aid"
            params.append({"name": "@aid", "value": agent_id})
        if time_range:
            delta = TIME_RANGE_MAP.get(time_range, timedelta(days=7))
            since = datetime.now(timezone.utc) - delta
            conditions += " AND c.created_at >= @since"
            params.append({"name": "@since", "value": since.isoformat()})

        # Get total count
        count_result = await _log_repo.query(
            tenant_id, f"SELECT VALUE COUNT(1) FROM c WHERE {conditions}", params,
        )
        total = count_result[0] if count_result else 0

        # Get paginated logs
        logs = await _log_repo.query(
            tenant_id,
            f"SELECT * FROM c WHERE {conditions} ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit",
            params + [{"name": "@offset", "value": offset}, {"name": "@limit", "value": limit}],
        )

        pricing_map = await _load_pricing_map(tenant_id)

        # Resolve agent names for unique agent_ids
        agent_ids = set(log.get("agent_id", "") for log in logs if log.get("agent_id"))
        agent_name_map: Dict[str, str] = {}
        for aid in agent_ids:
            try:
                agent = await _agent_repo.get(tenant_id, aid)
                agent_name_map[aid] = agent.get("name", "Unknown") if agent else "Unknown"
            except Exception:
                agent_name_map[aid] = "Unknown"

        return {
            "logs": [
                {
                    "id": log["id"],
                    "thread_id": log.get("thread_id", ""),
                    "event_type": log.get("event_type", ""),
                    "duration_ms": log.get("duration_ms"),
                    "token_count": log.get("token_count"),
                    "model_name": (log.get("state_snapshot") or {}).get("model_name"),
                    "tool_calls": (log.get("state_snapshot") or {}).get("tool_calls", []),
                    "estimated_cost": round(_compute_cost(log, pricing_map), 6),
                    "state_snapshot": log.get("state_snapshot"),
                    "agent_name": agent_name_map.get(log.get("agent_id", ""), "Unknown"),
                    "created_at": log.get("created_at"),
                }
                for log in logs
            ],
            "total": total,
        }
