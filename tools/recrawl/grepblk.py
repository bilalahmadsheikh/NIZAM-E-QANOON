"""Blocks of a document whose text matches a regex (read-only): grepblk.py DOC REGEX"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, pat = int(sys.argv[1]), sys.argv[2]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, reading_order, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (doc,))
    for i, p, o, t in cur.fetchall():
        m = re.search(pat, t)
        if m:
            s = max(0, m.start() - 60)
            print(f"{i} p{p} #{o} ...{re.sub(r'\s+', ' ', t[s:m.end() + 60])}...")
