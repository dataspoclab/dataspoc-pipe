#!/bin/bash
# ============================================================================
# DataSpoc E2E Demo -- From raw data to analysis
#
# Downloads a real dataset from the web, ingests it with DataSpoc Pipe,
# then analyzes it with DataSpoc Lens.
#
# Usage:
#   cd /home/sanmartim/fontes/ds/dataspoc
#   source .venv/bin/activate
#   bash examples/e2e-demo.sh
# ============================================================================

set -euo pipefail

# -- Resolve paths ----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEMO_DIR=$(mktemp -d -t dataspoc-e2e-XXXXXX)
LAKE_DIR="$DEMO_DIR/lake"
MOCK_TAP="$SCRIPT_DIR/mock_tap_csv.py"

# Ensure dataspoc-lens is importable even if not pip-installed
export PYTHONPATH="${PROJECT_DIR}/lens/src:${PROJECT_DIR}/src:${PYTHONPATH:-}"

# Resolve CLI commands -- prefer installed entry-points, fall back to module
if command -v dataspoc-pipe &>/dev/null; then
    PIPE_CMD="dataspoc-pipe"
else
    PIPE_CMD="python -m dataspoc_pipe.cli"
fi

if command -v dataspoc-lens &>/dev/null; then
    LENS_CMD="dataspoc-lens"
else
    LENS_CMD="python -m dataspoc_lens"
fi

# Dataset URL -- Iris from the UCI Machine Learning Repository (GitHub mirror)
DATASET_URL="https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"

echo "============================================================"
echo "  DataSpoc E2E Demo"
echo "============================================================"
echo ""
echo "  Working directory : $DEMO_DIR"
echo "  Lake directory    : $LAKE_DIR"
echo "  Pipe CLI          : $PIPE_CMD"
echo "  Lens CLI          : $LENS_CMD"
echo ""

# -- Step 1: Download dataset -----------------------------------------------
echo "--- Step 1: Downloading Iris dataset ---"
curl -sL "$DATASET_URL" -o "$DEMO_DIR/iris.csv"
ROW_COUNT=$(tail -n +2 "$DEMO_DIR/iris.csv" | wc -l)
echo "  Downloaded $ROW_COUNT rows to $DEMO_DIR/iris.csv"
echo ""

# -- Step 2: Create tap config ----------------------------------------------
echo "--- Step 2: Setting up mock Singer tap ---"
cat > "$DEMO_DIR/tap-config.json" <<EOF
{"csv_path": "$DEMO_DIR/iris.csv", "stream_name": "iris"}
EOF
echo "  Tap config: $DEMO_DIR/tap-config.json"

# Quick sanity check -- first 2 lines from mock tap
echo "  Verifying tap output (first 2 messages):"
set +o pipefail
python "$MOCK_TAP" --config "$DEMO_DIR/tap-config.json" 2>/dev/null | head -2 | while read -r line; do
    echo "    $line"
done
set -o pipefail
echo ""

# -- Step 3: Initialize Pipe and create pipeline ----------------------------
echo "--- Step 3: Initializing DataSpoc Pipe ---"
$PIPE_CMD init

# Write pipeline YAML directly (avoids interactive wizard)
mkdir -p ~/.dataspoc-pipe/pipelines
cat > ~/.dataspoc-pipe/pipelines/iris-demo.yaml <<EOF
source:
  tap: "python $MOCK_TAP"
  config: "$DEMO_DIR/tap-config.json"
destination:
  bucket: "file://$LAKE_DIR"
  path: raw
  compression: zstd
incremental:
  enabled: false
schedule:
  cron: null
EOF
echo "  Pipeline config saved to ~/.dataspoc-pipe/pipelines/iris-demo.yaml"
echo ""

# -- Step 4: Run Pipe -------------------------------------------------------
echo "--- Step 4: Running DataSpoc Pipe (ingest CSV -> Parquet) ---"
$PIPE_CMD run iris-demo
echo ""

# -- Step 5: Inspect the lake -----------------------------------------------
echo "--- Step 5: Inspecting lake contents ---"
echo "  Parquet files in lake:"
find "$LAKE_DIR" -name '*.parquet' -printf "    %p (%s bytes)\n" 2>/dev/null || true
echo ""
echo "  Manifest:"
$PIPE_CMD manifest "file://$LAKE_DIR"
echo ""

# -- Step 6: Pipeline status -------------------------------------------------
echo "--- Step 6: Pipeline status ---"
$PIPE_CMD status
echo ""

# -- Step 7: Initialize Lens ------------------------------------------------
echo "--- Step 7: Setting up DataSpoc Lens ---"

# Note: Pipe writes a dict-keyed manifest; Lens expects a list-keyed manifest.
# Convert the manifest so Lens can read it via manifest-first discovery.
python - "$LAKE_DIR" <<'PYEOF'
import json, sys
mpath = f"{sys.argv[1]}/.dataspoc/manifest.json"
try:
    with open(mpath) as f:
        m = json.load(f)
    tables_dict = m.get("tables", {})
    if isinstance(tables_dict, dict):
        tables_list = []
        for key, val in tables_dict.items():
            entry = dict(val)
            if "location" not in entry:
                entry["location"] = f"raw/{key}"
            if "row_count" not in entry:
                stats = entry.pop("stats", {})
                entry["row_count"] = stats.get("total_rows", 0)
            tables_list.append(entry)
        m["tables"] = tables_list
        with open(mpath, "w") as f:
            json.dump(m, f, indent=2)
        print("  Manifest converted for Lens compatibility.")
except FileNotFoundError:
    print("  No manifest found (Lens will use scan fallback).")
PYEOF

$LENS_CMD init
$LENS_CMD add-bucket "file://$LAKE_DIR"
echo ""

# -- Step 8: Catalog ---------------------------------------------------------
echo "--- Step 8: Viewing catalog ---"
$LENS_CMD catalog
echo ""

# -- Step 9: Run queries -----------------------------------------------------
echo "--- Step 9: Querying with DataSpoc Lens ---"

echo ""
echo "[Query 1] First 10 rows:"
$LENS_CMD query "SELECT * FROM iris LIMIT 10"

echo ""
echo "[Query 2] Row count:"
$LENS_CMD query "SELECT count(*) AS total_rows FROM iris"

echo ""
echo "[Query 3] Average measurements per species:"
$LENS_CMD query "SELECT species, ROUND(AVG(sepal_length),2) AS avg_sepal_len, ROUND(AVG(sepal_width),2) AS avg_sepal_wid, ROUND(AVG(petal_length),2) AS avg_petal_len, ROUND(AVG(petal_width),2) AS avg_petal_wid FROM iris GROUP BY species ORDER BY species"

echo ""
echo "[Query 4] Species distribution:"
$LENS_CMD query "SELECT species, count(*) AS n FROM iris GROUP BY species ORDER BY n DESC"

echo ""
echo "[Query 5] Top 5 largest petals:"
$LENS_CMD query "SELECT species, petal_length, petal_width FROM iris ORDER BY petal_length DESC LIMIT 5"
echo ""

# -- Step 10: Export results -------------------------------------------------
echo "--- Step 10: Exporting results ---"
$LENS_CMD export "SELECT * FROM iris" --format csv --output "$DEMO_DIR/export.csv"
$LENS_CMD export "SELECT species, ROUND(AVG(sepal_length),2) AS avg_sepal_len, ROUND(AVG(petal_length),2) AS avg_petal_len FROM iris GROUP BY species ORDER BY species" --format json --output "$DEMO_DIR/summary.json"
echo ""
echo "  Exported files:"
ls -lh "$DEMO_DIR/export.csv" "$DEMO_DIR/summary.json"
echo ""

# -- Done --------------------------------------------------------------------
echo "============================================================"
echo "  Demo complete!"
echo "============================================================"
echo ""
echo "  Lake location   : $LAKE_DIR"
echo "  CSV export       : $DEMO_DIR/export.csv"
echo "  JSON export      : $DEMO_DIR/summary.json"
echo ""
echo "  To explore interactively:"
echo "    $LENS_CMD shell"
echo ""
echo "  To clean up:"
echo "    rm -rf $DEMO_DIR"
echo "    rm -f ~/.dataspoc-pipe/pipelines/iris-demo.yaml"
echo "============================================================"
