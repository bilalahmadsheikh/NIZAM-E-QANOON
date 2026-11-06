#!/bin/bash
# finish.sh OLDDOC NEWDOC "description" : verify_ocr the promoted revision; if it is still held only on OCR quality
# review (table vocabulary), record the reviewed table-document assertion (table_doc.sh, precedent 12); show release.
cd /mnt/e/Nizam_e_Qanoon
bash tools/recrawl/ocr_verify.sh $2 | tail -1
Q=$(./nz psql -tAc "SELECT overall_outcome FROM v_document_quality_status WHERE document_id=$2" | tr -d '[:space:]')
if grep -q '"reviewer_name": "lead' .artifacts/ocr-review-exports/ocr-review-doc-$1.json; then export REVIEWER="The lead, under the owner's chat delegation of 25 Oct 2026,"; fi
# only with the owner's export on disk: without it table_doc.sh recorded an owner review that never happened
# (assertions 36-38, 28-29 Oct, withdrawn)
if [ "$Q" = "review" ] && [ -s .artifacts/ocr-review-exports/ocr-review-doc-$1.json ]; then
  bash tools/recrawl/table_doc.sh $1 $2 "$3" | tail -1
fi
