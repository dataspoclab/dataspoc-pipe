# DataSpoc Pipe — Agent Guide

You are interacting with DataSpoc Pipe, a data ingestion engine that connects Singer taps to Parquet files in cloud buckets.

## What you can do

| Capability | How | Returns |
|------------|-----|---------|
| List pipelines | `dataspoc-pipe status` | All pipelines with last run, status, records |
| Run a pipeline | `dataspoc-pipe run <name>` | Extraction result (success, record counts) |
| Run all pipelines | `dataspoc-pipe run _ --all` | Summary of all runs |
| Force full extraction | `dataspoc-pipe run <name> --full` | Ignores incremental bookmarks |
| View logs | `dataspoc-pipe logs <name>` | JSON log of last execution |
| Validate connectivity | `dataspoc-pipe validate <name>` | Tests bucket write + tap availability |
| Validate all | `dataspoc-pipe validate` | Tests all pipelines |
| View catalog | `dataspoc-pipe manifest <bucket>` | Tables, schemas, extraction stats |
| Create pipeline | `dataspoc-pipe add <name>` | Interactive wizard (not for agents) |
| Install schedules | `dataspoc-pipe schedule install` | Cron jobs for scheduled pipelines |

## Python SDK

```python
# List pipelines
from dataspoc_pipe.config import list_pipelines, load_pipeline
names = list_pipelines()  # ["sales", "users", "events"]

# Load config
config = load_pipeline("sales")
# config.name, config.source.tap, config.destination.bucket

# Run pipeline
from dataspoc_pipe.engine import run_pipeline
from dataspoc_pipe.state import load_state

state = load_state(config.destination.bucket, "sales")
result = run_pipeline(config, state=state)
# result.success → True/False
# result.streams → {"orders": 5000, "line_items": 12000}
# result.error → None or error message

# View manifest (data catalog)
from dataspoc_pipe.catalog import load_manifest
manifest = load_manifest("s3://my-bucket")
# {"version": "1.0", "tables": {"source/table": {stats...}}}

# View last execution log
from dataspoc_pipe.catalog import load_latest_log
log = load_latest_log("s3://my-bucket", "sales")
# {"pipeline": "sales", "status": "success", "total_records": 17000, ...}
```

## Key functions

| Module | Function | Signature | Returns |
|--------|----------|-----------|---------|
| `config` | `list_pipelines()` | `() → list[str]` | Pipeline names |
| `config` | `load_pipeline(name)` | `(str) → PipelineConfig` | Pydantic model with source, destination, schedule |
| `config` | `save_pipeline(config)` | `(PipelineConfig) → Path` | Path to saved YAML |
| `engine` | `run_pipeline(config, state, full)` | `(PipelineConfig, dict?, bool) → ExtractionResult` | Success, streams, error |
| `state` | `load_state(bucket, pipeline)` | `(str, str) → dict?` | Incremental bookmark or None |
| `state` | `save_state(bucket, pipeline, state)` | `(str, str, dict) → None` | Writes state to bucket |
| `catalog` | `load_manifest(bucket)` | `(str) → dict` | Full data catalog |
| `catalog` | `update_manifest(bucket, result, source)` | `(str, ExtractionResult, str) → None` | Updates catalog |
| `catalog` | `load_latest_log(bucket, pipeline)` | `(str, str) → dict?` | Last execution log |
| `catalog` | `save_execution_log(bucket, result, start, end)` | `(...) → None` | Writes log to bucket |

## Data models

### PipelineConfig (Pydantic)

```yaml
source:
  tap: tap-postgres          # Singer tap command
  config: ~/.dataspoc-pipe/sources/sales.json  # Tap config path
  streams: [orders, customers]  # Optional filter (null = all)

destination:
  bucket: s3://my-bucket     # S3, GCS, Azure, or file://
  path: raw                  # Base path in bucket
  compression: zstd          # zstd, snappy, gzip, none
  partition_by: _extraction_date

incremental:
  enabled: true              # Use Singer bookmarks

schedule:
  cron: "0 */6 * * *"       # Optional cron expression
```

### ExtractionResult

```python
@dataclass
class ExtractionResult:
    pipeline: str                    # Pipeline name
    success: bool                    # True if extraction completed
    streams: dict[str, int]          # {stream_name: record_count}
    schemas: dict[str, list]         # {stream_name: column_info}
    streams_raw: dict[str, int]      # Pre-transform counts
    error: str | None                # Error message if failed
    last_state: dict | None          # Updated bookmark state
```

## Configuration

```
~/.dataspoc-pipe/
  config.yaml           # Global defaults (compression, partition_by)
  sources/              # One JSON per data source (tap config)
    sales.json
    users.json
  pipelines/            # One YAML per pipeline
    sales.yaml
    users.yaml
  transforms/           # Optional Python transforms
    sales.py            # def transform(df) → df
```

## Bucket convention (public contract)

```
<bucket>/
  .dataspoc/
    manifest.json                          # Data catalog (Pipe writes, Lens reads)
    state/<pipeline>/state.json            # Incremental bookmarks
    logs/<pipeline>/<timestamp>.json       # Execution history
  raw/<source>/<table>/
    dt=YYYY-MM-DD/                         # Hive-style partitioning
      <table>_0000.parquet                 # Parquet files (zstd compressed)
      <table>_0001.parquet
```

Source name is derived from tap: `tap-postgres` → `postgres`, `tap-csv` → `csv`.

## Patterns for agents

### Pattern: Check status and run stale pipelines
```
1. dataspoc-pipe status                     → see all pipelines + last run
2. Identify pipelines not run today
3. dataspoc-pipe run <name>                 → run each stale pipeline
4. dataspoc-pipe status                     → verify success
```

### Pattern: Validate before running
```
1. dataspoc-pipe validate <name>            → test bucket + tap connectivity
2. dataspoc-pipe run <name>                 → run if validation passed
3. dataspoc-pipe logs <name>                → check details
```

### Pattern: Full re-extraction
```
1. dataspoc-pipe run <name> --full          → ignore bookmarks, extract everything
2. dataspoc-pipe manifest <bucket>          → verify catalog updated
```

### Pattern: Monitor all pipelines
```
1. dataspoc-pipe status                     → overview table
2. For any failed: dataspoc-pipe logs <name> → get error details
3. Fix source issue
4. dataspoc-pipe run <name>                 → retry
```

## Built-in taps (no extra install)

| Tap | Source |
|-----|--------|
| `parquet` | Parquet files (local or cloud) |
| `google-sheets-public` | Public Google Sheets |

Any Singer-compatible tap works. Install separately: `pip install tap-postgres`.

## Constraints

- Batch only. No streaming, no CDC.
- No concurrent writes to the same bucket (pipelines run sequentially).
- Pipe needs WRITE access to the destination bucket (cloud IAM).
- Singer taps are external binaries — must be on PATH.
- Transforms are convention-based: `~/.dataspoc-pipe/transforms/<pipeline>.py` with `def transform(df)`.
- Never modify the bucket convention without versioning — Lens depends on it.
