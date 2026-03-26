"""Validation tests for PostgreSQL → Cosmos DB migration script — DATA-05."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from unittest.mock import MagicMock

import pytest

from scripts.migrate_to_cosmos import serialize_value, serialize_row, MODEL_CONTAINER_MAP


class TestSerializeValue:
    """Tests for serialize_value function."""

    def test_uuid_to_str(self):
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert serialize_value(u) == "12345678-1234-5678-1234-567812345678"

    def test_datetime_to_iso(self):
        dt = datetime(2026, 3, 26, 12, 0, 0)
        result = serialize_value(dt)
        assert result == "2026-03-26T12:00:00"

    def test_date_to_iso(self):
        d = date(2026, 3, 26)
        assert serialize_value(d) == "2026-03-26"

    def test_none_stays_none(self):
        assert serialize_value(None) is None

    def test_dict_preserved(self):
        val = {"key": "value"}
        assert serialize_value(val) == {"key": "value"}

    def test_list_preserved(self):
        val = [1, 2, 3]
        assert serialize_value(val) == [1, 2, 3]

    def test_primitive_types_preserved(self):
        assert serialize_value(42) == 42
        assert serialize_value(3.14) == 3.14
        assert serialize_value(True) is True
        assert serialize_value("hello") == "hello"


class TestSerializeRow:
    """Tests for serialize_row function."""

    def test_serializes_uuid_id_to_str(self):
        row = MagicMock()
        row.__class__ = type("FakeModel", (), {})
        mapper = MagicMock()
        col_id = MagicMock()
        col_id.key = "id"
        col_name = MagicMock()
        col_name.key = "name"
        mapper.columns = [col_id, col_name]
        row.__class__.__mapper__ = mapper

        test_uuid = uuid.UUID("abcdef01-2345-6789-abcd-ef0123456789")
        row.id = test_uuid
        row.name = "test-agent"

        doc = serialize_row(row)
        assert doc["id"] == str(test_uuid)
        assert doc["name"] == "test-agent"

    def test_serializes_datetime_fields(self):
        row = MagicMock()
        row.__class__ = type("FakeModel", (), {})
        mapper = MagicMock()
        col_id = MagicMock()
        col_id.key = "id"
        col_ts = MagicMock()
        col_ts.key = "created_at"
        mapper.columns = [col_id, col_ts]
        row.__class__.__mapper__ = mapper

        row.id = "simple-id"
        row.created_at = datetime(2026, 1, 15, 10, 30)

        doc = serialize_row(row)
        assert doc["created_at"] == "2026-01-15T10:30:00"


class TestModelMappings:
    """Verify all model→container mappings (DATA-05)."""

    def test_mapping_count(self):
        assert len(MODEL_CONTAINER_MAP) == 35

    def test_all_container_names_are_strings(self):
        for model_cls, container_name in MODEL_CONTAINER_MAP:
            assert isinstance(container_name, str), f"{model_cls} has non-string container name"
            assert len(container_name) > 0, f"{model_cls} has empty container name"

    def test_known_critical_mappings_exist(self):
        container_names = {name for _, name in MODEL_CONTAINER_MAP}
        critical = {"tenants", "users", "agents", "tools", "data_sources", "mcp_servers", "model_endpoints"}
        for name in critical:
            assert name in container_names, f"Missing critical container mapping: {name}"
