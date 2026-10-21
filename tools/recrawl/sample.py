import json, random, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools/recrawl")
random.seed(7)
for src, listing, n in (("balochistan", "pabalochistan:acts", 14), ("sindh", "sindhlaws:gazette", 14)):
    rows = [json.loads(l) for l in open(f"/mnt/e/nizam-data/recrawl-2026-10-20/missing-{src}.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["listing"] == listing]
    amend = sum(1 for r in rows if "amend" in (r.get("title") or "").lower())
    print(f"== {src} {listing}: {len(rows)} missing, {amend} titled amendment")
    for r in random.sample(rows, min(n, len(rows))):
        print("  ", r.get("year"), (r.get("title") or "")[:90], "|", (r.get("extra") or {}).get("cells", "")[:4] if src == "balochistan" else r.get("number"))
