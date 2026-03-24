# How-To: Multi-Stage Data Lake with Permission Layers

Build a production-ready data lake: Bronze (raw) → Silver (curated per team) → Gold (analyst reports).

```
Sources → Pipe (ingest) → Bronze → Pipe (transform) → Silver → Lens (analyze) → Gold
```

---

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────────────────────┐
│  SOURCES    │     │  BRONZE (raw)        │     │  SILVER (curated per team)   │
│             │     │  s3://company-bronze │     │                              │
│  Postgres   │────▶│    /raw/postgres/    │     │  s3://company-finance        │
│  Google     │────▶│    /raw/sheets/      │────▶│    /curated/revenue/         │
│  API        │────▶│    /raw/api/         │     │    /curated/costs/           │
│             │     │                      │     │                              │
│             │     │                      │     │  s3://company-hr             │
│             │     │                      │     │    /curated/headcount/       │
│             │     │                      │     │                              │
│             │     │                      │     │  s3://company-product        │
│             │     │                      │     │    /curated/events/          │
└─────────────┘     └──────────────────────┘     └──────────────────────────────┘

  Pipe (ingest)          Pipe (transform)              Lens (analyze)
  source → raw           raw → curated                 curated → gold
  Singer taps            Python transforms             SQL transforms
```

### Who does what

| Role | Tool | Access | Responsibility |
|------|------|--------|---------------|
| **Data Engineer** | Pipe | Write bronze, write silver | Ingest sources, build transforms |
| **Finance Analyst** | Lens | Read finance silver only | Query, reports, gold layer |
| **HR Analyst** | Lens | Read HR silver only | Query, reports |
| **Product Analyst** | Lens | Read product silver only | Query, dashboards |
| **Manager** | Lens | Read their team's silver | AI ask, notebooks |

### Three layers

| Layer | Tool | Who | Automated |
|-------|------|-----|-----------|
| **Raw (Bronze)** | Pipe ingest | DE | Cron |
| **Curated (Silver)** | Pipe transform | DE | Cron |
| **Gold** | Lens transform | Analyst | On demand |

---

## Prerequisites

- DataSpoc Pipe and Lens installed
- AWS credentials
- 4 S3 buckets:
  - `s3://company-bronze` — raw data (DE only)
  - `s3://company-finance` — finance team
  - `s3://company-hr` — HR team
  - `s3://company-product` — product team

---

# Stage 1: Bronze — Ingest sources into raw

The DE uses Pipe to ingest from external sources into the bronze bucket.

## 1.1 Setup ingest pipelines

```bash
dataspoc-pipe init

# Source 1: Google Sheets (sales data)
dataspoc-pipe add sales-sheet
# → Tap: google-sheets-public
# → Bucket: s3://company-bronze

# Source 2: Postgres (customers, orders)
dataspoc-pipe add customers-db
# → Tap: tap-postgres
# → Bucket: s3://company-bronze

# Source 3: REST API (product events)
dataspoc-pipe add product-events
# → Tap: tap-rest-api
# → Bucket: s3://company-bronze
```

## 1.2 Edit source configs

```bash
# ~/.dataspoc-pipe/sources/sales-sheet.json
{
  "url": "https://docs.google.com/spreadsheets/d/.../edit?gid=0",
  "sheet_name": "sales"
}

# ~/.dataspoc-pipe/sources/customers-db.json
{
  "host": "db.company.com",
  "port": 5432,
  "user": "readonly",
  "password": "...",
  "dbname": "production",
  "filter_schemas": "public"
}
```

## 1.3 Run ingest

```bash
dataspoc-pipe run sales-sheet
dataspoc-pipe run customers-db
dataspoc-pipe run product-events
```

Bronze result:
```
s3://company-bronze/
  .dataspoc/manifest.json
  raw/
    google-sheets-public/sales/sales_0000.parquet
    postgres/customers/customers_0000.parquet
    postgres/orders/orders_0000.parquet
    rest-api/events/events_0000.parquet
```

---

# Stage 2: Silver — Transform raw into team buckets

The DE creates **new pipelines** that read from bronze (Parquet) and write to each team's silver bucket, with Python transforms.

## 2.1 Create silver pipelines

Each silver pipeline uses the built-in `parquet` tap to read from bronze:

```bash
# Finance silver: orders + customers → revenue, costs
dataspoc-pipe add finance-orders
# → Tap: parquet
# → Bucket: s3://company-finance

dataspoc-pipe add finance-customers
# → Tap: parquet
# → Bucket: s3://company-finance

# HR silver: customers → headcount by region
dataspoc-pipe add hr-headcount
# → Tap: parquet
# → Bucket: s3://company-hr

# Product silver: events → daily aggregates
dataspoc-pipe add product-events-daily
# → Tap: parquet
# → Bucket: s3://company-product
```

## 2.2 Edit source configs (point to bronze)

```bash
# ~/.dataspoc-pipe/sources/finance-orders.json
{
  "path": "s3://company-bronze/raw/postgres/orders",
  "stream_name": "orders"
}

# ~/.dataspoc-pipe/sources/finance-customers.json
{
  "path": "s3://company-bronze/raw/postgres/customers",
  "stream_name": "customers"
}

# ~/.dataspoc-pipe/sources/hr-headcount.json
{
  "path": "s3://company-bronze/raw/postgres/customers",
  "stream_name": "customers"
}

# ~/.dataspoc-pipe/sources/product-events-daily.json
{
  "path": "s3://company-bronze/raw/rest-api/events",
  "stream_name": "events"
}
```

## 2.3 Create transforms (Python)

Each transform cleans and shapes the data for its team:

```bash
mkdir -p ~/.dataspoc-pipe/transforms
```

### Finance transform

```python
# ~/.dataspoc-pipe/transforms/finance-orders.py
import pandas as pd

def transform(df):
    """Clean orders for finance team."""
    # Only completed orders
    df = df[df["order_status"] == "completed"].copy()

    # Clean dates
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["month"] = df["order_date"].dt.to_period("M").astype(str)

    # Clean amounts
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0)

    # Remove PII (finance doesn't need emails)
    df = df.drop(columns=["email", "phone"], errors="ignore")

    return df
```

### HR transform

```python
# ~/.dataspoc-pipe/transforms/hr-headcount.py

def transform(df):
    """Aggregate customers by region for HR analysis."""
    # Group by region
    result = df.groupby(["region", "city"]).agg(
        total_customers=("id", "count"),
        first_signup=("created_at", "min"),
        last_signup=("created_at", "max"),
    ).reset_index()

    return result
```

### Product transform

```python
# ~/.dataspoc-pipe/transforms/product-events-daily.py
import pandas as pd

def transform(df):
    """Aggregate events daily for product team."""
    df["event_date"] = pd.to_datetime(df["event_timestamp"]).dt.date

    result = df.groupby(["event_date", "event_type"]).agg(
        event_count=("event_type", "count"),
        unique_users=("user_id", "nunique"),
    ).reset_index()

    return result
```

## 2.4 Run silver pipelines

```bash
dataspoc-pipe run finance-orders
dataspoc-pipe run finance-customers
dataspoc-pipe run hr-headcount
dataspoc-pipe run product-events-daily
```

Output:
```
Running: finance-orders
  orders: 200,000 raw → 185,000 after transform
Done! 185,000 records in 1 stream(s)

Running: hr-headcount
  customers: 10,000 raw → 350 after transform
Done! 350 records in 1 stream(s)
```

Silver result:
```
s3://company-finance/
  .dataspoc/manifest.json
  raw/parquet/orders/orders_0000.parquet          ← cleaned orders
  raw/parquet/customers/customers_0000.parquet    ← cleaned customers

s3://company-hr/
  .dataspoc/manifest.json
  raw/parquet/customers/customers_0000.parquet    ← aggregated headcount

s3://company-product/
  .dataspoc/manifest.json
  raw/parquet/events/events_0000.parquet          ← daily aggregates
```

---

# Stage 3: Analysts query their silver data with Lens

Each analyst only has AWS credentials for their team's bucket.

## Finance analyst

```bash
dataspoc-lens init
dataspoc-lens add-bucket s3://company-finance
dataspoc-lens catalog
dataspoc-lens setup-ai            # one-time: install local AI (Ollama)

dataspoc-lens shell
sql> .tables
orders
customers

sql> SELECT month, SUM(total_amount) as revenue
     FROM orders GROUP BY month ORDER BY month DESC;

sql> .quit

# AI query
dataspoc-lens ask "what was the revenue trend in the last 6 months?"

# Export for report
dataspoc-lens query "SELECT * FROM orders WHERE month >= '2026-01'" --export q1.csv
```

## HR analyst

```bash
dataspoc-lens init
dataspoc-lens add-bucket s3://company-hr
dataspoc-lens setup-ai

dataspoc-lens ask "which regions have the most customers?"
```

## Product analyst

```bash
dataspoc-lens init
dataspoc-lens add-bucket s3://company-product

dataspoc-lens notebook --marimo
# Explore events interactively
```

## Gold layer (analyst transforms with Lens)

The analyst can create SQL transforms to build gold metrics:

```sql
-- ~/.dataspoc-lens/transforms/001_weekly_metrics.sql
COPY (
    SELECT event_date,
           SUM(CASE WHEN event_type = 'purchase' THEN event_count END) as purchases,
           SUM(unique_users) as wau
    FROM events
    GROUP BY event_date
) TO 's3://company-product/gold/weekly_metrics/data.parquet' (FORMAT PARQUET);
```

```bash
dataspoc-lens transform run
```

---

# Automation

## Schedule everything with cron

```yaml
# ~/.dataspoc-pipe/pipelines/sales-sheet.yaml
schedule:
  cron: "0 6 * * *"     # 6 AM: ingest sources

# ~/.dataspoc-pipe/pipelines/finance-orders.yaml
schedule:
  cron: "30 6 * * *"    # 6:30 AM: transform to silver (after ingest)
```

```bash
dataspoc-pipe schedule install
```

Full pipeline:
```
06:00  Pipe ingest → sources → s3://company-bronze/raw/
06:30  Pipe transform → bronze → silver buckets
       Analysts query anytime → Lens → silver data
```

---

# AWS IAM setup

### DE (full access)
```json
{
  "Effect": "Allow",
  "Action": ["s3:*"],
  "Resource": [
    "arn:aws:s3:::company-bronze/*",
    "arn:aws:s3:::company-finance/*",
    "arn:aws:s3:::company-hr/*",
    "arn:aws:s3:::company-product/*"
  ]
}
```

### Finance analyst (read finance only)
```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::company-finance",
    "arn:aws:s3:::company-finance/*"
  ]
}
```

---

# Summary

| Stage | Pipeline | Source | Destination | Transform | Schedule |
|-------|----------|-------|-------------|-----------|----------|
| **Ingest** | sales-sheet | Google Sheets | bronze/raw/ | — | 6:00 AM |
| **Ingest** | customers-db | Postgres | bronze/raw/ | — | 6:00 AM |
| **Ingest** | product-events | REST API | bronze/raw/ | — | 6:00 AM |
| **Curate** | finance-orders | bronze (parquet) | finance/curated/ | Python: clean, remove PII | 6:30 AM |
| **Curate** | hr-headcount | bronze (parquet) | hr/curated/ | Python: aggregate by region | 6:30 AM |
| **Curate** | product-events-daily | bronze (parquet) | product/curated/ | Python: daily aggregates | 6:30 AM |
| **Gold** | Lens transforms | silver (curated) | gold/ | SQL: metrics, reports | On demand |

```bash
# DE: full pipeline
dataspoc-pipe run --all              # ingest + transform (by schedule)

# Analyst: query silver
dataspoc-lens add-bucket s3://my-team
dataspoc-lens ask "my question"
```

---

## Related

- **Lens: Query your silver data** → [howto-query-s3-lake](https://github.com/dataspoclab/dataspoc-lens/blob/main/docs/howto-query-s3-lake.md)
- **Lens: Explore with AI** → [howto-explore-with-ai](https://github.com/dataspoclab/dataspoc-lens/blob/main/docs/howto-explore-with-ai.md)
- **Pipe: Simple ingest** → [howto-google-sheets-s3](howto-google-sheets-s3.md)
