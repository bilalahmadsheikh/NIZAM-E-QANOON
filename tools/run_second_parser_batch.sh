#!/usr/bin/env bash
# Run one signed, proposal-only second-parser batch end to end.
#
# The freshness check runs on both sides of the expensive inference step.  If
# the corpus changes while Surya is working, results stay on disk as evidence
# but are not imported or proposed against a different legal tree.
set -euo pipefail

RUN="${1:?usage: run_second_parser_batch.sh RUN INPUT_DIR}"
INPUT="${2:?usage: run_second_parser_batch.sh RUN INPUT_DIR}"
DB="${NIZAM_CLEAN_DB:-nizam_clean}"

POSTGRES_DB="$DB" uv run python tools/second_parser_release.py verify --run "$RUN"
bash tools/run_surya_ocr.sh "$INPUT" "$RUN/output"
POSTGRES_DB="$DB" uv run python tools/second_parser_release.py verify --run "$RUN"
POSTGRES_DB="$DB" uv run python tools/second_parser_release.py import-results --run "$RUN"
POSTGRES_DB="$DB" uv run python tools/second_parser_release.py propose --run "$RUN"
