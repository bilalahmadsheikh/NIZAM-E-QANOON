import collections, json, sys
r = json.load(open(f"/mnt/e/nizam-data/recrawl-2026-10-20/landed-{sys.argv[1]}.json", encoding="utf-8"))
c = collections.Counter((x.get("why") or "")[:110] for x in r["refused"])
for k, v in c.most_common(8): print(v, k)
print([ (x.get("title"), x.get("pdf_url")) for x in r["refused"][:3]])
