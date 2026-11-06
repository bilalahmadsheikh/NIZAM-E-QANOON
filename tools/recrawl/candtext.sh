#!/bin/bash
# candtext.sh DOC PAGE... : full Surya candidate text of each page (read-only)
cd /mnt/e/Nizam_e_Qanoon; D=$1; shift
for p in "$@"; do echo "##### $D p$p"; ./nz psql -tA -c "SELECT text FROM page_ocr_candidate WHERE document_id=$D AND page_no=$p AND engine LIKE 'surya%' ORDER BY id DESC LIMIT 1"; done
