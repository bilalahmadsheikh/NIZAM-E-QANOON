"""units_on.py DOC P1 [P2 ...] : active section-level units whose first block is on the given pages (read-only)"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
d, pages = int(sys.argv[1]), [int(p) for p in sys.argv[2:]]
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT pr.kind::text, pr.label, t.id, t.page_no, left(t.text, 70) FROM provision pr JOIN instrument i ON i.id=pr.instrument_id
                    JOIN text_block t ON t.id=pr.first_block
                   WHERE i.document_id=%s AND i.is_active AND pr.is_active AND t.page_no = ANY(%s)
                     AND pr.kind::text IN ('section','rule','regulation','article') ORDER BY t.page_no, t.reading_order""", (d, pages))
    for k, lab, b, p, t in cur.fetchall():
        print(k, lab, b, p, repr(re.sub(r"\s+", " ", t)))
