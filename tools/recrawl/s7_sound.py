import collections, json
rows = [json.loads(l) for l in open("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/s7-units.jsonl", encoding="utf-8")]
by = collections.defaultdict(list)
for r in rows: by[r["instrument_id"]].append(r)
def bucket(us):
    r = us[0]
    if r["instrument_toc_open"]: return "has contents gaps too"
    if r["lane"] != "E2": return f"scan ({r['lane']})"
    n = len(us)
    return "E2, 1 unit" if n == 1 else ("E2, 2-3 units" if n <= 3 else "E2, 4+ units")
c = collections.Counter(bucket(us) for us in by.values())
for k, v in c.most_common(): print(v, k)
sel = [us[0] for us in by.values() if bucket(us) == "E2, 1 unit"]
json.dump(sel, open("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/s7-e2-single.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("written", len(sel))
