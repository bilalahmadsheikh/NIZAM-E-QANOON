"""c_rawgrep.py DOC REGEX [CTX] : repr of raw text around each match (read-only)"""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, pat = int(sys.argv[1]), sys.argv[2]
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 60
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (doc,))
    for i, p, t in cur.fetchall():
        for m in re.finditer(pat, t):
            print(i, f"p{p}", repr(t[max(0, m.start() - ctx):m.end() + ctx]))
