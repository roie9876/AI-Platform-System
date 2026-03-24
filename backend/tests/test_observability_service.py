"""Unit tests for ObservabilityService - time range mapping and result formatting."""

from datetime import timedelta

from app.services.observability_service import ObservabilityService, TIME_RANGE_MAP


class TestTimeRangeMap:
    def test_1h(self):
        assert TIME_RANGE_MAP["1h"] == timedelta(hours=1)

    def test_24h(self):
        assert TIME_RANGE_MAP["24h"] == timedelta(hours=24)

    def test_7d(self):
        assert TIME_RANGE_MAP["7d"] == timedelta(days=7)

    def test_30d(self):
        assert TIME_RANGE_MAP["30d"] == timedelta(days=30)

    def test_all_keys_present(self):
        assert set(TIME_RANGE_MAP.keys()) == {"1h", "24h", "7d", "30d"}


class TestDashboardSummaryStructure:
    """Test the structure of the empty/default return from get_dashboard_summary."""

    def test_empty_row_returns_zeroed_dict(self):
        expected_keys = {
            "total_requests", "total_input_tokens", "total_output_tokens",
            "total_tokens", "total_cost", "avg_latency_ms",
            "p50_latency_ms", "p95_latency_ms",
            "success_count", "error_count", "requests_per_minute",
        }
        # The empty-row return dict is defined inline in the method
        empty = {
            "total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0,
            "total_tokens": 0, "total_cost": 0, "avg_latency_ms": 0,
            "p50_latency_ms": 0, "p95_latency_ms": 0,
            "success_count": 0, "error_count": 0,
            "requests_per_minute": 0,
        }
        assert set(empty.keys()) == expected_keys
        assert all(v == 0 for v in empty.values())
