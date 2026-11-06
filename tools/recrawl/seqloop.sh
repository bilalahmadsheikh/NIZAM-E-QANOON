#!/bin/bash
# seqloop.sh N : seqfix proposals (minus known-bad docs in seq-skip.txt) -> crops sheet seqN.png + seqN.json
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
Q=.artifacts/recrawl-queue
.venv/bin/python tools/recrawl/seqfix.py $Q/seq$1-all.json | head -1
.venv/bin/python - "$1" <<'PY'
import json, sys
Q = ".artifacts/recrawl-queue"
skip = {(int(a), b) for a, b in (l.split()[:2] for l in open(f"{Q}/seq-skip.txt") if l.strip())}
xs, seen = [], set()
for x in json.load(open(f"{Q}/seq{sys.argv[1]}-all.json", encoding="utf-8")):
    if (x["doc"], str(x["block"])) in skip or (x["doc"], x["block"]) in seen:
        continue
    seen.add((x["doc"], x["block"])); xs.append(x)
json.dump(xs, open(f"{Q}/seq{sys.argv[1]}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for i, x in enumerate(xs, 1):
    print(i, x["doc"], x["block"], x["label"], "->", x["proposed"], repr(x["text"][:40]))
PY
.venv/bin/python tools/recrawl/cropblocks.py $Q/seq$1.json $Q/seq$1.png >/dev/null
