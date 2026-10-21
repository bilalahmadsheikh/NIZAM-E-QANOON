#!/bin/bash
# Stop the slow 3-way archive run; re-split what is left of it into 10 chunks; restart Sindh and Balochistan.
O=/mnt/e/nizam-data/recrawl-2026-10-20
pkill -f "missing-drs[012].jsonl"; sleep 2
cd /mnt/e/Nizam_e_Qanoon
python3 - <<'PY'
import json
O = "/mnt/e/nizam-data/recrawl-2026-10-20/"
rows = [json.loads(l) for i in range(3) for l in open(O + f"missing-drs{i}.jsonl", encoding="utf-8")]
for i in range(10):
    with open(O + f"missing-drsx{i}.jsonl", "w", encoding="utf-8") as fh:
        for r in rows[i::10]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("archive items", len(rows), "in 10 chunks")
PY
bash tools/recrawl/run_land.sh sindh balochistan drsx0 drsx1 drsx2 drsx3 drsx4 drsx5 drsx6 drsx7 drsx8 drsx9
