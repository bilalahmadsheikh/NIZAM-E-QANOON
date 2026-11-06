"""raw.py BLOCK [N] : repr of the first N chars of a block (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT text FROM text_block WHERE id=%s", (int(sys.argv[1]),))
    print(repr(cur.fetchone()[0][: int(sys.argv[2]) if len(sys.argv) > 2 else 300]))
