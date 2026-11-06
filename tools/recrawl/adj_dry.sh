#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for t in adjudicate_structural_candidates adjudicate_citation_preserving adjudicate_toc_found_elsewhere adjudicate_run_only_gaps; do
  echo "=== $t"; timeout 1800 .venv/bin/python tools/$t.py 2>&1 | grep -vE "^\s{4,}" | tail -8
done
echo "=== triage_toc_gaps"; timeout 1800 .venv/bin/python tools/triage_toc_gaps.py 2>&1 | tail -12
