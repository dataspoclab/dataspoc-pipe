<h1 align="center">DataSpoc Pipe</h1>

<p align="center">
  <a href="https://github.com/dataspoclab/dataspoc-pipe/actions"><img src="https://img.shields.io/github/actions/workflow/status/dataspoclab/dataspoc-pipe/ci.yml?branch=main&label=CI&style=flat-square" alt="CI"></a>
  <a href="https://pypi.org/project/dataspoc-pipe/"><img src="https://img.shields.io/pypi/v/dataspoc-pipe?style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/dataspoclab/dataspoc-pipe/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License"></a>
  <a href="https://pypi.org/project/dataspoc-pipe/"><img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python 3.10+"></a>
</p>

<p align="center"><i>Singer taps to Parquet in cloud buckets. That simple.</i></p>

## Why DataSpoc Pipe?

Most data ingestion tools drown you in orchestration complexity. DataSpoc Pipe does one thing well: connect to any of the **400+ Singer taps** (databases, APIs, SaaS), convert to Parquet, and land it in your cloud bucket -- cataloged and ready to query. No DAGs, no servers, no infrastructure.

> **400+** data sources -- **Streaming** (no memory limits) -- **Zero** infrastructure -- **< 15 min** setup

## Installation

```bash
pip install dataspoc-pipe
```

Cloud storage extras:

```bash
pip install dataspoc-pipe[s3]      # AWS S3
pip install dataspoc-pipe[gcs]     # Google Cloud Storage
pip install dataspoc-pipe[azure]   # Azure Blob Storage
```

Singer taps are installed separately:

```bash
pip install tap-csv
pip install tap-postgres
```

## Quick Start

### 1. Initialize

```bash
dataspoc-pipe init
```

Creates `~/.dataspoc-pipe/` with `config.yaml`, `pipelines/`, `sources/`, and `transforms/`.

### 2. Install a Singer tap and prepare data

```bash
pip install tap-csv
```

Create `/tmp/sample/users.csv`:

```csv
id,name,email
1,Alice,alice@example.com
2,Bob,bob@example.com
3,Carol,carol@example.com
```

### 3. Create a pipeline

```bash
dataspoc-pipe add my-first-pipeline
```

The interactive wizard prompts for tap name, destination bucket, compression, incremental mode, and schedule. Or create `~/.dataspoc-pipe/pipelines/my-first-pipeline.yaml` manually:

```yaml
source:
  tap: tap-csv
  config:
    files:
      - entity: users
        path: /tmp/sample/users.csv
        keys:
          - id

destination:
  bucket: file:///tmp/my-lake
  path: raw
  compression: zstd

incremental:
  enabled: false
```

### 4. Validate and run

```bash
dataspoc-pipe validate my-first-pipeline
dataspoc-pipe run my-first-pipeline
```

### 5. Check results

```bash
dataspoc-pipe status
dataspoc-pipe logs my-first-pipeline
dataspoc-pipe manifest file:///tmp/my-lake
```

Your data is now at `/tmp/my-lake/raw/csv/users/dt=2026-03-20/users_0000.parquet`.

## How It Works

```
┌─────────────┐    ┌──────────┐  stdout  ┌───────────────┐    ┌──────────────┐
│ Data Source  │───>│ Singer   │─────────>│ DataSpoc Pipe │───>│ Cloud Bucket │
│ (DB, API, …)│    │ Tap      │          │ transform(df) │    │ (S3/GCS/Az)  │
└─────────────┘    └──────────┘          └───────┬───────┘    └──────────────┘
                                                 │
                                          manifest.json
                                           state.json
                                             logs/
```

1. Singer tap extracts data from the source, emits JSON on stdout
2. Pipe reads the stream, buffers in batches (~10K records)
3. If `~/.dataspoc-pipe/transforms/<pipeline>.py` exists, applies `transform(df)` per batch
4. Converts to Parquet (zstd) and uploads to bucket
5. Updates the manifest catalog and saves execution logs

## AI Agent Integration

Pipe works as an MCP server for Claude Desktop, Claude Code, Cursor, and any MCP-compatible AI agent.

```bash
pip install dataspoc-pipe[mcp]
dataspoc-pipe mcp                     # Start MCP server (stdio)
```

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dataspoc-pipe": {
      "command": "dataspoc-pipe",
      "args": ["mcp"]
    }
  }
}
```

Your agent can now list pipelines, trigger runs, check status, and read logs.

### Python SDK

```python
from dataspoc_pipe import PipeClient

client = PipeClient()
pipelines = client.pipelines()
result = client.run("sales-data")
status = client.status()
log = client.logs("sales-data")
```

### JSON Output

All CLI commands support `--output json` for machine-readable output:

```bash
dataspoc-pipe status --output json
dataspoc-pipe manifest s3://my-bucket --output json
```

## Commands

```bash
dataspoc-pipe init                    # Initialize config structure
dataspoc-pipe add <name>              # Create pipeline (interactive wizard)
dataspoc-pipe run <name>              # Run a pipeline
dataspoc-pipe run <name> --full       # Force full extraction (ignore bookmarks)
dataspoc-pipe run _ --all             # Run all pipelines
dataspoc-pipe status                  # Status table for all pipelines
dataspoc-pipe logs <name>             # Last execution log (JSON)
dataspoc-pipe validate [name]         # Test bucket and tap connectivity
dataspoc-pipe manifest <bucket>       # Show data catalog
dataspoc-pipe schedule install        # Install cron jobs
dataspoc-pipe schedule remove         # Remove cron jobs
dataspoc-pipe mcp                    # Start MCP server for AI agents
dataspoc-pipe --version              # Show version
```

## Incremental Extraction

Enable in pipeline YAML:

```yaml
incremental:
  enabled: true
```

Pipe saves Singer bookmarks to `<bucket>/.dataspoc/state/<pipeline>/state.json`. Next run only fetches new data. Use `--full` to re-extract everything.

## Bucket Convention

This is the public contract between Pipe, Lens, and ML. Do not change without versioning.

```
<bucket>/
  .dataspoc/
    manifest.json                          # Data catalog
    state/<pipeline>/state.json            # Incremental bookmarks
    logs/<pipeline>/<timestamp>.json       # Execution logs
  raw/<source>/<table>/
    dt=YYYY-MM-DD/                         # Hive-style partitioning
      <table>_0000.parquet                 # Data files
```

## Built-in Taps

| Tap | Source | Extra install |
|-----|--------|---------------|
| `parquet` | Parquet files (local/cloud) | None |
| `google-sheets-public` | Public Google Sheets | None |

Any Singer-compatible tap works. Run `dataspoc-pipe add` to see available templates.

## Part of the DataSpoc Platform

| Product | Role |
|---------|------|
| **[DataSpoc Pipe](https://github.com/dataspoclab/dataspoc-pipe)** (this) | Ingestion: Singer taps to Parquet in cloud buckets |
| **[DataSpoc Lens](https://github.com/dataspoclab/dataspoc-lens)** | Virtual warehouse: SQL + Jupyter + AI over your data lake |
| **DataSpoc ML** | AutoML: train and deploy models from your lake |

The bucket is the contract. Pipe writes. Lens reads. ML learns.

## Community

- **GitHub Issues** -- [Report bugs or request features](https://github.com/dataspoclab/dataspoc-pipe/issues)
- **Contributing** -- PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines

## License

[Apache 2.0](LICENSE) -- free to use, modify, and distribute.
