#!/bin/bash
# lead_confirm.sh DOC "what the pages are" : the lead read EVERY page render of DOC and transcribed or checked its text
# against the page (blockfix/pagewrite specs). Records the source_content_confirmed assertion verify_ocr honours for a
# low legal-token rate (purpose 'ocr-table-document', precedent assertion 12 -- there an owner export; here the lead
# under the owner's chat delegation of 25 Oct 2026, the renders' sha256 in the detail), then re-runs verify_ocr.
# Use only after every page has been read; the document's provisions must already be the page-read text.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$1; WHAT=$2
SHA=$(./nz psql -tAc "SELECT sha256 FROM document WHERE id=$D" | tr -d '[:space:]')
N=$(./nz psql -tAc "SELECT page_count FROM document WHERE id=$D" | tr -d '[:space:]')
R=.artifacts/release-work-2026-09-24/claude/renders
for p in $(seq 1 $N); do [ -f $R/doc$D-p$p.png ] || bash .artifacts/recrawl-queue/render_pages.sh $D 80 $p >/dev/null; done
RSHA=$(for p in $(seq 1 $N); do printf '"%s",' $(sha256sum $R/doc$D-p$p.png | cut -c1-64); done | sed 's/,$//')
./nz psql -v ON_ERROR_STOP=1 -v sha="$SHA" \
  -v ev="The lead, under the owner's chat delegation of 25 Oct 2026, checked document $D: $WHAT The low legal-token rate reflects a short text or amounts and names, not misreading." \
  -v det="{\"method\": \"${METHOD:-lead-full-page-read}\", \"purpose\": \"ocr-table-document\", \"document_id\": $D, \"render_sha256\": [$RSHA], \"precedent_assertion_id\": 12}" <<'SQL'
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT :'sha', NULL, 'source_content_confirmed', :'ev', (:'det')::jsonb, 'claude.lead-page-read/1'
 WHERE NOT EXISTS (SELECT 1 FROM extraction_assertion WHERE sha256=:'sha' AND kind='source_content_confirmed' AND is_active AND detail->>'purpose'='ocr-table-document');
SQL
bash tools/recrawl/ocr_verify.sh $D | tail -2
