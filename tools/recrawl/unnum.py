"""unnum.py : held contents gaps whose promised heading opens a body block that prints no number (read-only).
Per gap: doc, label, heading, candidate block/page, whether the previous active section label is label-1."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT g.document_id, g.instrument_id, g.printed_label, g.printed_heading, g.source_page
                     FROM v_toc_gap_pending g WHERE g.toc_entry_id IS NOT NULL AND g.printed_heading IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=g.instrument_id)""")
    gaps = cur.fetchall(); n = 0
    for doc, inst, label, head, tpage in gaps:
        h = norm(head)
        if len(h.split()) < 2 or not re.fullmatch(r"\d{1,3}[A-Z]?", label or ""): continue
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s AND page_no > %s ORDER BY page_no, reading_order", (doc, tpage or 0))
        for bid, p, t in cur.fetchall():
            lines = [l for l in (t or "").split("\n") if l.strip()]
            for l in lines[:6]:
                nl = norm(l)
                if len(nl) >= 8 and (nl.startswith(h[:max(12, min(len(h), 30))]) ) and not re.match(r"\s*\(?\d", l):
                    n += 1; print(f"{doc}|{label}|{head[:50]}|blk {bid} p{p}|{l.strip()[:70]}"); break
            else: continue
            break
    print(n, "of", len(gaps))
