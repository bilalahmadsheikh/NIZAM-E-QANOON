#!/usr/bin/env bash
# round.sh WORKDIR PATCHDIR SUFFIX : one proof round of a page-furniture batch (D-085 method).
# Records every patch-*SUFFIX.json in PATCHDIR, dry-runs those documents with the release gate's tree dumps, proves
# each document (tools/recrawl/sindh_title_proof.py), then runs batch_stage2.sh: failing documents' readings from this
# round are retired unreplayed, passing documents are held, replayed, re-verified and released.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
W=$1; P=$2; SUF=$3
mkdir -p "$W"; date -u +%Y-%m-%dT%H:%M:%SZ > "$W/started_at"
: > "$W/record.log"
for f in "$P"/patch-*"$SUF".json; do
  [ "$(.venv/bin/python -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$f")" = 0 ] && continue
  .venv/bin/python tools/record_curation_patch.py --readings "$f" --apply 2>&1 \
    | grep -E 'recorded|refused  *: [1-9]|^    doc .*:' | sed "s#^#$(basename "$f") #" >> "$W/record.log"
done
echo "recorded: $(grep -c 'recorded [1-9]' "$W/record.log") files; refusals: $(grep -c 'refused' "$W/record.log")"
DOCS=$(ls "$P" | sed -nE "s/patch-([0-9]+)$SUF.json/\1/p" | paste -sd, -)
rm -rf "$W/dump"; mkdir -p "$W/dump"
.venv/bin/python -m nizam.workers.segment --documents "$DOCS" --redo --include-review --dry-run --quiet \
  --release-diff "$W/diff.jsonl" --release-tree-dump "$W/dump" 2>&1 | grep -E 'ERROR|analysed' | cut -c1-220 > "$W/dry.log"
tail -3 "$W/dry.log"
.venv/bin/python tools/recrawl/sindh_title_proof.py "$W/dump" "$P" "$W/proof.json" "$SUF"
bash .artifacts/heritage-2026-11-18/batch_stage2.sh "$W" "$SUF" "${LABEL:-page furniture round}"
