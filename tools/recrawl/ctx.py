"""ctx.py PATFILE BLOCK [BLOCK ...] : the text around the first regex match in each block, raw repr (read-only)"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
pat = open(sys.argv[1], encoding="utf-8").read().strip()
with connect() as conn, conn.cursor() as cur:
    for b in sys.argv[2:]:
        cur.execute("SELECT page_no, text FROM text_block WHERE id=%s", (int(b),))
        p, t = cur.fetchone()
        m = re.search(pat, t)
        print(b, f"p{p}", repr(t[max(0, m.start() - 30): m.start() + 120]) if m else "NO MATCH")
