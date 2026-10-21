import collections, json, glob
c = collections.Counter()
for f in glob.glob("/mnt/e/nizam-data/recrawl-2026-10-20/landed-drsx*.json"):
    for x in json.load(open(f, encoding="utf-8"))["refused"]:
        c[(x.get("why") or "")[:90]] += 1
for k, v in c.most_common(10): print(v, k)
