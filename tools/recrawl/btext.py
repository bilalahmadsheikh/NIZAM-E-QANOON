"""btext.py DOC:BLOCK[:BLOCK2:tag] ... : raw first 90 chars of blocks (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    for a in sys.argv[1:]:
        parts = a.split(":")
        for b in parts[1:3]:
            cur.execute("SELECT page_no, text FROM text_block WHERE id=%s", (int(b),))
            r = cur.fetchone()
            print(parts[0], parts[3] if len(parts) > 3 else "", b, f"p{r[0]}", repr(r[1][:90]))
