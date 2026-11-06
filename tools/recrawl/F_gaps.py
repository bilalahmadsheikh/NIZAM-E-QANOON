"""Section/rule label sequence of an instrument, with gaps and repeats (read-only): F_gaps.py DOC [DOC ...]"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for doc in [int(x) for x in sys.argv[1:]]:
        cur.execute(r"""SELECT p.label, p.first_page, nlevel(p.path) FROM provision p
                         JOIN instrument i ON i.id=p.instrument_id AND i.is_active AND i.duplicate_of IS NULL
                        WHERE i.document_id=%s AND p.is_active AND p.kind::text IN ('section','article','rule','regulation')
                          AND NOT p.path::text ~ 'sch_' ORDER BY p.first_page, p.path""", (doc,))
        rows = cur.fetchall()
        labs = [r[0] for r in rows]
        nums = [int(m.group()) for l in labs if (m := re.match(r"\d+", l or ""))]
        mx = max(nums) if nums else 0
        missing = sorted(set(range(1, mx + 1)) - set(nums))
        rep = sorted({n for n in nums if nums.count(n) > 1})
        print(f"doc {doc}: {len(labs)} sections, max {mx}, missing {missing[:40]}{'...' if len(missing)>40 else ''} repeated {rep}")
        print("   seq:", " ".join(f"{l}@{p}" for l, p, _ in rows)[:900])
