import collections, json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
print(len(rows), collections.Counter(r["listing"] for r in rows))
print("empty titles", sum(1 for r in rows if not r.get("title")))
for r in rows[:4] + rows[-3:]: print({k: r[k] for k in ("listing", "title", "year", "detail_url")})
