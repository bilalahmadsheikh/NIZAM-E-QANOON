"""rawmany.py N BLOCK [BLOCK ...] : repr of the first N chars of each block (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
n = int(sys.argv[1])
with connect() as conn, conn.cursor() as cur:
    for b in sys.argv[2:]:
        cur.execute("SELECT page_no, text FROM text_block WHERE id=%s", (int(b),))
        p, t = cur.fetchone(); print(b, f"p{p}", repr(t[:n]))
