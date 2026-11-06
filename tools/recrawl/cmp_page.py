"""cmp_page.py DOC PAGE : current page text vs the Surya candidate (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
d, p = int(sys.argv[1]), int(sys.argv[2])
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT string_agg(text, E'\n|' ORDER BY reading_order) FROM text_block WHERE document_id=%s AND page_no=%s", (d, p))
    print("=== CURRENT\n" + (cur.fetchone()[0] or ""))
    cur.execute("SELECT text FROM page_ocr_candidate WHERE document_id=%s AND page_no=%s AND engine LIKE 'surya%%' ORDER BY id DESC LIMIT 1", (d, p))
    print("=== SURYA\n" + cur.fetchone()[0])
