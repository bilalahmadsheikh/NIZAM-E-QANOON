#!/bin/bash
# pageread_confirm.sh DOC "what was read" : the lead rendered EVERY page of DOC and its provisions are now that reading
# (pagewrite/blockfix transcription, or text checked line by line against the page). Records the
# source_content_confirmed assertion (purpose 'ocr-page-read-document') that verify_ocr/5 honours for an OCR
# confidence below threshold -- doc 02 §4 "human review below threshold" -- under the owner's chat delegation of
# 25 Oct 2026, with every page's render sha256 in the detail; then re-runs verify_ocr. Never before every page is read.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; WHAT=$2
SHA=$(./nz psql -tAc "SELECT sha256 FROM document WHERE id=$D" | tr -d '[:space:]')
N=$(./nz psql -tAc "SELECT page_count FROM document WHERE id=$D" | tr -d '[:space:]')
R=.artifacts/release-work-2026-09-24/claude/renders
for p in $(seq 1 $N); do [ -f $R/doc$D-p$p.png ] || bash .artifacts/recrawl-queue/render_pages.sh $D 80 $p >/dev/null; done
RSHA=$(for p in $(seq 1 $N); do printf '"%s",' $(sha256sum $R/doc$D-p$p.png | cut -c1-64); done | sed 's/,$//')
./nz psql -v ON_ERROR_STOP=1 -v sha="$SHA" \
  -v ev="The lead, under the owner's chat delegation of 25 Oct 2026, read every page of document $D against its render: $WHAT The document's provisions are that page-read text; the OCR engine's mean confidence describes a reading the release no longer carries." \
  -v det="{\"method\": \"${METHOD:-lead-full-page-read}\", \"purpose\": \"ocr-page-read-document\", \"document_id\": $D, \"pages\": $N, \"render_sha256\": [$RSHA]}" <<'SQL'
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT :'sha', NULL, 'source_content_confirmed', :'ev', (:'det')::jsonb, 'claude.lead-page-read/1'
 WHERE NOT EXISTS (SELECT 1 FROM extraction_assertion WHERE sha256=:'sha' AND kind='source_content_confirmed' AND is_active AND detail->>'purpose'='ocr-page-read-document');
SQL
bash tools/recrawl/ocr_verify.sh $D | tail -2
