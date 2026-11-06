"""bt.py BLOCK [BLOCK ...] : full raw text of blocks (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for b in sys.argv[1:]:
        cur.execute("SELECT document_id, page_no, text FROM text_block WHERE id=%s", (int(b),))
        d, p, t = cur.fetchone(); print(f"--- {b} doc {d} p{p}\n{t[:600]!r}")
