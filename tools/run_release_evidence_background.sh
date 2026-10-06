#!/usr/bin/env bash
# Build one proposal-only release evidence batch without occupying an agent.
#
# This script never adjudicates a legal decision and never rewrites a legal
# tree. It waits for a signed second-parser manifest, selects whole
# single-blocker document evidence sets, runs local Surya inference, imports
# page candidates, and writes proposals only if the manifest is still fresh.

set -euo pipefail
cd "$(dirname "$0")/.."

run_dir="${1:?usage: tools/run_release_evidence_background.sh RUN_DIR [MAX_FILES]}"
max_files="${2:-40}"
batch_dir="$run_dir/background-input"
log="$run_dir/background.log"
status="$run_dir/background.status"

mkdir -p "$run_dir"
exec > >(tee -a "$log") 2>&1

# A detached shell can disappear after any step. Never leave a misleading
# "running-local-inference" marker when the worker has actually failed.
mark_failed() {
    result=$?
    if [ "$result" -ne 0 ]; then
        printf 'failed-exit-%s\n' "$result" > "$status"
        echo "proposal batch failed with exit $result; see $log"
    fi
}
trap mark_failed EXIT

printf 'waiting-for-manifest\n' > "$status"
echo "waiting for $run_dir/manifest.json"
while [ ! -f "$run_dir/manifest.json" ]; do
    sleep 5
done

printf 'verifying\n' > "$status"
./nz second-parser verify --run "$run_dir"

printf 'selecting-batch\n' > "$status"
./nz second-parser batch \
    --run "$run_dir" \
    --out "$batch_dir" \
    --single-blocker \
    --max-files "$max_files"

input_count="$(find "$batch_dir" -maxdepth 1 -type f -o -type l | wc -l)"
if [ "$input_count" -le 1 ]; then
    echo "no incomplete single-blocker page inputs remain"
    printf 'complete-no-input\n' > "$status"
    exit 0
fi

printf 'running-local-inference\n' > "$status"
bash tools/run_second_parser_batch.sh "$run_dir" "$batch_dir"

printf 'complete-proposals-ready\n' > "$status"
echo "proposal batch complete: $run_dir/proposals.json"
