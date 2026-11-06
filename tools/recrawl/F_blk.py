"""Raw text (repr) of text blocks by id (read-only): F_blk.py ID [ID ...]  (first 400 chars, or all with --all)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
full = "--all" in sys.argv
ids = [int(x) for x in sys.argv[1:] if x != "--all"]
with connect() as conn, conn.cursor() as cur:
    for i in ids:
        cur.execute("SELECT page_no, text FROM text_block WHERE id=%s", (i,))
        p, t = cur.fetchone()
        print(f"{i} p{p}: {t!r}" if full else f"{i} p{p}: {t[:400]!r}")
