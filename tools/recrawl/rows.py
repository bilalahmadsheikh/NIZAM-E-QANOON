"""Blocks opening with a bare serial ('12.' / '12 ') in a page range (read-only): rows.py DOC P1 P2"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, p1, p2 = map(int, sys.argv[1:4])
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, round(x0), left(regexp_replace(text, E'\\s+', ' ', 'g'), 70) FROM text_block "
                "WHERE document_id=%s AND page_no BETWEEN %s AND %s ORDER BY page_no, reading_order", (doc, p1, p2))
    for i, p, x, t in cur.fetchall():
        if re.match(r"\s*\d{1,3}\s*[.)]?\s", t + " "):
            print(i, f"p{p}", x, t)
