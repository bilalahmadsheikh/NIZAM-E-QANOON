"""c_ids.py DOC P1 P2 REGEX : block ids (by page) whose text matches REGEX at its start (re.match), read-only.
REGEX may be given base64-free; use @D for \d and @S for \s and @P for \. to dodge shell quoting."""
import re, sys, json
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, p1, p2 = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
pat = sys.argv[4].replace("@D", r"\d").replace("@S", r"\s").replace("@P", r"\.")
out = {}
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s AND page_no BETWEEN %s AND %s ORDER BY page_no, reading_order", (doc, p1, p2))
    for i, p, t in cur.fetchall():
        if re.match(pat, t):
            out.setdefault(p, []).append(i)
            print(i, f"p{p}", repr(t[:70]))
print(json.dumps(out))
