"""MCP Server for DataSpoc Pipe — exposes Pipe capabilities as MCP tools."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("dataspoc-pipe")

_client = None


def _get_client():
    """Return a singleton PipeClient instance."""
    global _client
    if _client is None:
        from dataspoc_pipe.sdk import PipeClient

        _client = PipeClient()
    return _client


# ------------------------------------------------------------------
# Tools
# ------------------------------------------------------------------


@mcp.tool()
def list_pipelines() -> str:
    """List all configured pipeline names, one per line."""
    client = _get_client()
    names = client.pipelines()
    return "\n".join(names) if names else "No pipelines configured."


@mcp.tool()
def pipeline_config(name: str) -> str:
    """Return the full configuration of a pipeline as JSON.

    Args:
        name: Pipeline name.
    """
    client = _get_client()
    cfg = client.config(name)
    return json.dumps(cfg, default=str)


@mcp.tool()
def run_pipeline(name: str, full: bool = False) -> str:
    """Run an extraction pipeline and return the result as JSON.

    Returns a JSON object with keys: success, streams, error.

    Args:
        name: Pipeline name.
        full: If True, force full extraction ignoring incremental state.
    """
    client = _get_client()
    result = client.run(name, full=full)
    return json.dumps(result, default=str)


@mcp.tool()
def pipeline_status() -> str:
    """Return status for all configured pipelines as a JSON array.

    Each entry contains: name, last_run, status, duration, records.
    """
    client = _get_client()
    rows = client.status()
    return json.dumps(rows, default=str)


@mcp.tool()
def pipeline_logs(name: str) -> str:
    """Return the latest execution log for a pipeline as JSON.

    Args:
        name: Pipeline name.
    """
    client = _get_client()
    log = client.logs(name)
    if log is None:
        return "No logs found"
    return json.dumps(log, default=str)


@mcp.tool()
def show_manifest(bucket: str) -> str:
    """Return the manifest (catalog) of a bucket as JSON.

    Args:
        bucket: Bucket URI (e.g. s3://my-bucket, file:///tmp/lake).
    """
    client = _get_client()
    m = client.manifest(bucket)
    return json.dumps(m, default=str)


@mcp.tool()
def validate_pipeline(name: str) -> str:
    """Validate bucket connectivity and tap availability for a pipeline.

    Returns a JSON object with keys: pipeline, bucket_ok, tap_ok, errors.

    Args:
        name: Pipeline name.
    """
    client = _get_client()
    result = client.validate(name)
    result["pipeline"] = name
    return json.dumps(result, default=str)


# ------------------------------------------------------------------
# Resources
# ------------------------------------------------------------------


@mcp.resource("pipe://pipelines")
def pipelines_resource() -> str:
    """List all pipeline names with their tap and bucket."""
    client = _get_client()
    names = client.pipelines()
    entries = []
    for name in names:
        try:
            cfg = client.config(name)
            tap = cfg.get("source", {}).get("tap", "unknown")
            bucket = cfg.get("destination", {}).get("bucket", "unknown")
            entries.append({"name": name, "tap": tap, "bucket": bucket})
        except Exception:
            entries.append({"name": name, "tap": "error", "bucket": "error"})
    return json.dumps(entries, default=str)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def run_server():
    """Start the MCP server."""
    mcp.run()
