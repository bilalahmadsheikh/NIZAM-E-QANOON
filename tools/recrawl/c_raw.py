"""c_raw.py DOC BLOCK_ID [...] : repr of raw block text (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for b in sys.argv[2:]:
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s AND id=%s", (int(sys.argv[1]), int(b)))
        for r in cur.fetchall():
            print(r[0], "p", r[1], ascii(r[2]))
