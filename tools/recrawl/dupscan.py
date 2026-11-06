"""dupscan.py DOC... : pages of a document that repeat another page (a second scan bound into the PDF), read-only.
For each pair of pages, the share of the smaller page's word trigrams found on the other; pairs over 0.5 are printed."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
W = re.compile(r"[a-z]{3,}")
with connect() as conn, conn.cursor() as cur:
    for d in map(int, sys.argv[1:]):
        cur.execute("SELECT page_no, string_agg(text, ' ' ORDER BY block_no) FROM text_block WHERE document_id=%s GROUP BY 1", (d,))
        tri = {}
        for p, t in cur.fetchall():
            w = W.findall((t or "").casefold())
            tri[p] = set(zip(w, w[1:], w[2:]))
        ps = sorted(tri)
        hits = []
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                s = min(len(tri[a]), len(tri[b]))
                if s >= 40:
                    r = len(tri[a] & tri[b]) / s
                    if r > 0.5:
                        hits.append(f"p{a}=p{b} {r:.2f}")
        if hits:
            print(d, " ".join(hits))
