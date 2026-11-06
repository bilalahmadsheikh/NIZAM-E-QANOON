cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do P=.artifacts/ocr-review-pack-q1; [ -d $P/doc-$d ] || P=.artifacts/ocr-review-pack-q1b
echo -n "$d "; .venv/bin/python tools/validate_ocr_review_export.py .artifacts/ocr-review-exports/ocr-review-doc-$d.json --pack $P 2>&1 | tail -1; done
