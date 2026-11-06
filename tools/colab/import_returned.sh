#!/bin/bash
# import_returned.sh : unpack every Colab results zip in /mnt/e/nizam-data/ocr/colab/returned/ into colab/output/ and
# import each results.json as Surya page candidates (nizam.workers.import_surya_candidates is idempotent: pages
# already present are skipped). Prints the documents that gained candidates. Writes candidates only -- acceptance,
# promotion and release go through tools/recrawl/pt_trial.py / ocr_policy.py / pt_apply.sh as for local reads.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
C=/mnt/e/nizam-data/ocr/colab; mkdir -p $C/returned $C/output $C/returned/imported
for z in $C/returned/*.zip; do
  [ -f "$z" ] || continue
  .venv/bin/python -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$z" $C/output && mv "$z" $C/returned/imported/
done
DOCS=""
for r in $C/output/*/results.json; do
  [ -f "$r" ] || continue
  out=$(.venv/bin/python -m nizam.workers.import_surya_candidates "$r" 2>&1 | tail -1)
  case "$out" in *"inserted 0 "*) ;; *) stem=$(basename $(dirname $r)); echo "$stem: $out"; DOCS="$DOCS ${stem%%-page*}";; esac
done
echo "documents with new candidates:$(echo $DOCS | tr ' ' '\n' | sort -u | tr '\n' ' ')"
