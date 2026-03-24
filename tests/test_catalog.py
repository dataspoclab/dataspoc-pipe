"""Testes do catálogo (manifest) e observabilidade (logs)."""

from datetime import datetime, timezone

from dataspoc_pipe.catalog import (
    load_latest_log,
    load_manifest,
    save_execution_log,
    update_manifest,
)
from dataspoc_pipe.engine import ExtractionResult


def _make_result(pipeline="test", success=True, streams=None):
    return ExtractionResult(
        pipeline=pipeline,
        success=success,
        streams=streams or {"users": 100},
    )


def test_load_empty_manifest(tmp_path):
    m = load_manifest(f"file://{tmp_path}")
    assert m["version"] == "1.0"
    assert m["tables"] == {}


def test_update_manifest(tmp_path):
    bucket = f"file://{tmp_path}"
    result = _make_result(streams={"users": 50, "orders": 30})

    update_manifest(bucket, result, "postgres")
    m = load_manifest(bucket)

    assert "postgres/users" in m["tables"]
    assert "postgres/orders" in m["tables"]
    assert m["tables"]["postgres/users"]["stats"]["total_rows"] == 50
    assert m["tables"]["postgres/orders"]["stats"]["total_rows"] == 30


def test_manifest_accumulates(tmp_path):
    bucket = f"file://{tmp_path}"

    update_manifest(bucket, _make_result(streams={"users": 50}), "pg")
    update_manifest(bucket, _make_result(streams={"users": 30}), "pg")

    m = load_manifest(bucket)
    assert m["tables"]["pg/users"]["stats"]["total_rows"] == 80
    assert m["tables"]["pg/users"]["stats"]["extractions"] == 2


def test_save_and_load_log(tmp_path):
    bucket = f"file://{tmp_path}"
    result = _make_result()
    now = datetime.now(timezone.utc)

    save_execution_log(bucket, result, now, now)
    log = load_latest_log(bucket, "test")

    assert log is not None
    assert log["status"] == "success"
    assert log["total_records"] == 100


def test_load_log_nonexistent(tmp_path):
    log = load_latest_log(f"file://{tmp_path}", "nope")
    assert log is None


def test_failure_log(tmp_path):
    bucket = f"file://{tmp_path}"
    result = _make_result(success=False)
    result.error = "tap crashed"
    now = datetime.now(timezone.utc)

    save_execution_log(bucket, result, now, now)
    log = load_latest_log(bucket, "test")

    assert log["status"] == "failure"
    assert log["error"] == "tap crashed"
