#!/bin/bash
# adj.sh : run the machine adjudicators and duplicate/repeal passes over all pending, then declare
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
q() { ./nz psql -tAc "$1" | tr -d "[:space:]"; }
R0=$(q "SELECT count(*) FROM v_release_instrument")
.venv/bin/python tools/adjudicate_structural_candidates.py --apply 2>&1 | grep -E "machine_evidenced|left_for"
.venv/bin/python tools/adjudicate_citation_preserving.py --apply 2>&1 | grep -E "recorded|left pending"
.venv/bin/python tools/resolve_exact_instrument_duplicates.py --apply 2>&1 | tail -1
R1=$(q "SELECT count(*) FROM v_release_instrument"); echo "released: $R0 -> $R1"
bash tools/recrawl/declare.sh 2>&1 | tail -1
