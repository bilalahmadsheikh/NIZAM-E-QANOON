"""First and last page of several documents side by side (read-only): ends.py OUT.png DOC [DOC ...]"""
import sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
docs = [int(x) for x in sys.argv[2:]]
W, H = 300, 420
out = pymupdf.open(); pg = out.new_page(width=2 * W, height=len(docs) * (H + 14))
with connect() as conn, conn.cursor() as cur:
    for i, d in enumerate(docs):
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
        src = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        for j, p in enumerate((1, len(src))):
            x, y = j * W, i * (H + 14)
            pg.insert_text((x + 4, y + 10), f"doc {d} p{p}/{len(src)}", fontsize=9, color=(0.8, 0, 0))
            pg.show_pdf_page(pymupdf.Rect(x + 2, y + 13, x + W - 2, y + 13 + H), src, p - 1)
pg.get_pixmap(dpi=100).save(sys.argv[1]); print(sys.argv[1])
