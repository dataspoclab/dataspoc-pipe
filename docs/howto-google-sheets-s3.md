# Tutorial: Google Sheets → Data Lake → SQL Analysis

From a spreadsheet to querying your data with SQL in 30 minutes.

```
Google Sheets → DataSpoc Pipe → Parquet in S3 → DataSpoc Lens → SQL + Jupyter + AI
```


---

## What is DataSpoc?

DataSpoc is a Brazilian open-source data platform with 3 products:

| Product | What it does | Cost |
|---------|-------------|------|
| **Pipe** | Ingests data from any source → Parquet in cloud | Free |
| **Lens** | SQL + Jupyter + AI over your cloud data | Free |
| **ML** | AutoML with automatic feature engineering | Paid |

This tutorial uses Pipe (ingest) and Lens (analysis).

---

# Part 1: DataSpoc Pipe — Ingest the spreadsheet

Everything you need to get data from Google Sheets into your S3 data lake.

## 1.1 Install Pipe

```bash
pip install dataspoc-pipe[s3]
```

<details><summary>Install from source (development)</summary>

```bash
git clone https://github.com/dataspoclab/dataspoc-pipe.git
cd dataspoc-pipe
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[s3]"
```

</details>

Verify:
```bash
dataspoc-pipe --version
```

## 1.2 Configure AWS credentials

Pipe needs **write** access to your S3 bucket.

Via environment variables:
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

Or via `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key
region = us-east-1
```

Verify access:
```bash
python -c "import s3fs; fs = s3fs.S3FileSystem(); print(fs.ls('your-bucket/'))"
```

## 1.3 Initialize Pipe

```bash
dataspoc-pipe init
```

Creates:
```
~/.dataspoc-pipe/
  config.yaml       ← global defaults
  pipelines/        ← pipeline definitions (1 YAML per pipeline)
  sources/          ← source configs (1 JSON per source)
  transforms/       ← optional Python transforms (same name as pipeline)
```

## 1.4 Create the pipeline

```bash
dataspoc-pipe add my-sheet
```

The wizard shows available taps and asks for configuration:

```
Taps with template: google-sheets-public, tap-csv, tap-github,
                    tap-google-sheets, tap-mongodb, tap-mysql,
                    tap-postgres, tap-rest-api, tap-s3-csv,
                    tap-salesforce

Tap Singer: google-sheets-public
Template found for google-sheets-public
Source config: ~/.dataspoc-pipe/sources/my-sheet.json

Bucket: s3://your-bucket
Path [raw]: raw
Compression [zstd]: zstd
Enable incremental? [n]: n
Cron expression []:

Pipeline saved: ~/.dataspoc-pipe/pipelines/my-sheet.yaml

Next steps:
  1. Edit source config: ~/.dataspoc-pipe/sources/my-sheet.json
  2. Validate: dataspoc-pipe validate my-sheet
  3. Run: dataspoc-pipe run my-sheet
```

This creates two files:

**Pipeline** (`~/.dataspoc-pipe/pipelines/my-sheet.yaml`):
```yaml
source:
  tap: google-sheets-public
  config: /home/user/.dataspoc-pipe/sources/my-sheet.json
destination:
  bucket: s3://your-bucket
  path: raw
  compression: zstd
incremental:
  enabled: false
```

**Source config** (`~/.dataspoc-pipe/sources/my-sheet.json`):
```json
{
  "url": "PASTE_SPREADSHEET_URL_HERE",
  "sheet_name": "sheet"
}
```

## 1.5 Edit the source config

Open `~/.dataspoc-pipe/sources/my-sheet.json` and paste the full Google Sheets URL:

```json
{
  "url": "https://docs.google.com/spreadsheets/d/Y0000_000000000000000000000000000_0000000000/edit?gid=0#gid=0",
  "sheet_name": "orders"
}
```

How to get the URL:
1. Open the spreadsheet in Google Sheets
2. Copy the full URL from the browser address bar
3. Paste it in the `url` field

Requirements:
- The spreadsheet must be **public**: Share → Anyone with the link → Viewer
- The `sheet_name` is how the table will appear in the data lake
- The `gid` (sheet tab) is extracted automatically from the URL

## 1.6 Validate

```bash
dataspoc-pipe validate my-sheet
```

```
Validating: my-sheet
  Bucket OK: s3://your-bucket
  Tap OK: google-sheets-public (built-in)
```

## 1.7 Run

```bash
dataspoc-pipe run my-sheet
```

```
Running: my-sheet
  orders: 9,144 records...
Done! 9,144 records in 1 stream(s)
  orders: 9,144
```

What happened:
1. Downloaded the spreadsheet as CSV (via Google export URL)
2. Inferred column types (integer, float, string)
3. Converted to Parquet with zstd compression
4. Uploaded to `s3://your-bucket/raw/google-sheets-public/orders/`
5. Updated the manifest at `s3://your-bucket/.dataspoc/manifest.json`

## 1.8 Verify

```bash
# Catalog
dataspoc-pipe manifest s3://your-bucket

# Pipeline status
dataspoc-pipe status

# Execution logs
dataspoc-pipe logs my-sheet
```

Your data lake in S3:
```
s3://your-bucket/
  .dataspoc/
    manifest.json                           ← catalog (tables, schemas, timestamps)
    logs/my-sheet/2026-03-24T14-30-00.json  ← execution log
  raw/
    google-sheets-public/
      orders/
        orders_0000.parquet                  ← your data in Parquet
```

## 1.9 Transform (optional — clean data during ingestion)

You can clean or reshape data before it lands in the lake by creating a transform file. No config changes needed -- just create a Python file with the same name as the pipeline.

Create `~/.dataspoc-pipe/transforms/my-sheet.py`:

```python
# ~/.dataspoc-pipe/transforms/my-sheet.py
import pandas as pd

def transform(df):
    """Clean orders before writing to the lake."""
    # Normalize emails
    df["Email (Billing)"] = df["Email (Billing)"].str.lower().str.strip()

    # Remove cancelled orders
    df = df[df["Order Status"] != "cancelled"]

    # Parse dates
    df["Order Date"] = pd.to_datetime(df["Order Date"])

    # Drop duplicates
    df = df.drop_duplicates(subset=["Order Number"])

    return df
```

Next time you run the pipeline, the transform runs automatically per batch:

```bash
dataspoc-pipe run my-sheet
```

```
Running: my-sheet
  orders: 9,144 records (transform: my-sheet.py)...
Done! 8,210 records in 1 stream(s)
  orders: 8,210
```

The flow becomes:

```
Google Sheets → tap → batch → transform(df) → Parquet → S3
```

If the transform file does not exist, the pipeline runs normally with raw data. If the transform fails, the pipeline continues with raw data and prints a warning.

## 1.10 Schedule (automatic runs)

To run the pipeline automatically, add a cron expression to the pipeline YAML:

```bash
# Edit the pipeline
nano ~/.dataspoc-pipe/pipelines/my-sheet.yaml
```

Add the `schedule` section:
```yaml
source:
  tap: google-sheets-public
  config: /home/user/.dataspoc-pipe/sources/my-sheet.json
destination:
  bucket: s3://your-bucket
  path: raw
  compression: zstd
incremental:
  enabled: false
schedule:
  cron: "0 8 * * *"     # every day at 8:00 AM
```

Common cron expressions:

| Expression | Meaning |
|-----------|---------|
| `0 * * * *` | Every hour |
| `0 8 * * *` | Every day at 8 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 8 * * 1` | Every Monday at 8 AM |
| `0 0 1 * *` | First day of each month |

Install the schedule:
```bash
dataspoc-pipe schedule install
```

```
Installed: my-sheet (0 8 * * *)
1 schedule(s) installed.
```

Verify:
```bash
crontab -l | grep dataspoc
# 0 8 * * * flock -n /tmp/dataspoc-pipe-my-sheet.lock dataspoc-pipe run my-sheet # dataspoc-pipe:my-sheet
```

The schedule uses `flock` to prevent overlapping runs — if a pipeline is still running when the next one triggers, it skips.

To update, edit the YAML and run `schedule install` again — it replaces the old entry.

To remove:
```bash
dataspoc-pipe schedule remove
```

---

---

# Next: Query your data with DataSpoc Lens

Your data is now in S3 as Parquet. Use DataSpoc Lens to query it with SQL, notebooks, and AI.

**→ [How-To: Query a Data Lake on S3](https://github.com/dataspoclab/dataspoc-lens/blob/main/docs/howto-query-s3-lake.md)**

Quick preview:
```bash
pip install dataspoc-lens[s3]
dataspoc-lens init
dataspoc-lens add-bucket s3://your-bucket
dataspoc-lens shell
sql> SELECT * FROM orders LIMIT 10;
```
