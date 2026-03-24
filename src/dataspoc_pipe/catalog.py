"""Catalog (manifest) and observability (logs/status)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from dataspoc_pipe.engine import ExtractionResult
from dataspoc_pipe.storage import atomic_write, exists, read_bytes, write_bytes


# --- Manifest ---

def get_manifest_uri(bucket: str) -> str:
    return f"{bucket.rstrip('/')}/.dataspoc/manifest.json"


def load_manifest(bucket: str) -> dict:
    """Load manifest from bucket. Returns empty if it does not exist."""
    uri = get_manifest_uri(bucket)
    if not exists(uri):
        return {"version": "1.0", "updated_at": None, "tables": {}}
    return json.loads(read_bytes(uri))


def update_manifest(bucket: str, result: ExtractionResult, source_name: str) -> None:
    """Update manifest with extraction results."""
    manifest = load_manifest(bucket)
    now = datetime.now(timezone.utc).isoformat()
    manifest["updated_at"] = now

    for stream, count in result.streams.items():
        key = f"{source_name}/{stream}"
        if key not in manifest["tables"]:
            manifest["tables"][key] = {
                "source": source_name,
                "table": stream,
                "stats": {"total_rows": 0, "extractions": 0},
            }

        table = manifest["tables"][key]
        table["stats"]["total_rows"] += count
        table["stats"]["extractions"] += 1
        table["stats"]["last_extraction"] = now
        table["stats"]["last_extraction_rows"] = count

        # Save column schema if available
        if hasattr(result, 'schemas') and stream in result.schemas:
            table["columns"] = result.schemas[stream]

    data = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    atomic_write(get_manifest_uri(bucket), data)


# --- Logs ---

def get_log_uri(bucket: str, pipeline: str, timestamp: str) -> str:
    return f"{bucket.rstrip('/')}/.dataspoc/logs/{pipeline}/{timestamp}.json"


def save_execution_log(
    bucket: str,
    result: ExtractionResult,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    """Save execution log to bucket."""
    ts = started_at.strftime("%Y-%m-%dT%H-%M-%S")
    log = {
        "pipeline": result.pipeline,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "status": "success" if result.success else "failure",
        "streams": {name: {"records": count} for name, count in result.streams.items()},
        "total_records": sum(result.streams.values()),
    }
    if result.error:
        log["error"] = result.error

    uri = get_log_uri(bucket, result.pipeline, ts)
    data = json.dumps(log, indent=2, ensure_ascii=False).encode()
    write_bytes(uri, data)

    return log


def load_latest_log(bucket: str, pipeline: str) -> dict | None:
    """Load the most recent log of a pipeline."""
    from dataspoc_pipe.storage import list_files

    prefix = f"{bucket.rstrip('/')}/.dataspoc/logs/{pipeline}"
    try:
        files = list_files(prefix)
    except Exception:
        return None

    if not files:
        return None

    # Get the most recent (lexicographic ordering of timestamps)
    json_files = [f for f in files if f.endswith(".json")]
    if not json_files:
        return None

    latest = sorted(json_files)[-1]
    # list_files may return paths without scheme — add the bucket scheme
    if not latest.startswith(("s3://", "gs://", "az://", "file://", "/")):
        # Extract scheme from bucket URI
        scheme = bucket.split("://")[0] if "://" in bucket else "file"
        latest = f"{scheme}://{latest}"
    elif latest.startswith("/") and not latest.startswith("file://"):
        latest = f"file://{latest}"

    return json.loads(read_bytes(latest))


def list_pipeline_logs(bucket: str, pipeline: str, limit: int = 10) -> list[dict]:
    """List the last N logs of a pipeline."""
    from dataspoc_pipe.storage import list_files

    prefix = f"{bucket.rstrip('/')}/.dataspoc/logs/{pipeline}"
    try:
        files = list_files(prefix)
    except Exception:
        return []

    json_files = sorted([f for f in files if f.endswith(".json")])[-limit:]
    scheme = bucket.split("://")[0] if "://" in bucket else "file"
    logs = []
    for f in json_files:
        if not f.startswith(("s3://", "gs://", "az://", "file://", "/")):
            f = f"{scheme}://{f}"
        elif f.startswith("/") and not f.startswith("file://"):
            f = f"file://{f}"
        try:
            logs.append(json.loads(read_bytes(f)))
        except Exception:
            continue
    return logs
