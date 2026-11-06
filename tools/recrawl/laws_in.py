"""List the laws a PDF prints, by their short-title clauses, and where else the corpus holds each (read-only).

    python tools/recrawl/laws_in.py DOC [DOC ...]
For each block with 'may be called the <title>' (or 'shall be called'): page, block id, the title, and active
canonical instruments elsewhere whose folded title equals it (doc, * = released). Also prints every block that opens a
law (ACT No./ORDINANCE No./PRESIDENT'S ORDER/'No. F.' notification/'An Act to'), so spans can be drawn."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

CALLED = re.compile(r"(?:may|shall)\s+be\s+(?:called|cited\s+as)\s+the\s+(.{5,160}?\b(?:1[89]\d\d|20\d\d))", re.I | re.S)
OPEN = re.compile(r"\b(?:ACT|Act|AcT)\s*:?\s*No\b|\bORDINANCE\s+No\b|PRESIDENT.S\s+(?:\(POST.PROCLAMATION\)\s+)?ORDER|"
                  r"^\s*No\.\s*F\.|\bAN?\s+(?:ACT|ORDINANCE)\b|^\s*An\s+Act\b", re.M)


def key(t):
    t = (t or "").lower()
    t = re.sub(r"\bsind\b", "sindh", t)
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^\W*the\s+", "", t))


with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT i.document_id, i.short_title, EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
                     FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL""")
    idx = {}
    for d, t, rel in cur.fetchall():
        idx.setdefault(key(re.sub(r"[.,]?\s*$", "", t or "")), []).append(f"{d}{'*' if rel else ''}")
    for doc in map(int, sys.argv[1:]):
        cur.execute("SELECT short_title FROM instrument WHERE document_id=%s AND is_active AND duplicate_of IS NULL "
                    "ORDER BY expression_ordinal LIMIT 1", (doc,))
        print(f"=== doc {doc} {cur.fetchone()[0]!r}")
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (doc,))
        rows = cur.fetchall()
        print(f"  first block {rows[0][0]} p{rows[0][1]}; last {rows[-1][0]} p{rows[-1][1]}")
        for bid, page, text in rows:
            one = re.sub(r"\s+", " ", text).strip()
            if OPEN.search(text) and len(one) < 200:
                print(f"  open  p{page} {bid} {one[:110]!r}")
            for m in CALLED.finditer(one):
                t = m.group(1)
                hits = [h for h in idx.get(key(t), []) if not h.startswith(str(doc))]
                print(f"  TITLE p{page} {bid} {t!r} elsewhere={hits}")
