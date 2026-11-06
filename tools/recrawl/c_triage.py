"""c_triage.py LISTFILE : per unreleased document -- open S7/TOC, top-level numeric units, missing numbers in 1..max,
out-of-order count, lane, pages (read-only)."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
docs = [int(x) for x in open(sys.argv[1]).read().split()]
with connect() as conn, conn.cursor() as cur:
    for doc in docs:
        cur.execute("""SELECT i.id, d.lane, d.page_count, coalesce(i.year,0),
              EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id),
              (SELECT count(*) FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id),
              (SELECT count(*) FROM v_toc_gap_pending g WHERE g.instrument_id=i.id)
              FROM instrument i JOIN document d ON d.id=i.document_id
             WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc,))
        rows = cur.fetchall()
        for iid, lane, pages, year, rel, s7, toc in rows:
            if rel:
                print(f"{doc}\tRELEASED"); continue
            cur.execute("""SELECT p.label FROM provision p WHERE p.instrument_id=%s AND p.is_active
                             AND p.kind::text IN ('section','article') ORDER BY p.first_page, p.path""", (iid,))
            labels = [r[0] for r in cur.fetchall()]
            nums = [int(m.group()) for l in labels for m in [re.fullmatch(r"\d{1,3}", l or "")] if m]
            mx = max(nums) if nums else 0
            missing = [n for n in range(1, mx + 1) if n not in set(nums)]
            disorder = sum(1 for a, b in zip(nums, nums[1:]) if b < a)
            print(f"{doc}\t{year}\t{lane}\t{pages}p\ts7={s7}\ttoc={toc}\tunits={len(labels)}\tmax={mx}\tmissing={len(missing)}\tdisorder={disorder}\t{missing[:12]}")
