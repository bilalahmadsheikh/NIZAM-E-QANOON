#!/usr/bin/env bash
# Continue two proposal-only batches after the first queue quarantines the
# malformed document 4608 PDF. This never changes legal trees or adjudicates.
set -euo pipefail
cd "$(dirname "$0")/.."

run_dir="${1:?usage: tools/resume_release_evidence_after_4608.sh RUN_DIR}"
status="$run_dir/background-queue-resume.status"
log="$run_dir/background-queue-resume.log"
mkdir -p "$run_dir"
exec > >(tee -a "$log") 2>&1
trap 'code=$?; if (( code != 0 )); then printf "failed-exit-%s\n" "$code" > "$status"; fi' EXIT

printf 'waiting-for-queue-001\n' > "$status"
while :; do
    current="$(<"$run_dir/background-queue.status")"
    case "$current" in
        failed-exit-1) break ;;
        complete-proposals-ready|complete-no-input)
            printf 'complete-original-queue-finished\n' > "$status"
            exit 0 ;;
        waiting-*|selecting-*|running-*|complete-001|complete-002)
            echo "waiting for batch 001: $current"; sleep 30 ;;
        *) echo "unexpected queue state: $current" >&2; exit 1 ;;
    esac
done

# Only continue if the precise known PDFium failure is the sole missing result
# from the first 40-file queue. A different failure must be investigated.
mapfile -d '' -t first_inputs < <(find "$run_dir" -maxdepth 2 \
    -path '*/background-input-queue-*-001/*.pdf' -print0)
(( ${#first_inputs[@]} == 40 )) || {
    echo "expected 40 first-queue inputs, found ${#first_inputs[@]}" >&2
    exit 1
}
missing=()
for pdf in "${first_inputs[@]}"; do
    stem="$(basename "$pdf" .pdf)"
    [[ -s "$run_dir/output/$stem/results.json" ]] || missing+=("$stem")
done
[[ ${#missing[@]} == 1 && ${missing[0]} == 4608 ]] || {
    echo "refusing resume: first-queue missing results are ${missing[*]}" >&2
    exit 1
}
grep -q 'PDFium: Data format error' "$run_dir/output/run.log" || {
    echo "refusing resume: no recorded PDFium format error for 4608" >&2
    exit 1
}

# The first queue owns this lock until its failure trap finishes. Never start
# another Surya worker while it still holds the shared inference server.
exec 9>"$run_dir/background-queue.lock"
flock -w 120 9 || { echo "original queue did not release lock" >&2; exit 1; }

printf 'quarantined-4608-source-format\n' > "$status"
echo "quarantined document 4608 from inference only: source PDF is malformed"
for number in 2 3; do
    label="$(printf '%03d' "$number")"
    input="$run_dir/background-input-resume-$(date -u +%Y%m%dT%H%M%SZ)-$label"
    printf 'selecting-%s\n' "$label" > "$status"
    ./nz second-parser batch --run "$run_dir" --out "$input" \
        --single-blocker --max-files 40 --exclude-document 4608
    mapfile -d '' -t selected < <(find "$input" -maxdepth 1 -name '*.pdf' -print0)
    if (( ${#selected[@]} == 0 )); then
        printf 'complete-no-input\n' > "$status"
        exit 0
    fi
    printf 'running-%s-%s-files\n' "$label" "${#selected[@]}" > "$status"
    bash tools/run_second_parser_batch.sh "$run_dir" "$input"
    for pdf in "${selected[@]}"; do
        stem="$(basename "$pdf" .pdf)"
        [[ -s "$run_dir/output/$stem/results.json" ]] || {
            echo "batch $label missing result $stem" >&2
            exit 1
        }
    done
    printf 'complete-%s\n' "$label" > "$status"
done
printf 'complete-proposals-ready\n' > "$status"
