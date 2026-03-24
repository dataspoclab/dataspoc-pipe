# DataSpoc E2E Demo

End-to-end demonstration of the DataSpoc platform: download a real dataset, ingest it with DataSpoc Pipe, then analyze it with DataSpoc Lens.

## What it does

1. Downloads the Iris dataset (150 rows, 5 columns) from GitHub
2. Feeds it through a mock Singer tap (`mock_tap_csv.py`) into DataSpoc Pipe
3. Pipe converts it to Parquet and writes it to a local file-based lake
4. Lens registers the lake bucket, discovers tables, and runs SQL queries
5. Exports query results to CSV and JSON

## Prerequisites

- Python 3.10+
- DataSpoc Pipe and Lens installed (or importable via PYTHONPATH)
- Internet access (to download the dataset)

## Running

```bash
cd /home/sanmartim/fontes/ds/dataspoc
source .venv/bin/activate
bash examples/e2e-demo.sh
```

## Files

| File | Description |
|------|-------------|
| `e2e-demo.sh` | Main demo script |
| `mock_tap_csv.py` | Mock Singer tap that reads any CSV and emits Singer protocol messages |

## Mock tap standalone usage

```bash
# Create a config file
echo '{"csv_path": "/path/to/data.csv", "stream_name": "my_table"}' > config.json

# Run the tap (outputs Singer messages to stdout)
python examples/mock_tap_csv.py --config config.json
```
