#!/usr/bin/env python3
"""Mock Singer tap that reads a CSV file and emits Singer protocol messages.

Usage:
    python mock_tap_csv.py --config config.json

Config JSON format:
    {"csv_path": "/path/to/file.csv", "stream_name": "my_table"}

The stream_name field is optional and defaults to the CSV filename (without extension).
"""

import argparse
import csv
import json
import signal
import sys
from pathlib import Path

# Handle SIGPIPE gracefully (e.g. when piped to head)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def infer_type(value: str) -> str | None:
    """Infer JSON Schema type from a string value. Returns None for empty."""
    if value == "":
        return None
    # Try integer
    try:
        int(value)
        return "integer"
    except ValueError:
        pass
    # Try float
    try:
        float(value)
        return "number"
    except ValueError:
        pass
    # Boolean
    if value.lower() in ("true", "false"):
        return "boolean"
    return "string"


def cast_value(value: str, json_type: str):
    """Cast a string value to the appropriate Python type."""
    if value == "":
        return None
    if json_type == "integer":
        try:
            return int(value)
        except ValueError:
            return None
    if json_type == "number":
        try:
            return float(value)
        except ValueError:
            return None
    if json_type == "boolean":
        return value.lower() == "true"
    return value


def infer_schema(rows: list[dict], headers: list[str]) -> dict[str, str]:
    """Infer JSON Schema types by sampling rows."""
    type_counts: dict[str, dict[str, int]] = {h: {} for h in headers}

    sample = rows[:200]  # sample first 200 rows
    for row in sample:
        for h in headers:
            val = row.get(h, "")
            t = infer_type(val)
            if t is not None:
                type_counts[h][t] = type_counts[h].get(t, 0) + 1

    result = {}
    for h in headers:
        counts = type_counts[h]
        if not counts:
            result[h] = "string"
            continue
        # Pick the most specific numeric type if no string values found
        non_string = {k: v for k, v in counts.items() if k != "string"}
        if non_string and not counts.get("string", 0):
            result[h] = max(non_string, key=non_string.get)
        else:
            result[h] = "string"
    return result


def main():
    parser = argparse.ArgumentParser(description="Mock Singer tap for CSV files")
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    parser.add_argument("--state", default=None, help="Path to state JSON file (ignored)")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    csv_path = config["csv_path"]
    stream_name = config.get("stream_name", Path(csv_path).stem)
    # Sanitize stream name for use as table name
    stream_name = stream_name.replace("-", "_").replace(" ", "_").lower()

    # Read CSV
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    if not headers:
        print("No headers found in CSV", file=sys.stderr)
        sys.exit(1)

    # Infer types
    col_types = infer_schema(rows, headers)

    # Emit SCHEMA
    properties = {}
    for h in headers:
        t = col_types.get(h, "string")
        properties[h] = {"type": ["null", t]}

    schema_msg = {
        "type": "SCHEMA",
        "stream": stream_name,
        "schema": {
            "type": "object",
            "properties": properties,
        },
        "key_properties": [],
    }
    print(json.dumps(schema_msg))

    # Emit RECORD for each row
    for row in rows:
        record = {}
        for h in headers:
            record[h] = cast_value(row.get(h, ""), col_types.get(h, "string"))

        record_msg = {
            "type": "RECORD",
            "stream": stream_name,
            "record": record,
        }
        print(json.dumps(record_msg))

    # Emit STATE
    state_msg = {
        "type": "STATE",
        "value": {"completed": True, "rows": len(rows)},
    }
    print(json.dumps(state_msg))


if __name__ == "__main__":
    main()
