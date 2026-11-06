"""targetpages.py OUT.json : pages worth a Surya re-read in held documents (read-only).
S7: the pages of every pending unit (demoted and kept). Gaps: for a numeric gap N, the pages from unit N-1's page to
unit N+1's page (or N-1's page and the next one). Only held documents not already in the q1 Surya queue."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
out = {}
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT c.document_id, c.source_page, c.canonical_source_page FROM v_structural_adjudication_pending p
                     JOIN segmentation_structural_candidate c ON c.id=p.id
                    WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=c.instrument_id)""")
    for d, a, b in cur.fetchall():
        out.setdefault(d, set()).update(x for x in (a, b) if x)
    cur.execute("SELECT document_id, printed_label FROM v_toc_gap_pending")
    for d, lab in cur.fetchall():
        if not re.fullmatch(r"\d{1,3}", (lab or "").strip()):
            continue
        n = int(lab)
        cur.execute("""SELECT pr.label, coalesce(t.page_no, pr.first_page) FROM provision pr JOIN instrument i ON i.id=pr.instrument_id AND i.is_active
                        LEFT JOIN text_block t ON t.id=pr.first_block WHERE i.document_id=%s AND pr.is_active
                        AND pr.kind::text IN ('section','rule','regulation','article') AND pr.label IN (%s,%s)""", (d, str(n - 1), str(n + 1)))
        pg = {l: p for l, p in cur.fetchall()}
        lo, hi = pg.get(str(n - 1)), pg.get(str(n + 1))
        if lo and hi and 0 <= hi - lo <= 3:
            out.setdefault(d, set()).update(range(lo, hi + 1))
        elif lo:
            out.setdefault(d, set()).update((lo, lo + 1))
    cur.execute("SELECT id, page_count FROM document WHERE id = ANY(%s)", (list(out),))
    pc = dict(cur.fetchall())
q1 = {int(x) for x in open("/mnt/e/nizam-data/ocr/q1r-output/targets.txt").read().split()[0::2]}
res = {str(d): sorted(p for p in ps if 1 <= p <= (pc.get(d) or 0)) for d, ps in out.items() if d not in q1}
json.dump(res, open(sys.argv[1], "w"), indent=0)
print(len(res), "documents,", sum(len(v) for v in res.values()), "pages")
