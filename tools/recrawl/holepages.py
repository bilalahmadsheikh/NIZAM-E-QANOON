"""holepages.py STATUS.csv : pages and lanes of held passed-quality docs, split by sequence completeness (read-only)"""
import csv, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
rows = [r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")) if r["cls"] in ("s7-only", "gaps-only", "s7+gaps")]
tot = {}
with connect() as conn, conn.cursor() as cur:
    for r in rows:
        cur.execute("""SELECT p.label FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active
                        WHERE i.document_id=%s AND p.is_active AND p.kind IN ('section','article')""", (int(r["doc"]),))
        labs = [int(m.group(1)) for (l,) in cur.fetchall() if (m := re.fullmatch(r"(\d{1,3})", l or ""))]
        holes = bool(labs) and any(x not in set(labs) for x in range(1, max(labs) + 1))
        k = ("holes" if holes else "complete", r["lane"]); n, p = tot.get(k, (0, 0)); tot[k] = (n + 1, p + int(r["pages"] or 0))
for k, (n, p) in sorted(tot.items()): print(k, n, "docs", p, "pages")
