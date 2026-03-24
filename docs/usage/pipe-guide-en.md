# DataSpoc Pipe -- Usage Guide

## Table of Contents

1. [Introduction](#1-introduction)
2. [Installation](#2-installation)
3. [Quickstart: Your First Pipeline in 15 Minutes](#3-quickstart-your-first-pipeline-in-15-minutes)
4. [Configuration Reference](#4-configuration-reference)
5. [Commands Reference](#5-commands-reference)
6. [Incremental Extraction](#6-incremental-extraction)
7. [Multi-Cloud Storage](#7-multi-cloud-storage)
8. [Directory Convention](#8-directory-convention)
9. [Transforms](#9-transforms)
10. [Scheduling](#10-scheduling)
11. [Troubleshooting](#11-troubleshooting)
12. [Practical Examples](#12-practical-examples)
13. [Part of the DataSpoc Platform](#13-part-of-the-dataspoc-platform)

---

## 1. Introduction

### What is DataSpoc Pipe?

DataSpoc Pipe is an open-source data ingestion engine that connects any data source to your cloud (or local) data lake using three proven technologies:

- **Singer** -- an open standard for data extraction with hundreds of available taps
- **Parquet** -- a columnar file format optimized for analytics
- **Cloud buckets** -- S3, GCS, Azure Blob, or local filesystem

The pipeline is simple: a Singer tap extracts data from the source, DataSpoc Pipe reads the JSON output stream, converts records to Parquet in batches, and uploads the result to your bucket following a standard directory convention.

### Who is it for?

- Data engineers who need a lightweight ingestion layer without the overhead of a full orchestrator
- Small and mid-size teams that want a data lake without managing complex infrastructure
- Anyone who prefers convention over configuration

### What problem does it solve?

Setting up data ingestion typically requires stitching together multiple tools: an orchestrator, a format converter, a storage client, state management for incremental loads, and a catalog. DataSpoc Pipe handles all of this in a single CLI tool with YAML configuration files. You install it, create a pipeline definition, and run it. That is it.

---

## 2. Installation

### Requirements

- **Python 3.10** or higher
- **pip** (or any PEP 517-compatible installer)

### Base install

```bash
pip install dataspoc-pipe
```

The base install supports local filesystem storage (`file://` URIs) out of the box.

### Cloud storage extras

Install the extra that matches your cloud provider:

```bash
# AWS S3
pip install dataspoc-pipe[s3]

# Google Cloud Storage
pip install dataspoc-pipe[gcs]

# Azure Blob Storage
pip install dataspoc-pipe[azure]
```

You can combine extras:

```bash
pip install dataspoc-pipe[s3,gcs]
```

### Installing Singer taps

DataSpoc Pipe does not bundle any Singer taps. Install each tap separately:

```bash
pip install tap-csv
pip install tap-postgres
pip install tap-github
```

It is recommended to install taps in the same Python environment as DataSpoc Pipe, or ensure they are available on your system `PATH`.

### Verifying the installation

```bash
dataspoc-pipe --version
```

---

## 3. Quickstart: Your First Pipeline in 15 Minutes

This walkthrough extracts data from a local CSV file and writes Parquet files to the local filesystem.

### Step 1: Initialize the configuration structure

```bash
dataspoc-pipe init
```

This creates the directory `~/.dataspoc-pipe/` with:

```
~/.dataspoc-pipe/
  config.yaml          # Global defaults
  pipelines/           # Pipeline definitions go here
```

### Step 2: Install a Singer tap

```bash
pip install tap-csv
```

### Step 3: Prepare a sample CSV file

Create `/tmp/sample/users.csv`:

```csv
id,name,email
1,Alice,alice@example.com
2,Bob,bob@example.com
3,Carol,carol@example.com
```

### Step 4: Create the pipeline

You can use the interactive wizard:

```bash
dataspoc-pipe add my-first-pipeline
```

The wizard will prompt you for:
- Tap name (enter `tap-csv`)
- Tap configuration (JSON or path to config file)
- Destination bucket URI
- Base path in the bucket
- Compression algorithm
- Whether to enable incremental extraction
- Cron schedule (optional)

Alternatively, create the file manually at `~/.dataspoc-pipe/pipelines/my-first-pipeline.yaml`:

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

### Step 5: Validate the setup

```bash
dataspoc-pipe validate my-first-pipeline
```

This checks that the bucket is writable and the tap binary is available on the PATH.

### Step 6: Run the pipeline

```bash
dataspoc-pipe run my-first-pipeline
```

You will see output similar to:

```
Executing: my-first-pipeline
  users: 3 records...
Success! 3 records in 1 stream(s)
  users: 3
```

### Step 7: Inspect the results

Your data is now stored as Parquet at:

```
/tmp/my-lake/raw/csv/users/dt=2026-03-20/users_0000.parquet
```

Check the pipeline status:

```bash
dataspoc-pipe status
```

View execution logs:

```bash
dataspoc-pipe logs my-first-pipeline
```

View the lake catalog:

```bash
dataspoc-pipe manifest file:///tmp/my-lake
```

---

## 4. Configuration Reference

Pipelines are defined as YAML files stored in `~/.dataspoc-pipe/pipelines/<name>.yaml`. The file name (without `.yaml`) becomes the pipeline name.

### Complete pipeline structure

```yaml
source:
  tap: <string>           # Required. Singer tap command (e.g., "tap-postgres")
  config: <dict|string>   # Required. Inline config dict or path to a JSON config file
  streams:                # Optional. List of stream names to extract (null = all)
    - stream_a
    - stream_b

destination:
  bucket: <string>        # Required. Bucket URI (s3://, gs://, az://, file://)
  path: <string>          # Optional. Base path inside the bucket. Default: "raw"
  partition_by: <string>  # Optional. Partition field name. Default: "_extraction_date"
  compression: <string>   # Optional. Parquet compression: zstd, snappy, gzip, none. Default: "zstd"

incremental:
  enabled: <bool>         # Optional. Enable incremental extraction. Default: false

schedule:
  cron: <string|null>     # Optional. Cron expression for scheduling. Default: null
```

### Field details

#### source.tap

The Singer tap command to execute. This can be:
- A simple command name: `tap-postgres` (must be on PATH)
- A command with arguments: `python my_custom_tap.py`

#### source.config

The tap configuration, provided in one of two ways:
- **Inline dictionary** -- the config is written directly in the YAML:

```yaml
source:
  tap: tap-postgres
  config:
    host: db.example.com
    port: 5432
    user: reader
    password: secret
    dbname: production
```

- **Path to a JSON file** -- useful for complex configs or to keep secrets out of the pipeline file:

```yaml
source:
  tap: tap-postgres
  config: /etc/dataspoc/tap-postgres-config.json
```

#### source.streams

An optional filter. When set, only the listed streams are extracted. When omitted or set to `null`, all streams emitted by the tap are processed.

#### destination.bucket

The URI of the target storage location. Supported schemes:

| Scheme     | Example                     | Provider          |
|------------|-----------------------------|-------------------|
| `file://`  | `file:///data/lake`         | Local filesystem  |
| `s3://`    | `s3://my-company-lake`      | AWS S3            |
| `gs://`    | `gs://my-company-lake`      | Google Cloud      |
| `az://`    | `az://my-company-lake`      | Azure Blob        |

#### destination.compression

Parquet compression algorithm. Available options:

| Value    | Notes                                         |
|----------|-----------------------------------------------|
| `zstd`   | Default. Best compression ratio for analytics |
| `snappy` | Faster compression, larger files              |
| `gzip`   | Widely compatible, slower                     |
| `none`   | No compression                                |

### Global defaults

The file `~/.dataspoc-pipe/config.yaml` contains global defaults:

```yaml
defaults:
  compression: zstd
  partition_by: _extraction_date
```

---

## 5. Commands Reference

### `dataspoc-pipe init`

Initializes the configuration directory structure.

```bash
dataspoc-pipe init
```

Creates:
- `~/.dataspoc-pipe/` -- configuration home directory
- `~/.dataspoc-pipe/pipelines/` -- pipeline definitions directory
- `~/.dataspoc-pipe/config.yaml` -- global defaults file

Running `init` on an already-initialized setup is safe and has no side effects.

---

### `dataspoc-pipe add <name>`

Creates a new pipeline via an interactive wizard.

```bash
dataspoc-pipe add sales-data
```

The wizard prompts for all required fields (tap name, tap config, bucket, path, compression, incremental, and schedule). The resulting pipeline is saved to `~/.dataspoc-pipe/pipelines/<name>.yaml`.

If a pipeline with the same name already exists, the command exits with an error to prevent accidental overwrites.

---

### `dataspoc-pipe run <name>`

Executes a single pipeline.

```bash
dataspoc-pipe run sales-data
```

What happens during execution:

1. The pipeline configuration is loaded and validated
2. If incremental extraction is enabled, the previous state (bookmark) is loaded from the bucket
3. The Singer tap is spawned as a subprocess
4. Records from `stdout` are read, buffered in batches of ~10,000 records, and flushed as Parquet files
5. On success, the state file is updated, the manifest is refreshed, and an execution log is saved

Exit code is `0` on success, `1` on failure.

#### `--full` flag

Forces a full extraction, ignoring any saved incremental state:

```bash
dataspoc-pipe run sales-data --full
```

This is useful when you need to re-extract all data from scratch, for example after a schema change.

#### `--all` flag

Runs all configured pipelines sequentially:

```bash
dataspoc-pipe run _ --all
```

Note: a pipeline name argument is still required syntactically, but it is ignored when `--all` is used. At the end, a summary is printed showing how many pipelines succeeded and how many failed.

---

### `dataspoc-pipe status`

Shows the status of all configured pipelines in a table.

```bash
dataspoc-pipe status
```

Example output:

```
                  Pipelines
+------------+---------------------+---------+----------+---------+
| Pipeline   | Last Run            | Status  | Duration | Records |
+------------+---------------------+---------+----------+---------+
| sales-data | 2026-03-20T08:00:00 | success | 12.3s    | 45000   |
| users      | 2026-03-19T22:00:00 | success | 2.1s     | 320     |
| events     | -                   | no run  | -        | -       |
+------------+---------------------+---------+----------+---------+
```

The status information is read from the execution logs stored in each pipeline's bucket.

---

### `dataspoc-pipe logs <name>`

Displays the full JSON log from the most recent execution of a pipeline.

```bash
dataspoc-pipe logs sales-data
```

Example output:

```json
{
  "pipeline": "sales-data",
  "started_at": "2026-03-20T08:00:00.123456+00:00",
  "finished_at": "2026-03-20T08:00:12.456789+00:00",
  "duration_seconds": 12.33,
  "status": "success",
  "streams": {
    "orders": {"records": 30000},
    "line_items": {"records": 15000}
  },
  "total_records": 45000
}
```

---

### `dataspoc-pipe validate [name]`

Tests connectivity to the bucket and checks that the Singer tap is available.

```bash
# Validate a specific pipeline
dataspoc-pipe validate sales-data

# Validate all pipelines
dataspoc-pipe validate
```

The validation performs two checks for each pipeline:

1. **Bucket test** -- writes a temporary file to the bucket, verifies it exists, then deletes it
2. **Tap test** -- checks if the tap command is found on the system PATH

---

### `dataspoc-pipe manifest <bucket>`

Displays the data catalog (manifest) of a bucket.

```bash
dataspoc-pipe manifest s3://my-company-lake
dataspoc-pipe manifest file:///tmp/my-lake
```

The manifest tracks every table that has been written to the bucket, including extraction statistics (total rows, number of extractions, last extraction timestamp).

---

### `dataspoc-pipe schedule install`

Installs cron jobs for all pipelines that have a `schedule.cron` value configured.

```bash
dataspoc-pipe schedule install
```

Each cron job uses `flock` to prevent overlapping executions. The command is idempotent: if a cron entry for the same pipeline already exists, it is replaced with the current configuration. Run `install` again after changing a cron expression to update the crontab.

`python-crontab` is a core dependency -- no extra install is needed.

---

### `dataspoc-pipe schedule remove`

Removes all DataSpoc Pipe cron entries from the current user's crontab.

```bash
dataspoc-pipe schedule remove
```

Only entries created by DataSpoc Pipe (identified by the comment prefix `dataspoc-pipe:`) are removed. Other crontab entries are left untouched.

---

## 6. Incremental Extraction

### How it works

Many Singer taps support incremental extraction using **bookmarks** (also called **state**). A bookmark records the last position read (e.g., a timestamp or an ID), so the next run only extracts new or modified records.

DataSpoc Pipe manages this automatically:

1. Before running the tap, Pipe loads the saved state from the bucket (if it exists)
2. The state is passed to the tap via the `--state` flag
3. During extraction, the tap emits `STATE` messages whenever a checkpoint is reached
4. After a successful extraction, Pipe saves the latest state to the bucket

### Enabling incremental extraction

Set `incremental.enabled` to `true` in your pipeline YAML:

```yaml
incremental:
  enabled: true
```

The tap itself must support incremental replication. Consult your tap's documentation to confirm support and to understand which bookmark keys are used.

### Where state is stored

The state file is saved to the bucket at:

```
<bucket>/.dataspoc/state/<pipeline-name>/state.json
```

The state is written atomically (write to temp file, then rename/move) to prevent corruption.

### Forcing a full extraction

To ignore the saved state and re-extract all data:

```bash
dataspoc-pipe run my-pipeline --full
```

This does **not** delete the existing state file. The state will be overwritten with the new state after the full extraction completes successfully.

### Example: incremental PostgreSQL extraction

```yaml
source:
  tap: tap-postgres
  config:
    host: db.example.com
    port: 5432
    user: reader
    password: secret
    dbname: production

destination:
  bucket: s3://my-company-lake
  path: raw
  compression: zstd

incremental:
  enabled: true
```

First run: extracts all data, saves a bookmark (e.g., `replication_key_value: "2026-03-20T00:00:00"`).

Subsequent runs: only extracts records newer than the saved bookmark.

---

## 7. Multi-Cloud Storage

DataSpoc Pipe uses [fsspec](https://filesystem-spec.readthedocs.io/) under the hood, providing a unified interface for multiple storage backends.

### Supported providers

| Provider           | URI prefix | Install command              |
|--------------------|-----------|------------------------------|
| Local filesystem   | `file://`  | (built-in)                   |
| AWS S3             | `s3://`    | `pip install dataspoc-pipe[s3]`    |
| Google Cloud Storage | `gs://`  | `pip install dataspoc-pipe[gcs]`   |
| Azure Blob Storage | `az://`    | `pip install dataspoc-pipe[azure]` |

### Local filesystem

No additional configuration needed. Use `file://` URIs:

```yaml
destination:
  bucket: file:///data/lake
```

### AWS S3

Install the S3 extra:

```bash
pip install dataspoc-pipe[s3]
```

Configure AWS credentials using any standard method:

- **Environment variables**:
  ```bash
  export AWS_ACCESS_KEY_ID=AKIA...
  export AWS_SECRET_ACCESS_KEY=...
  export AWS_DEFAULT_REGION=us-east-1
  ```

- **AWS credentials file** (`~/.aws/credentials`):
  ```ini
  [default]
  aws_access_key_id = AKIA...
  aws_secret_access_key = ...
  ```

- **IAM role** (when running on EC2, ECS, or Lambda): no configuration needed.

- **AWS SSO / CLI profiles**:
  ```bash
  export AWS_PROFILE=my-profile
  ```

Pipeline configuration:

```yaml
destination:
  bucket: s3://my-company-lake
  path: raw
```

### Google Cloud Storage

Install the GCS extra:

```bash
pip install dataspoc-pipe[gcs]
```

Configure credentials using any standard method:

- **Service account JSON**:
  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
  ```

- **gcloud CLI** (for development):
  ```bash
  gcloud auth application-default login
  ```

- **Workload Identity** (on GKE): no configuration needed.

Pipeline configuration:

```yaml
destination:
  bucket: gs://my-company-lake
  path: raw
```

### Azure Blob Storage

Install the Azure extra:

```bash
pip install dataspoc-pipe[azure]
```

Configure credentials using any standard method:

- **Connection string**:
  ```bash
  export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
  ```

- **Account key**:
  ```bash
  export AZURE_STORAGE_ACCOUNT_NAME=myaccount
  export AZURE_STORAGE_ACCOUNT_KEY=...
  ```

- **Azure CLI** (for development):
  ```bash
  az login
  ```

- **Managed Identity** (on Azure VMs or AKS): no configuration needed.

Pipeline configuration:

```yaml
destination:
  bucket: az://my-container
  path: raw
```

---

## 8. Directory Convention

DataSpoc Pipe writes data following a strict directory convention. This convention is a **stable public contract** -- other DataSpoc tools (Lens, ML) and third-party tools rely on it for auto-discovery.

### Bucket structure

```
bucket/
  .dataspoc/
    manifest.json                              # Data catalog
    state/<pipeline>/state.json                # Incremental bookmarks
    logs/<pipeline>/<timestamp>.json            # Execution logs
  raw/
    <source>/<table>/
      dt=YYYY-MM-DD/
        <table>_0000.parquet                   # Data files (Hive-style partitioned)
        <table>_0001.parquet
```

### How paths are built

Given a pipeline with:
- `source.tap`: `tap-postgres`
- `destination.bucket`: `s3://my-lake`
- `destination.path`: `raw`
- A stream named `orders`
- Extraction date: `2026-03-20`

The resulting path is:

```
s3://my-lake/raw/postgres/orders/dt=2026-03-20/orders_0000.parquet
```

The source name is derived from the tap name by removing the `tap-` prefix (e.g., `tap-postgres` becomes `postgres`, `tap-csv` becomes `csv`).

### Partitioning

Data is partitioned by extraction date using Hive-style partitioning (`dt=YYYY-MM-DD`). This enables efficient date-based queries from tools like Apache Spark, DuckDB, Trino, and DataSpoc Lens.

### Batch files

Records are written in batches of approximately 10,000 records per Parquet file. Batch files are numbered sequentially: `<table>_0000.parquet`, `<table>_0001.parquet`, etc.

### manifest.json

The manifest file is the data catalog for the bucket. It is updated after every successful extraction and contains:

```json
{
  "version": "1.0",
  "updated_at": "2026-03-20T08:00:12.456789+00:00",
  "tables": {
    "postgres/orders": {
      "source": "postgres",
      "table": "orders",
      "stats": {
        "total_rows": 150000,
        "extractions": 12,
        "last_extraction": "2026-03-20T08:00:12.456789+00:00",
        "last_extraction_rows": 5000
      }
    }
  }
}
```

### Execution logs

Each pipeline execution produces a JSON log file at:

```
.dataspoc/logs/<pipeline>/<timestamp>.json
```

The timestamp format is `YYYY-MM-DDTHH-MM-SS`. Logs include start/end times, duration, record counts per stream, and error messages (on failure).

---

## 9. Transforms

### What are transforms?

Transforms let you clean, filter, or reshape data during ingestion -- before it is written as Parquet. They are convention-based: if a Python file exists at `~/.dataspoc-pipe/transforms/<pipeline_name>.py`, it runs automatically when you execute `dataspoc-pipe run <pipeline_name>`. No configuration is needed.

### How it works

The transform is applied per batch (~10,000 records) during ingestion, between the Singer tap output and the Parquet write:

```
source → tap → batch → transform(df) [if exists] → Parquet → bucket
```

- If no transform file exists for a pipeline, it runs normally (raw data is written as-is).
- If the transform file exists but fails at runtime, the pipeline continues with raw data and a warning is printed.

### Creating a transform

Create a Python file in `~/.dataspoc-pipe/transforms/` with the same name as the pipeline. The file must define a `transform(df)` function that receives a pandas DataFrame and returns a pandas DataFrame.

**Example**: clean orders during ingestion (`~/.dataspoc-pipe/transforms/orders.py`):

```python
# ~/.dataspoc-pipe/transforms/orders.py
import pandas as pd

def transform(df):
    """Clean orders during ingestion."""
    df = df.drop_duplicates(subset=["order_id"])
    df["email"] = df["email"].str.lower().str.strip()
    df = df[df["order_status"] != "cancelled"]
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df
```

### Directory structure

```
~/.dataspoc-pipe/
  config.yaml
  pipelines/
    orders.yaml          ← pipeline definition
  sources/
    orders.json          ← source config
  transforms/            ← NEW
    orders.py            ← same name as pipeline, runs automatically
```

### Rules

1. **Convention-based** -- the transform file name must match the pipeline name (without `.yaml`).
2. **No config needed** -- just create the `.py` file and it runs on the next `dataspoc-pipe run`.
3. **Function signature** -- the file must define `def transform(df)` that takes and returns a pandas DataFrame.
4. **Per-batch execution** -- the function is called once per batch (~10K records), not once for the entire extraction.
5. **Fail-safe** -- if the transform raises an exception, the batch is written with raw data and a warning is printed. The pipeline does not abort.

### When to use transforms

| Use case | Example |
|----------|---------|
| Remove duplicates | `df.drop_duplicates(subset=["id"])` |
| Normalize text fields | `df["email"] = df["email"].str.lower().str.strip()` |
| Filter out unwanted rows | `df = df[df["status"] != "deleted"]` |
| Parse dates | `df["date"] = pd.to_datetime(df["date"])` |
| Rename columns | `df = df.rename(columns={"old": "new"})` |
| Add computed columns | `df["total"] = df["qty"] * df["price"]` |

### When NOT to use transforms

Transforms are for lightweight cleaning during ingestion. For complex transformations (joins, aggregations, multi-table logic), use DataSpoc Lens transforms instead.

---

## 10. Scheduling

DataSpoc Pipe integrates with the system crontab for scheduled execution. The `python-crontab` package is included as a core dependency -- no extra install is needed.

### Step 1: Add `schedule.cron` to the pipeline YAML

Add the `schedule.cron` field to your pipeline definition:

```yaml
source:
  tap: tap-postgres
  config:
    host: db.example.com
    port: 5432
    user: reader
    password: secret
    dbname: production

destination:
  bucket: s3://my-company-lake
  path: raw
  compression: zstd

incremental:
  enabled: true

schedule:
  cron: "0 */6 * * *"   # Every 6 hours
```

The `schedule.cron` value is a standard five-field cron expression.

### Step 2: Install the cron jobs

```bash
dataspoc-pipe schedule install
```

This reads all pipeline YAML files, and for each one that has a `schedule.cron` value, creates a crontab entry for the current user. Key behaviors:

- **Overlap protection**: each cron entry uses `flock` to prevent overlapping executions of the same pipeline. If a previous run is still in progress, the new invocation is skipped.
- **Idempotent**: running `schedule install` again updates existing entries. If you change a cron expression in the YAML, just run `install` again to apply it -- the old entry is replaced, not duplicated.

### Step 3 (optional): Remove cron jobs

```bash
dataspoc-pipe schedule remove
```

This removes all crontab entries created by DataSpoc Pipe. Only entries identified by the comment prefix `dataspoc-pipe:` are removed; other crontab entries are left untouched.

### Verifying installed schedules

```bash
crontab -l | grep dataspoc-pipe
```

### Common cron expressions

| Expression        | Meaning                            |
|-------------------|------------------------------------|
| `0 * * * *`       | Every hour, at minute 0            |
| `0 */6 * * *`     | Every 6 hours                      |
| `0 2 * * *`       | Daily at 2:00 AM                   |
| `0 0 * * 1`       | Weekly on Monday at midnight       |
| `0 0 1 * *`       | Monthly on the 1st at midnight     |
| `*/30 * * * *`    | Every 30 minutes                   |
| `0 8,20 * * *`    | Twice daily at 8:00 AM and 8:00 PM |
| `0 0 * * 1-5`     | Weekdays at midnight               |

### Dependency: python-crontab

`python-crontab` is a **core dependency** of DataSpoc Pipe and is installed automatically with `pip install dataspoc-pipe`. No extra install step is required.

---

## 11. Troubleshooting

### Tap not found

**Error**: `Tap 'tap-postgres' not found. Install with: pip install tap-postgres`

**Cause**: The Singer tap is not installed or is not on the system PATH.

**Solutions**:
- Install the tap: `pip install tap-postgres`
- Ensure the tap is installed in the same Python environment as DataSpoc Pipe
- Verify with: `which tap-postgres`
- If using a virtual environment, make sure it is activated

---

### Bucket permission denied

**Error**: `Bucket FAILED: s3://my-bucket -- AccessDenied`

**Cause**: Missing or insufficient cloud credentials.

**Solutions**:
- **S3**: Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set, or that the IAM role has `s3:PutObject`, `s3:GetObject`, and `s3:ListBucket` permissions
- **GCS**: Verify `GOOGLE_APPLICATION_CREDENTIALS` points to a valid service account JSON
- **Azure**: Verify `AZURE_STORAGE_CONNECTION_STRING` or account key environment variables are set
- Run `dataspoc-pipe validate <pipeline>` to test connectivity

---

### Local bucket path does not exist

**Error**: Writing fails with a file permission or "No such file or directory" error.

**Cause**: The parent directory in the `file://` URI does not exist.

**Solution**: Create the directory before running:
```bash
mkdir -p /tmp/my-lake
```

---

### Pipeline YAML not found

**Error**: `Pipeline 'my-pipeline' not found in /home/user/.dataspoc-pipe/pipelines/my-pipeline.yaml`

**Cause**: The pipeline file does not exist, or was created with a different name.

**Solutions**:
- Run `dataspoc-pipe init` to create the directory structure
- Check the file name matches exactly (names are case-sensitive)
- List existing pipelines: `ls ~/.dataspoc-pipe/pipelines/`

---

### Invalid YAML configuration

**Cause**: Syntax error in the pipeline YAML file.

**Solutions**:
- Validate YAML syntax (indentation must use spaces, not tabs)
- Ensure required fields (`source.tap`, `source.config`, `destination.bucket`) are present
- Use the `dataspoc-pipe add` wizard to generate a valid configuration

---

### Tap exits with non-zero code

**Error**: `Tap failed (exit code 1): <stderr output>`

**Cause**: The Singer tap encountered an error (connection refused, authentication failure, invalid configuration).

**Solutions**:
- Check the tap's stderr output in the error message for details
- Run the tap manually to debug: `tap-postgres --config config.json`
- Verify the tap configuration (credentials, host, port)
- Check network connectivity to the data source

---

### Missing cloud storage extra

**Error**: `No module named 's3fs'` (or `gcsfs`, `adlfs`)

**Cause**: The cloud storage extra was not installed.

**Solution**: Install the appropriate extra:
```bash
pip install dataspoc-pipe[s3]   # for S3
pip install dataspoc-pipe[gcs]  # for GCS
pip install dataspoc-pipe[azure] # for Azure
```

---

### Schedule install fails

**Error**: `No module named 'crontab'`

**Cause**: The DataSpoc Pipe installation may be incomplete or corrupted.

**Solution**: Reinstall DataSpoc Pipe, which includes `python-crontab` as a core dependency:
```bash
pip install --force-reinstall dataspoc-pipe
```

---

## 12. Practical Examples

### Example 1: CSV files to local bucket

Extract data from local CSV files and store as Parquet on the local filesystem.

**Install the tap**:
```bash
pip install tap-csv
```

**Pipeline file** (`~/.dataspoc-pipe/pipelines/local-csv.yaml`):

```yaml
source:
  tap: tap-csv
  config:
    files:
      - entity: customers
        path: /data/exports/customers.csv
        keys:
          - customer_id
      - entity: products
        path: /data/exports/products.csv
        keys:
          - sku

destination:
  bucket: file:///data/lake
  path: raw
  compression: snappy

incremental:
  enabled: false
```

**Run**:
```bash
dataspoc-pipe run local-csv
```

**Result**:
```
/data/lake/
  .dataspoc/
    manifest.json
    logs/local-csv/2026-03-20T08-00-00.json
  raw/
    csv/customers/dt=2026-03-20/customers_0000.parquet
    csv/products/dt=2026-03-20/products_0000.parquet
```

---

### Example 2: PostgreSQL to AWS S3

Extract data from a PostgreSQL database with incremental extraction, scheduled every 6 hours.

**Install dependencies**:
```bash
pip install dataspoc-pipe[s3] tap-postgres
```

**Configure AWS credentials**:
```bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

**Pipeline file** (`~/.dataspoc-pipe/pipelines/production-db.yaml`):

```yaml
source:
  tap: tap-postgres
  config:
    host: db.mycompany.com
    port: 5432
    user: dataspoc_reader
    password: ${DB_PASSWORD}
    dbname: production
    filter_schemas:
      - public
  streams:
    - orders
    - customers
    - line_items

destination:
  bucket: s3://mycompany-data-lake
  path: raw
  compression: zstd

incremental:
  enabled: true

schedule:
  cron: "0 */6 * * *"
```

**Validate**:
```bash
dataspoc-pipe validate production-db
```

**Run manually (first time)**:
```bash
dataspoc-pipe run production-db
```

**Install the schedule**:
```bash
dataspoc-pipe schedule install
```

**Result** (after first run):
```
s3://mycompany-data-lake/
  .dataspoc/
    manifest.json
    state/production-db/state.json
    logs/production-db/2026-03-20T08-00-00.json
  raw/
    postgres/orders/dt=2026-03-20/orders_0000.parquet
    postgres/customers/dt=2026-03-20/customers_0000.parquet
    postgres/line_items/dt=2026-03-20/line_items_0000.parquet
```

Subsequent runs will only extract records newer than the bookmark saved in `state.json`.

---

### Example 3: GitHub API to Google Cloud Storage

Extract repository data from the GitHub API and store it in GCS.

**Install dependencies**:
```bash
pip install dataspoc-pipe[gcs] tap-github
```

**Configure GCS credentials**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

**Pipeline file** (`~/.dataspoc-pipe/pipelines/github-data.yaml`):

```yaml
source:
  tap: tap-github
  config:
    access_token: ghp_xxxxxxxxxxxxxxxxxxxx
    repository: myorg/myrepo
  streams:
    - commits
    - pull_requests
    - issues

destination:
  bucket: gs://mycompany-data-lake
  path: raw
  compression: zstd

incremental:
  enabled: true

schedule:
  cron: "0 2 * * *"
```

**Run**:
```bash
dataspoc-pipe run github-data
```

**Result**:
```
gs://mycompany-data-lake/
  .dataspoc/
    manifest.json
    state/github-data/state.json
    logs/github-data/2026-03-20T02-00-00.json
  raw/
    github/commits/dt=2026-03-20/commits_0000.parquet
    github/pull_requests/dt=2026-03-20/pull_requests_0000.parquet
    github/issues/dt=2026-03-20/issues_0000.parquet
```

**Check the catalog**:
```bash
dataspoc-pipe manifest gs://mycompany-data-lake
```

---

## 13. Part of the DataSpoc Platform

DataSpoc Pipe is the ingestion layer of the DataSpoc platform, a Brazilian open-source data platform built for simplicity.

### The three components

| Product            | Role         | Description                                           | License       |
|--------------------|--------------|-------------------------------------------------------|---------------|
| **DataSpoc Pipe**  | Ingestion    | Singer taps to Parquet to bucket (this tool)          | Open-source (Apache 2.0)  |
| **DataSpoc Lens**  | Query engine | Virtual warehouse: SQL + Jupyter + AI over your lake  | Open-source   |
| **DataSpoc ML**    | Machine learning | AutoML: train models directly from your lake      | Commercial    |

### The bucket is the contract

The three products communicate through the bucket using the directory convention described in [section 8](#8-directory-convention):

- **Pipe writes** -- extracts data from sources and writes Parquet files following the convention
- **Lens reads** -- auto-discovers tables via `manifest.json` and the Hive-style partitioning
- **ML consumes and produces** -- reads training data from the lake and writes model artifacts back

This means you can start with Pipe alone for ingestion, add Lens when you need SQL queries and notebooks, and bring in ML when you are ready for machine learning -- all working on the same bucket, no data movement required.

### Getting started with the full platform

1. Use **DataSpoc Pipe** to ingest data into your bucket (you are here)
2. Point **DataSpoc Lens** at the same bucket to query your data with SQL
3. Use **DataSpoc ML** to train models on your lake data

---

## Quick Reference Card

```bash
# Setup
dataspoc-pipe init                          # Initialize config structure
dataspoc-pipe add <name>                    # Create pipeline (wizard)

# Execution
dataspoc-pipe run <name>                    # Run a pipeline
dataspoc-pipe run <name> --full             # Run ignoring incremental state
dataspoc-pipe run <name> --all              # Run all pipelines

# Monitoring
dataspoc-pipe status                        # Status table for all pipelines
dataspoc-pipe logs <name>                   # Last execution log (JSON)
dataspoc-pipe manifest <bucket>             # Data catalog

# Validation
dataspoc-pipe validate [name]               # Test bucket and tap connectivity

# Scheduling
dataspoc-pipe schedule install              # Install cron jobs
dataspoc-pipe schedule remove               # Remove cron jobs

# Info
dataspoc-pipe --version                     # Show version
dataspoc-pipe --help                        # Show help
```
