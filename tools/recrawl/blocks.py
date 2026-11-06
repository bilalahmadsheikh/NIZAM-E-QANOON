"""Print a page's text blocks of the document's active extraction (read-only): blocks.py DOC PAGE [PAGE2]"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, p1 = int(sys.argv[1]), int(sys.argv[2]); p2 = int(sys.argv[3]) if len(sys.argv) > 3 else p1
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT t.id, t.page_no, t.reading_order, round(t.x0), round(t.y0), left(regexp_replace(t.text,'\s+',' ','g'),120)
                     FROM text_block t WHERE t.document_id=%s AND t.page_no BETWEEN %s AND %s
                    ORDER BY t.page_no, t.reading_order""", (doc, p1, p2))
    for r in cur.fetchall():
        print(f"{r[0]} p{r[1]} #{r[2]} ({r[3]},{r[4]}) {r[5]}")
