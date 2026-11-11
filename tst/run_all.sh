#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "${TOPICC_CONFIRM_FULL:-}" != "1" ]; then
  echo "Set TOPICC_CONFIRM_FULL=1 to run the complete multi-hour test plan." >&2
  exit 2
fi
STAMP="${TOPICC_TEST_STAMP:-$(date +%F)}"
ROOT="results/plan-tests/$STAMP"
.venv/bin/python tst/generate_instances.py
.venv/bin/python tst/run_verification.py --suite A --output-dir "$ROOT/A-contacts"
.venv/bin/python tst/run_verification.py --suite B --output-dir "$ROOT/B-propagation"
.venv/bin/python tst/run_verification.py --suite G --output-dir "$ROOT/G-static"
.venv/bin/python tst/run_campaign.py --group C --group D --group E --group G6 --output-root "$ROOT" --resume
.venv/bin/python tst/run_verification.py --suite G --output-dir "$ROOT/G-properties" -- \
  --determinism-results "$ROOT/G6/determinism-1/result.json" "$ROOT/G6/determinism-2/result.json"
SOURCE=$(find "$ROOT/C" -name result.json -print -quit)
.venv/bin/python tst/run_verification.py --suite F --output-dir "$ROOT/F-batch" -- --source-result "$SOURCE"
.venv/bin/python tst/analyze_campaign.py "$ROOT"
