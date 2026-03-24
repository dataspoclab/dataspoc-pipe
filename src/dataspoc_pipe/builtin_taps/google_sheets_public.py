#!/usr/bin/env python3
"""Built-in tap: Google Sheets (public links).

Reads a public Google Sheets spreadsheet via CSV export URL.
No OAuth needed — only works with publicly shared spreadsheets.

Usage:
    python -m dataspoc_pipe.builtin_taps.google_sheets_public --config config.json

Config:
    {
        "spreadsheet_id": "1BxiMVs0XRA...",
        "sheet_name": "Sheet1",       // optional, default: first sheet
        "sheet_gid": "0"              // optional, default: 0 (first sheet)
    }
"""

import argparse
import csv
import io
import json
import sys
import urllib.request


def _parse_spreadsheet_input(raw: str) -> tuple:
    """Parse spreadsheet ID or full URL. Returns (spreadsheet_id, gid_or_None)."""
    import re

    raw = raw.strip()

    # Full URL: https://docs.google.com/spreadsheets/d/<ID>/edit?gid=<GID>#gid=<GID>
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', raw)
    if match:
        spreadsheet_id = match.group(1)
        # Try to extract gid
        gid_match = re.search(r'[?&#]gid=(\d+)', raw)
        gid = gid_match.group(1) if gid_match else None
        return spreadsheet_id, gid

    # Just the ID
    return raw, None


def _infer_type(values: list) -> str:
    """Infer JSON Schema type from sample values."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "string"

    # Try integer
    try:
        for v in non_empty[:20]:
            int(v)
        return "integer"
    except (ValueError, TypeError):
        pass

    # Try float
    try:
        for v in non_empty[:20]:
            float(v.replace(",", "."))
        return "number"
    except (ValueError, TypeError):
        pass

    # Try boolean
    if all(v.lower() in ("true", "false", "sim", "nao", "yes", "no", "0", "1") for v in non_empty[:20]):
        return "boolean"

    return "string"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--state", required=False, help="Path to state JSON (ignored)")
    parser.add_argument("--catalog", required=False, help="Path to catalog JSON (ignored)")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    # Accept "url" (preferred) or legacy "spreadsheet_id"
    raw_id = config.get("url", config.get("spreadsheet_id", ""))
    spreadsheet_id, auto_gid = _parse_spreadsheet_input(raw_id)

    sheet_gid = str(config.get("sheet_gid", config.get("gid", auto_gid or "0")))
    sheet_name = config.get("sheet_name", config.get("stream_name", "sheet"))

    # Build CSV export URL
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={sheet_gid}"

    print(f"Downloading: {url}", file=sys.stderr)

    # Download CSV (with confirm=1 to bypass Google's "large file" warning)
    try:
        download_url = f"{url}&confirm=1"
        req = urllib.request.Request(download_url, headers={
            "User-Agent": "DataSpoc-Pipe/0.1",
            "Accept": "text/csv",
        })
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8-sig")
    except Exception as e:
        print(f"ERROR: Failed to download spreadsheet: {e}", file=sys.stderr)
        print(f"URL: {url}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Checklist:", file=sys.stderr)
        print(f"  1. Is the spreadsheet shared as 'Anyone with the link'?", file=sys.stderr)
        print(f"  2. Is the spreadsheet_id correct? Got: {spreadsheet_id}", file=sys.stderr)
        print(f"  3. Is the sheet_gid correct? Got: {sheet_gid}", file=sys.stderr)
        print(f"     (Check the URL: ...edit?gid=XXXXXX — use that number)", file=sys.stderr)
        print(f"  4. You can also paste the full URL in spreadsheet_id field", file=sys.stderr)
        sys.exit(1)

    # Parse CSV
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)

    if not rows:
        print("WARNING: Spreadsheet is empty or could not be parsed.", file=sys.stderr)
        sys.exit(0)

    # Clean column names (remove BOM, trim whitespace)
    columns = [c.strip().replace("\ufeff", "") for c in rows[0].keys()]

    # Infer schema from data
    col_values = {col: [row.get(col, "") for row in rows] for col in columns}
    properties = {}
    for col in columns:
        col_type = _infer_type(col_values[col])
        properties[col] = {"type": ["null", col_type]}

    # Emit SCHEMA
    schema_msg = {
        "type": "SCHEMA",
        "stream": sheet_name,
        "schema": {"properties": properties},
        "key_properties": [],
    }
    print(json.dumps(schema_msg))

    # Emit RECORDS
    for row in rows:
        # Convert types
        record = {}
        for col in columns:
            val = row.get(col, "").strip()
            col_type = _infer_type(col_values[col])

            if not val:
                record[col] = None
            elif col_type == "integer":
                try:
                    record[col] = int(val)
                except (ValueError, TypeError):
                    record[col] = val
            elif col_type == "number":
                try:
                    record[col] = float(val.replace(",", "."))
                except (ValueError, TypeError):
                    record[col] = val
            elif col_type == "boolean":
                record[col] = val.lower() in ("true", "sim", "yes", "1")
            else:
                record[col] = val

        record_msg = {
            "type": "RECORD",
            "stream": sheet_name,
            "record": record,
        }
        print(json.dumps(record_msg))

    # Emit STATE
    state_msg = {
        "type": "STATE",
        "value": {"bookmarks": {sheet_name: {"extracted_at": __import__("datetime").datetime.now().isoformat()}}},
    }
    print(json.dumps(state_msg))


if __name__ == "__main__":
    main()
