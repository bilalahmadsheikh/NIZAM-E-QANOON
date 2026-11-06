"""head.py DOC PAGE [N] : first N blocks of a page, one line each (read-only)"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, text FROM text_block WHERE document_id=%s AND page_no=%s ORDER BY reading_order LIMIT %s",
                (int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 12))
    for b, t in cur.fetchall():
        print(b, repr(re.sub(r"\s+", " ", t)[:100]))
