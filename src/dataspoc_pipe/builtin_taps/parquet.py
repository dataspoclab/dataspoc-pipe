#!/usr/bin/env python3
"""Built-in tap: reads Parquet files from local or cloud storage.

Emits Singer protocol messages (SCHEMA, RECORD, STATE) from Parquet files.
Used for raw → curated pipelines (second stage of the data lake).

Usage:
    python -m dataspoc_pipe.builtin_taps.parquet --config config.json

Config:
    {
        "path": "s3://bucket/raw/postgres/orders",
        "stream_name": "orders",
        "glob": "**/*.parquet"
    }

The path can be local (file://) or cloud (s3://, gs://, az://).
"""

import argparse
import json
import sys

import pyarrow.parquet as pq


def _arrow_type_to_json_schema(arrow_type) -> str:
    """Convert PyArrow type to JSON Schema type string."""
    t = str(arrow_type)
    if "int" in t:
        return "integer"
    elif "float" in t or "double" in t:
        return "number"
    elif "bool" in t:
        return "boolean"
    elif "timestamp" in t:
        return "string"
    elif "date" in t:
        return "string"
    else:
        return "string"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--state", required=False)
    parser.add_argument("--catalog", required=False)
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    path = config["path"].rstrip("/")
    stream_name = config.get("stream_name", config.get("name", "table"))
    glob_pattern = config.get("glob", "**/*.parquet")

    # Discover Parquet files
    import fsspec

    if path.startswith(("s3://", "gs://", "az://")):
        fs, base = fsspec.core.url_to_fs(path)
        full_pattern = f"{base}/{glob_pattern}"
        files = fs.glob(full_pattern)
        if not files:
            # Try without glob (single file or flat dir)
            files = fs.glob(f"{base}/*.parquet")
        # Add scheme back
        scheme = path.split("://")[0]
        files = [f"{scheme}://{f}" for f in files]
    elif path.startswith("file://"):
        from pathlib import Path as P
        local_path = P(path[7:])
        files = [str(f) for f in local_path.rglob("*.parquet")]
    else:
        from pathlib import Path as P
        local_path = P(path)
        files = [str(f) for f in local_path.rglob("*.parquet")]

    if not files:
        print(f"ERROR: No Parquet files found at {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} Parquet file(s)", file=sys.stderr)

    # Read schema from first file
    try:
        if files[0].startswith(("s3://", "gs://", "az://")):
            schema = pq.read_schema(files[0], filesystem=fs)
        else:
            schema = pq.read_schema(files[0])
    except Exception as e:
        print(f"ERROR: Cannot read schema from {files[0]}: {e}", file=sys.stderr)
        sys.exit(1)

    # Emit SCHEMA
    properties = {}
    for field in schema:
        json_type = _arrow_type_to_json_schema(field.type)
        if field.nullable:
            properties[field.name] = {"type": ["null", json_type]}
        else:
            properties[field.name] = {"type": json_type}

    schema_msg = {
        "type": "SCHEMA",
        "stream": stream_name,
        "schema": {"properties": properties},
        "key_properties": [],
    }
    print(json.dumps(schema_msg))

    # Emit RECORDS from all files
    total = 0
    for filepath in files:
        try:
            if filepath.startswith(("s3://", "gs://", "az://")):
                table = pq.read_table(filepath, filesystem=fs)
            else:
                table = pq.read_table(filepath)

            for batch in table.to_batches(max_chunksize=5000):
                df = batch.to_pandas()
                for _, row in df.iterrows():
                    record = {}
                    for col in df.columns:
                        val = row[col]
                        # Convert numpy/pandas types to Python native
                        if hasattr(val, 'item'):
                            val = val.item()
                        elif hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        elif val is None or (hasattr(val, '__class__') and 'NaT' in str(type(val))):
                            val = None
                        record[col] = val

                    record_msg = {
                        "type": "RECORD",
                        "stream": stream_name,
                        "record": record,
                    }
                    print(json.dumps(record_msg, default=str))
                    total += 1

        except Exception as e:
            print(f"WARNING: Failed to read {filepath}: {e}", file=sys.stderr)
            continue

    # Emit STATE
    state_msg = {
        "type": "STATE",
        "value": {"bookmarks": {stream_name: {"files_read": len(files), "total_records": total}}},
    }
    print(json.dumps(state_msg))

    print(f"Emitted {total} records from {len(files)} file(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
