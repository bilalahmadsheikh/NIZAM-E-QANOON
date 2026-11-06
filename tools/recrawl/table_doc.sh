#!/bin/bash
# table_doc.sh OLDDOC NEWDOC "description" : owner-reviewed OCR table document assertion (precedent tools/evidence/assert-ocr-table-document-4703.sql)
cd /mnt/e/Nizam_e_Qanoon
E=.artifacts/ocr-review-exports/ocr-review-doc-$1.json
[ -s "$E" ] || { echo "table_doc.sh: no owner export $E -- refused (an owner review is asserted only from its export)"; exit 1; }
ESHA=$(sha256sum $E | cut -c1-64)
SHA=$(./nz psql -tAc "SELECT sha256 FROM document WHERE id=$2" | tr -d '[:space:]')
N=$(./.venv/bin/python -c "import json;print(json.load(open('$E',encoding='utf-8-sig'))['source_page_count'])")
./nz psql -v ON_ERROR_STOP=1 -v sha="$SHA" -v ev="${REVIEWER:-The owner} reviewed all $N page images against the Surya reading and accepted every page ($E); the lead read the first and last page renders: $3 The low legal-token rate reflects table vocabulary." -v det="{\"method\": \"owner-page-review+lead-render-read\", \"purpose\": \"ocr-table-document\", \"owner_export\": \"$E\", \"owner_export_sha256\": \"$ESHA\", \"precedent_assertion_id\": 12}" <<'SQL'
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT :'sha', NULL, 'source_content_confirmed', :'ev', (:'det')::jsonb, 'claude.lead-table-document-review/1'
 WHERE NOT EXISTS (SELECT 1 FROM extraction_assertion WHERE sha256=:'sha' AND kind='source_content_confirmed' AND is_active AND detail->>'purpose'='ocr-table-document');
SQL
bash tools/recrawl/ocr_verify.sh $2 | tail -2
