"""Extraction engine — runs Singer tap, converts to Parquet, uploads to bucket."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from dataspoc_pipe.config import PipelineConfig
from dataspoc_pipe.singer import SingerMessage, json_schema_to_pyarrow, parse_message
from dataspoc_pipe.storage import atomic_write, write_bytes

BATCH_SIZE = 10_000


@dataclass
class StreamBuffer:
    """Record buffer for a Singer stream."""

    name: str
    schema: pa.Schema | None = None
    records: list[dict] = field(default_factory=list)
    total_records: int = 0
    batches_written: int = 0


@dataclass
class ExtractionResult:
    """Result of an extraction."""

    pipeline: str
    success: bool
    streams: dict[str, int] = field(default_factory=dict)  # stream → post-transform record count
    schemas: dict[str, list] = field(default_factory=dict)  # stream → post-transform column dicts
    streams_raw: dict[str, int] = field(default_factory=dict)  # stream → pre-transform record count
    error: str | None = None
    last_state: dict | None = None


def run_pipeline(
    config: PipelineConfig,
    state: dict | None = None,
    full: bool = False,
    on_progress: callable | None = None,
) -> ExtractionResult:
    """Run a full pipeline: tap → parquet → bucket."""
    result = ExtractionResult(pipeline=config.name, success=False)
    buffers: dict[str, StreamBuffer] = {}
    last_state = None
    extraction_date = date.today().isoformat()

    # Build tap command
    tap_cmd = _build_tap_command(config, state if not full else None)

    try:
        # If command has spaces (e.g.: "python mock_tap.py"), use shell=True
        if len(tap_cmd) > 0 and " " in tap_cmd[0]:
            shell_cmd = " ".join(tap_cmd)
            process = subprocess.Popen(
                shell_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True,
            )
        else:
            process = subprocess.Popen(
                tap_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                msg = parse_message(line)
            except (json.JSONDecodeError, KeyError):
                continue

            if msg.type == "SCHEMA":
                schema = json_schema_to_pyarrow(msg.schema)
                if msg.stream not in buffers:
                    buffers[msg.stream] = StreamBuffer(name=msg.stream)
                buffers[msg.stream].schema = schema

            elif msg.type == "RECORD":
                stream = msg.stream
                if stream not in buffers:
                    buffers[stream] = StreamBuffer(name=stream)

                buffers[stream].records.append(msg.record)
                buffers[stream].total_records += 1

                # Flush when buffer is full
                if len(buffers[stream].records) >= BATCH_SIZE:
                    _flush_buffer(config, buffers[stream], extraction_date)
                    if on_progress:
                        on_progress(stream, buffers[stream].total_records)

            elif msg.type == "STATE":
                last_state = msg.value

        # Wait for process to finish
        process.wait()
        stderr_output = process.stderr.read()

        if process.returncode != 0:
            result.error = f"Tap failed (exit code {process.returncode}): {stderr_output[:500]}"
            return result

        # Flush remaining buffers
        for stream_buf in buffers.values():
            if stream_buf.records:
                _flush_buffer(config, stream_buf, extraction_date)

        # Result — counts and schema reflect POST-transform data
        result.success = True
        result.streams = {name: buf.total_records for name, buf in buffers.items()}
        result.streams_raw = {
            name: getattr(buf, 'rows_before_transform', buf.total_records)
            for name, buf in buffers.items()
        }
        result.schemas = {}
        for name, buf in buffers.items():
            # Use final_schema (post-transform) if available, else tap schema
            schema = getattr(buf, 'final_schema', buf.schema)
            if schema:
                result.schemas[name] = [
                    {"name": f.name, "type": str(f.type), "nullable": f.nullable}
                    for f in schema
                ]
        result.last_state = last_state

    except FileNotFoundError:
        result.error = (
            f"Tap '{config.source.tap}' not found in PATH.\n"
            f"  Install with: pip install {config.source.tap}\n"
            f"  Or use a built-in tap: google-sheets-public"
        )
    except Exception as e:
        result.error = str(e)

    return result


def _build_tap_command(config: PipelineConfig, state: dict | None) -> list[str]:
    """Build the Singer tap command.

    Built-in taps (google-sheets-public, etc.) are executed as Python modules.
    External taps are executed as system commands.
    """
    from dataspoc_pipe.tap_templates import BUILTIN_TAPS

    tap_name = config.source.tap
    if tap_name in BUILTIN_TAPS:
        # Built-in tap: run as python module
        module = BUILTIN_TAPS[tap_name]
        cmd = [sys.executable, "-m", module]
    else:
        cmd = [tap_name]

    # Tap config
    if isinstance(config.source.config, dict):
        # Save config to temporary file
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config.source.config, tmp)
        tmp.close()
        cmd.extend(["--config", tmp.name])
    elif isinstance(config.source.config, str) and config.source.config:
        cmd.extend(["--config", config.source.config])

    # State for incremental
    if state and config.incremental.enabled:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(state, tmp)
        tmp.close()
        cmd.extend(["--state", tmp.name])

    return cmd


def _flush_buffer(config: PipelineConfig, buf: StreamBuffer, extraction_date: str) -> None:
    """Convert buffer to Parquet and upload to bucket."""
    if not buf.records:
        return

    # Convert records to PyArrow Table
    if buf.schema:
        # Use explicit schema — handle missing fields
        columns = {}
        for field_item in buf.schema:
            name = field_item.name
            values = [r.get(name) for r in buf.records]
            try:
                columns[name] = pa.array(values, type=field_item.type)
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                # Fallback: convert to string
                columns[name] = pa.array([str(v) if v is not None else None for v in values], type=pa.string())
        table = pa.table(columns, schema=buf.schema)
    else:
        # No schema: infer from PyArrow
        table = pa.Table.from_pylist(buf.records)

    rows_before = table.num_rows
    cols_before = table.num_columns

    # Apply transform by convention: ~/.dataspoc-pipe/transforms/<pipeline_name>.py
    from dataspoc_pipe.config import DATASPOC_HOME
    transform_path = DATASPOC_HOME / "transforms" / f"{config.name}.py"
    if transform_path.exists():
        table = _apply_transform(str(transform_path), table, buf.name)

        rows_after = table.num_rows
        cols_after = table.num_columns

        # Update record count to reflect post-transform reality
        diff_rows = rows_before - rows_after
        if diff_rows != 0:
            buf.total_records -= diff_rows

        # Store transform metadata for manifest
        if not hasattr(buf, 'transform_applied'):
            buf.transform_applied = True
            buf.rows_before_transform = 0
            buf.cols_before_transform = cols_before
        buf.rows_before_transform += rows_before
        buf.cols_after_transform = cols_after
        buf.final_schema = table.schema

    # Determine compression
    compression = config.destination.compression
    if compression == "none":
        compression = None

    # Write Parquet in memory
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression=compression)
    parquet_bytes = sink.getvalue().to_pybytes()

    # Build path in bucket
    bucket = config.destination.bucket.rstrip("/")
    base_path = config.destination.path.strip("/")
    # Extract source name from tap name (e.g.: "tap-postgres" → "postgres")
    tap_name = config.source.tap.split()[-1]  # Get last token (ignore python path)
    source_name = Path(tap_name).stem.replace("tap-", "")

    if config.incremental.enabled:
        # Incremental: partition by date (append new data per day)
        uri = f"{bucket}/{base_path}/{source_name}/{buf.name}/dt={extraction_date}/{buf.name}_{buf.batches_written:04d}.parquet"
    else:
        # Full extraction: single file, overwrite (no partitioning)
        uri = f"{bucket}/{base_path}/{source_name}/{buf.name}/{buf.name}_{buf.batches_written:04d}.parquet"

    write_bytes(uri, parquet_bytes)
    buf.batches_written += 1
    buf.records.clear()


def _apply_transform(transform_path: str, table: pa.Table, stream_name: str) -> pa.Table:
    """Load and apply a Python transform script to a PyArrow Table.

    The script must define a `transform(df)` function that receives a
    pandas DataFrame and returns a pandas DataFrame.

    Args:
        transform_path: path to the .py script
        table: PyArrow Table with the raw data
        stream_name: name of the current stream

    Returns:
        Transformed PyArrow Table
    """
    import importlib.util

    path = Path(transform_path).expanduser()
    if not path.exists():
        return table

    try:
        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(f"transform_{stream_name}", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if not hasattr(mod, "transform"):
            return table

        # Convert to DataFrame, transform, convert back
        df = table.to_pandas()
        df = mod.transform(df)

        if df is None:
            return table

        return pa.Table.from_pandas(df, preserve_index=False)

    except Exception as e:
        # Transform failure should not break the pipeline — log and continue with raw data
        import sys
        print(f"Warning: transform failed for '{stream_name}': {e}", file=sys.stderr)
        return table
