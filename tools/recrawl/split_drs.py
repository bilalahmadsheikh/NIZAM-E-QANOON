import json
O = "/mnt/e/nizam-data/recrawl-2026-10-20/"
rows = [json.loads(l) for l in open(O + "missing-federal_drs.jsonl", encoding="utf-8")]
keep = [r for r in rows if r.get("kind") != "Constitution"]
print("missing", len(rows), "landing", len(keep), "(Constitution entries held back)")
for i in range(3):
    with open(O + f"missing-drs{i}.jsonl", "w", encoding="utf-8") as fh:
        for r in keep[i::3]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
