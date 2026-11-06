"""order.py DOC PAGE : blocks of a page in reading order with their boxes (read-only)"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT reading_order, x0, y0, x1, y1, text FROM text_block WHERE document_id=%s AND page_no=%s ORDER BY reading_order",
                (int(sys.argv[1]), int(sys.argv[2])))
    for o, x0, y0, x1, y1, t in cur.fetchall():
        print(f"{o:5d} x{x0:5.0f}-{x1:5.0f} y{y0:5.0f}-{y1:5.0f} {re.sub(chr(10)+'|\s+', ' ', t)[:70]!r}")
