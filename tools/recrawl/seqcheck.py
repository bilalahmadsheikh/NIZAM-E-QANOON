"""seqcheck.py STATUS.csv : for S7-only / gaps-only docs, is the top-level numeric section sequence 1..N complete
(no holes, no out-of-range labels)? Prints counts and lists; plus the quality:other docs (read-only)."""
import csv, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
res = {}
with connect() as conn, conn.cursor() as cur:
    for r in rows:
        if r["cls"] not in ("s7-only", "gaps-only", "s7+gaps"): continue
        cur.execute("""SELECT p.label FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active
                        WHERE i.document_id=%s AND p.is_active AND p.kind IN ('section','article')""", (int(r["doc"]),))
        labs = [int(m.group(1)) for (l,) in cur.fetchall() if (m := re.fullmatch(r"(\d{1,3})", l or ""))]
        if not labs: res[r["doc"]] = ("none", 0, 0); continue
        n = max(labs); have = set(labs); holes = [x for x in range(1, n + 1) if x not in have]
        res[r["doc"]] = ("complete" if not holes else "holes", n, len(holes))
from collections import Counter
for k in ("s7-only", "gaps-only", "s7+gaps"):
    xs = [r for r in rows if r["cls"] == k]
    c = Counter(res[r["doc"]][0] for r in xs)
    comp = [r for r in xs if res[r["doc"]][0] == "complete"]
    print(k, dict(c), "| complete & <=3 blockers:", sum(1 for r in comp if int(r["s7"]) + int(r["gaps"]) <= 3))
    print("   complete:", " ".join(f"{r['doc']}({int(r['s7'])+int(r['gaps'])})" for r in sorted(comp, key=lambda r: int(r['s7'])+int(r['gaps']))))
print("quality:other:", " | ".join(f"{r['doc']} {r['lane']} {r['quality']} {r['title'][:40]}" for r in rows if r["cls"] == "quality:other"))
print("deferred-large:", " ".join(f"{r['doc']}({r['pages']}p)" for r in rows if r["cls"] == "ocr:surya-deferred-large"))
print("surya-queued:", " ".join(f"{r['doc']}({r['pages']}p)" for r in rows if r["cls"] == "ocr:surya-queued"))
print("q1d awaiting:", " ".join(r["doc"] for r in rows if r["cls"] == "ocr:q1d-awaiting-owner"))
