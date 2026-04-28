"""PipeClient — Python SDK for DataSpoc Pipe."""

from __future__ import annotations


class PipeClient:
    """Programmatic interface to DataSpoc Pipe.

    All methods return JSON-serializable data. Imports are lazy
    to keep ``import dataspoc_pipe`` fast.
    """

    # ------------------------------------------------------------------
    # pipelines
    # ------------------------------------------------------------------
    def pipelines(self) -> list[str]:
        """Return the names of all configured pipelines."""
        from dataspoc_pipe.config import list_pipelines

        return list_pipelines()

    # ------------------------------------------------------------------
    # config
    # ------------------------------------------------------------------
    def config(self, name: str) -> dict:
        """Return the full configuration of a pipeline as a plain dict.

        Keys: name, source (tap, config, streams), destination (bucket,
        path, partition_by, compression), incremental (enabled),
        schedule (cron).
        """
        from dataspoc_pipe.config import load_pipeline

        cfg = load_pipeline(name)
        return cfg.model_dump()

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------
    def run(self, name: str, full: bool = False) -> dict:
        """Load, execute, and persist results for a pipeline.

        Handles state loading (incremental), manifest update, and
        execution log — same post-run steps as the CLI ``run`` command.

        Returns ``{"success": bool, "streams": {name: count}, "error": str | None}``.
        """
        from datetime import datetime, timezone
        from pathlib import Path

        from dataspoc_pipe.catalog import save_execution_log, update_manifest
        from dataspoc_pipe.config import load_pipeline
        from dataspoc_pipe.engine import run_pipeline
        from dataspoc_pipe.state import load_state, save_state

        config = load_pipeline(name)

        # Load incremental state when applicable
        state = None
        if config.incremental.enabled and not full:
            state = load_state(config.destination.bucket, name)

        started_at = datetime.now(timezone.utc)
        result = run_pipeline(config, state=state, full=full)
        finished_at = datetime.now(timezone.utc)

        # Persist state on success
        if result.success and result.last_state:
            save_state(config.destination.bucket, name, result.last_state)

        # Update manifest on success
        if result.success:
            tap_name = config.source.tap.split()[-1]
            source_name = Path(tap_name).stem.replace("tap-", "")
            update_manifest(config.destination.bucket, result, source_name)

        # Save execution log (best-effort)
        try:
            save_execution_log(config.destination.bucket, result, started_at, finished_at)
        except Exception:
            pass

        return {
            "success": result.success,
            "streams": dict(result.streams),
            "error": result.error,
        }

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def status(self) -> list[dict]:
        """Return status for every configured pipeline.

        Each entry: ``{"name", "last_run", "status", "duration", "records"}``.
        Matches the output of ``dataspoc-pipe status``.
        """
        from dataspoc_pipe.catalog import load_latest_log
        from dataspoc_pipe.config import list_pipelines, load_pipeline

        names = list_pipelines()
        rows: list[dict] = []

        for name in names:
            try:
                config = load_pipeline(name)
                log = load_latest_log(config.destination.bucket, name)
            except Exception:
                rows.append(
                    {"name": name, "last_run": None, "status": "no runs", "duration": None, "records": None}
                )
                continue

            if log is None:
                rows.append(
                    {"name": name, "last_run": None, "status": "no runs", "duration": None, "records": None}
                )
            else:
                rows.append({
                    "name": name,
                    "last_run": log.get("started_at"),
                    "status": log.get("status", "unknown"),
                    "duration": log.get("duration_seconds"),
                    "records": log.get("total_records"),
                })

        return rows

    # ------------------------------------------------------------------
    # logs
    # ------------------------------------------------------------------
    def logs(self, name: str) -> dict | None:
        """Return the latest execution log for a pipeline, or ``None``."""
        from dataspoc_pipe.catalog import load_latest_log
        from dataspoc_pipe.config import load_pipeline

        config = load_pipeline(name)
        return load_latest_log(config.destination.bucket, name)

    # ------------------------------------------------------------------
    # manifest
    # ------------------------------------------------------------------
    def manifest(self, bucket: str) -> dict:
        """Return the manifest (catalog) dict for a bucket."""
        from dataspoc_pipe.catalog import load_manifest

        return load_manifest(bucket)

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------
    def validate(self, name: str) -> dict:
        """Test bucket connectivity and tap availability for a pipeline.

        Returns ``{"bucket_ok": bool, "tap_ok": bool, "errors": [str]}``.
        """
        import shutil

        from dataspoc_pipe.config import load_pipeline
        from dataspoc_pipe.storage import delete, exists, write_bytes

        config = load_pipeline(name)
        errors: list[str] = []

        # Test bucket write / read / delete
        test_uri = f"{config.destination.bucket.rstrip('/')}/.dataspoc/_validate_test"
        bucket_ok = False
        try:
            write_bytes(test_uri, b"ok")
            assert exists(test_uri)
            delete(test_uri)
            bucket_ok = True
        except Exception as exc:
            errors.append(f"Bucket test failed: {exc}")

        # Test tap in PATH
        tap_ok = bool(shutil.which(config.source.tap))
        if not tap_ok:
            errors.append(f"Tap '{config.source.tap}' not found in PATH")

        return {"bucket_ok": bucket_ok, "tap_ok": tap_ok, "errors": errors}
