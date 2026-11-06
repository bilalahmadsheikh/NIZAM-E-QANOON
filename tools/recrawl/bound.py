"""Find where bound laws start in a PDF and whether each is held elsewhere (read-only).

    python tools/recrawl/bound.py DOC [DOC ...]
Prints title-like blocks (ACT/ORDINANCE/ORDER/REGULATION/RULES headings, 'An Act to', 'PRESIDENT'S ORDER No.', '(Act No.')
with page and block id, and for each title the active canonical instruments elsewhere whose folded title matches."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

TITLE = re.compile(r"\b(?:ACT|ORDINANCE|ORDER|REGULATIONS?|RULES)\b[ ,.]*(?:\d{4}|N[Oo]\.)|PRESIDENT.S ORDER|"
                   r"^\s*An?\s+Act\b|\(Act No\.|ORDINANCE No\.|ACT No\.|^\s*No\. ?F\.", re.M)


def key(t):
    t = (t or "").lower()
    t = re.sub(r"\bsind\b", "sindh", t)
    t = re.sub(r"\b(1[89]\d\d|20\d\d)\b.*$", "", t, flags=re.S)
    return re.sub(r"[^a-z]", "", re.sub(r"^\W*the\s+", "", t))


with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT i.document_id, i.short_title, EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
                     FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL""")
    allinst = cur.fetchall()
    for doc in map(int, sys.argv[1:]):
        cur.execute("SELECT i.short_title, d.page_count FROM instrument i JOIN document d ON d.id=i.document_id "
                    "WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL LIMIT 1", (doc,))
        t = cur.fetchone()
        print(f"=== doc {doc} {t}")
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (doc,))
        rows = cur.fetchall()
        for bid, page, text in rows:
            one = re.sub(r"\s+", " ", text).strip()
            if TITLE.search(text) and len(one) < 220:
                k = key(one)
                hits = [f"{d}{'*' if rel else ''}" for d, st, rel in allinst
                        if d != doc and len(k) > 12 and key(st) and (k.startswith(key(st)) or key(st).startswith(k))]
                print(f"  p{page} {bid} {one[:120]!r}" + (f"  ELSEWHERE {hits[:4]}" if hits else ""))
        print(f"  last block p{rows[-1][1]} {rows[-1][0]} {re.sub(chr(10), ' ', rows[-1][2])[:80]!r}")
