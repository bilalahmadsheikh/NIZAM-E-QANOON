#!/usr/bin/env bash
# Queue several proposal-only batches after the currently running first batch.
# One Surya worker at a time: simultaneous workers share and recycle the same
# llama-server and would race over the same output directory.
set -euo pipefail
cd "$(dirname "$0")/.."

run_dir="${1:?usage: tools/run_release_evidence_queue.sh RUN_DIR [BATCHES] [MAX_FILES]}"
batches="${2:-3}"
max_files="${3:-40}"
[[ "$batches" =~ ^[1-9][0-9]*$ && "$max_files" =~ ^[1-9][0-9]*$ ]] || {
    echo "BATCHES and MAX_FILES must be positive integers" >&2
    exit 2
}

mkdir -p "$run_dir"
exec 9>"$run_dir/background-queue.lock"
flock -n 9 || { echo "another background evidence queue is running" >&2; exit 1; }
exec > >(tee -a "$run_dir/background-queue.log") 2>&1
status="$run_dir/background-queue.status"
first_status="$run_dir/background.status"

fail() {
    code=$?
    if (( code != 0 )); then
        printf 'failed-exit-%s\n' "$code" > "$status"
        echo "evidence queue stopped with exit $code; see $run_dir/background-queue.log"
    fi
}
trap fail EXIT

# The first worker writes this status only after its post-inference verify,
# import and proposal steps. Keep a heartbeat so detached WSL is not reaped.
printf 'waiting-for-first-batch\n' > "$status"
while :; do
    first="$(<"$first_status")"
    case "$first" in
        complete-proposals-ready|complete-no-input) break ;;
        failed-* ) echo "first batch failed: $first" >&2; exit 1 ;;
        waiting-for-manifest|verifying|selecting-batch|running-local-inference)
            echo "waiting for first batch: $first"; sleep 30 ;;
        * ) echo "unexpected first-batch status: $first" >&2; exit 1 ;;
    esac
done

for (( number=1; number<=batches; number++ )); do
    label="$(printf '%03d' "$number")"
    # A unique input directory avoids stale symlinks from an older batch.
    input="$run_dir/background-input-queue-$(date -u +%Y%m%dT%H%M%SZ)-$label"
    printf 'selecting-%s\n' "$label" > "$status"
    ./nz second-parser batch --run "$run_dir" --out "$input" \
        --single-blocker --max-files "$max_files"

    mapfile -d '' -t selected < <(find "$input" -maxdepth 1 -name '*.pdf' -print0)
    if (( ${#selected[@]} == 0 )); then
        echo "no more incomplete single-blocker page inputs"
        printf 'complete-no-input\n' > "$status"
        exit 0
    fi

    printf 'running-%s-%s-files\n' "$label" "${#selected[@]}" > "$status"
    echo "batch $label: ${#selected[@]} source PDFs"
    bash tools/run_second_parser_batch.sh "$run_dir" "$input"

    # run_surya_ocr.sh can finish with an individual PDF failure. Fail closed
    # rather than calling an incomplete batch finished; a retry is resumable.
    missing=0
    for pdf in "${selected[@]}"; do
        stem="$(basename "$pdf" .pdf)"
        if [[ ! -s "$run_dir/output/$stem/results.json" ]]; then
            echo "missing Surya result: $stem" >&2
            missing=$((missing + 1))
        fi
    done
    if (( missing != 0 )); then
        echo "batch $label left $missing missing result(s); stop for retry" >&2
        exit 1
    fi
    printf 'complete-%s\n' "$label" > "$status"
    echo "batch $label complete; proposals refreshed"
done

printf 'complete-proposals-ready\n' > "$status"
