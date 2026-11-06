"""candblocks.py DOC PAGE : the Surya candidate's blocks for a page, numbered, first 160 chars each (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, blocks FROM page_ocr_candidate WHERE document_id=%s AND page_no=%s AND engine=%s ORDER BY id DESC LIMIT 1", (int(sys.argv[1]), int(sys.argv[2]), ENGINE))
    cid, bl = cur.fetchone(); print("candidate", cid)
    for i, b in enumerate(bl):
        print(i, repr(b["text"][:160]))
