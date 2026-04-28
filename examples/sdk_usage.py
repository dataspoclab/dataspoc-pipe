"""Example: Using the DataSpoc Pipe Python SDK."""

from dataspoc_pipe import PipeClient

client = PipeClient()

# 1. List pipelines
pipelines = client.pipelines()
print("Pipelines:", pipelines)

# 2. Check status
for s in client.status():
    print(f"  {s['name']}: {s['status']} ({s['records']} records)")

# 3. Run a pipeline
result = client.run("sales-data")
if result["success"]:
    print(f"\nSuccess! Streams: {result['streams']}")
else:
    print(f"\nFailed: {result['error']}")

# 4. View logs
log = client.logs("sales-data")
if log:
    print(f"\nLast run: {log.get('started_at', 'N/A')}")
    print(f"Duration: {log.get('duration_seconds', 0):.1f}s")
    print(f"Records: {log.get('total_records', 0)}")

# 5. View manifest
manifest = client.manifest("s3://my-bucket")
for table_key, table_info in manifest.get("tables", {}).items():
    print(f"  {table_key}: {table_info.get('stats', {}).get('total_rows', 0)} rows")
