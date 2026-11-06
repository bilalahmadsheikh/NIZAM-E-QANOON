#!/bin/bash
# triage.sh DOC... : for each document with undecided Surya pages, the in-memory trial (stale patches dropped, empty
# re-reads keeping the stored text) on one line -- stored vs re-read, and the delegated-q5 verdict:
# ACCEPT (strictly better, no more demotions), READ (strictly more sections but more demotions: read them first,
# then --demotions-read), or HOLD. Read-only.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for d in "$@"; do
  out=$(STALE=drop .venv/bin/python tools/recrawl/pt_trial.py $d 2>&1)
  s=$(grep -m1 '^  stored' <<< "$out" | sed 's/^  stored : //'); r=$(grep -m1 '^  re-read' <<< "$out" | sed 's/^  re-read: //')
  v=$(.venv/bin/python - "$s" "$r" <<'PY'
import sys
def n(x): return dict(p.split("=") for p in x.split() if "=" in p)
try:
    a, b = n(sys.argv[1]), n(sys.argv[2])
    sa, sb, da, db = int(a["sections"]), int(b["sections"]), int(a["demoted"]), int(b["demoted"])
    ma, mb = int(a["missing"]), int(b["missing"])
    worse_toc = a["toc_found"] == "True" and b["toc_found"] == "False"
    gain = mb < ma or db < da or sb > sa or (b["toc_found"] == "True" and a["toc_found"] == "False")
    if sb < sa or mb > ma or worse_toc: print("HOLD")
    elif db <= da and gain: print("ACCEPT")
    elif sb > sa: print("READ")
    else: print("HOLD")
except Exception: print("FAILED")
PY
)
  printf '%s | %s | stored %s | re-read %s\n' "$d" "$v" "$s" "$r"
done
