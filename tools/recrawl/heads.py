"""heads.py DOC [DOC...] : blocks whose text is mostly upper-case titles or 'ORDINANCE No.'/'Ordinance No.' (read-only)"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for doc in map(int, sys.argv[1:]):
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (doc,))
        rows = cur.fetchall()
        print(f"=== {doc} first {rows[0][0]} last {rows[-1][0]} p{rows[-1][1]}")
        for i, p, t in rows:
            one = re.sub(r"\s+", " ", t).strip()
            letters = re.sub(r"[^A-Za-z]", "", one)
            if (len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.8 and len(one) < 120) \
               or re.search(r"(?i)ordinance\s+no\.|act\s+no\.|order\s+no\.", one) and len(one) < 120:
                print(f"  p{p} {i} {one[:100]!r}")
