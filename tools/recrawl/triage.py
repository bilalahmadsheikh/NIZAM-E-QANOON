"""triage.py MANIFEST [U ...] : per S7 unit, the kept and demoted openers with the two blocks before each (read-only)."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
m = json.load(open(sys.argv[1], encoding="utf-8"))
want = set(map(int, sys.argv[2:]))
def one(t, n=110): return re.sub(r"\s+", " ", t or "").strip()[:n]
with connect() as conn, conn.cursor() as cur:
    for x in m:
        if want and x["u"] not in want: continue
        print(f"=== U{x['u']} doc {x['document_id']} ({x['year']}) label {x['printed_label']!r}  D p{x['demoted_page']} {x['demoted_len']}c  K p{x['kept_page']} {x['kept_len']}c")
        for tag, b in (("K", x["kept_block"]), ("D", x["demoted_block"])):
            cur.execute("""SELECT t.id, t.page_no, t.text FROM text_block t, text_block o WHERE o.id=%s AND t.document_id=o.document_id
                             AND (t.page_no, t.reading_order) <= (o.page_no, o.reading_order) ORDER BY t.page_no DESC, t.reading_order DESC LIMIT 3""", (b,))
            for bid, p, t in reversed(cur.fetchall()):
                print(f"  {tag}{'*' if bid == b else ' '} {bid} p{p} {one(t)!r}")
