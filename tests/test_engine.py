"""Testes do motor de extração."""

import os
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from dataspoc_pipe.config import (
    DestinationConfig,
    PipelineConfig,
    SourceConfig,
)
from dataspoc_pipe.engine import run_pipeline
from dataspoc_pipe.singer import json_schema_to_pyarrow, parse_message

MOCK_TAP = str(Path(__file__).parent / "mock_tap.py")


def test_parse_schema_message():
    line = '{"type": "SCHEMA", "stream": "users", "schema": {"properties": {"id": {"type": "integer"}}}, "key_properties": ["id"]}'
    msg = parse_message(line)
    assert msg.type == "SCHEMA"
    assert msg.stream == "users"


def test_parse_record_message():
    line = '{"type": "RECORD", "stream": "users", "record": {"id": 1, "name": "Ana"}}'
    msg = parse_message(line)
    assert msg.type == "RECORD"
    assert msg.record["name"] == "Ana"


def test_parse_state_message():
    line = '{"type": "STATE", "value": {"bookmarks": {"users": {"id": 3}}}}'
    msg = parse_message(line)
    assert msg.type == "STATE"
    assert msg.value["bookmarks"]["users"]["id"] == 3


def test_json_schema_to_pyarrow():
    schema = {
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "email": {"type": ["string", "null"]},
            "active": {"type": "boolean"},
        }
    }
    pa_schema = json_schema_to_pyarrow(schema)
    assert len(pa_schema) == 4
    assert pa_schema.field("id").type.equals("int64")
    assert pa_schema.field("name").type.equals("string")
    assert pa_schema.field("email").nullable is True
    assert pa_schema.field("active").type.equals("bool")


def test_json_schema_datetime():
    schema = {
        "properties": {
            "created_at": {"type": "string", "format": "date-time"},
            "birth_date": {"type": "string", "format": "date"},
        }
    }
    pa_schema = json_schema_to_pyarrow(schema)
    assert "timestamp" in str(pa_schema.field("created_at").type)
    assert "date" in str(pa_schema.field("birth_date").type)


def test_run_pipeline_with_mock_tap(tmp_path):
    config = PipelineConfig(
        name="test-pipeline",
        source=SourceConfig(
            tap=sys.executable,
            config={},  # Não usado pelo mock
        ),
        destination=DestinationConfig(
            bucket=f"file://{tmp_path}/lake",
            path="raw",
        ),
    )
    # Hack: usar python como tap executando o mock_tap.py
    # Reconfigurar o tap para usar python + mock_tap
    config.source.tap = f"{sys.executable} {MOCK_TAP}"

    result = run_pipeline(config)

    assert result.success, f"Pipeline falhou: {result.error}"
    assert "users" in result.streams
    assert result.streams["users"] == 3
    assert result.last_state is not None

    # Verificar que Parquet foi criado
    parquet_files = list(tmp_path.rglob("*.parquet"))
    assert len(parquet_files) == 1

    # Verificar conteúdo
    table = pq.read_table(parquet_files[0])
    assert table.num_rows == 3
    assert "id" in table.column_names
    assert "name" in table.column_names


def test_run_pipeline_nonexistent_tap(tmp_path):
    config = PipelineConfig(
        name="fail-test",
        source=SourceConfig(tap="tap-inexistente-xyz", config={}),
        destination=DestinationConfig(bucket=f"file://{tmp_path}/lake"),
    )
    result = run_pipeline(config)
    assert not result.success
    assert result.error is not None


def test_parquet_directory_convention(tmp_path):
    """Verifica que a convenção de diretórios está correta."""
    config = PipelineConfig(
        name="test",
        source=SourceConfig(tap=f"{sys.executable} {MOCK_TAP}", config={}),
        destination=DestinationConfig(
            bucket=f"file://{tmp_path}/lake",
            path="raw",
        ),
    )
    run_pipeline(config)

    # Full extraction (no incremental): raw/<source>/<table>/<file>.parquet
    # Incremental: raw/<source>/<table>/dt=YYYY-MM-DD/<file>.parquet
    parquet_files = list(tmp_path.rglob("*.parquet"))
    assert len(parquet_files) == 1

    path_str = str(parquet_files[0].relative_to(tmp_path / "lake"))
    parts = path_str.split(os.sep)
    assert parts[0] == "raw"         # base path
    assert "mock_tap" in parts[1]    # source (tap name sem "tap-")
    assert parts[2] == "users"       # stream name
    # No partitioning for full extraction (incremental=false by default)
    assert parts[3].endswith(".parquet")  # file directly in table dir
