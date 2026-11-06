"""Thumbnail grid of a document's pages (read-only): grid.py DOC P1 P2 OUT.png [COLS]"""
import sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
doc, p1, p2, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 4
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (doc,))
    key = cur.fetchone()[0]
src = pymupdf.open(Path("/mnt/e/nizam-data") / key)
pages = list(range(p1, min(p2, len(src)) + 1))
W, H = 300, 420
rows = (len(pages) + cols - 1) // cols
g = pymupdf.open(); pg = g.new_page(width=cols * W, height=rows * (H + 14))
for i, p in enumerate(pages):
    x, y = (i % cols) * W, (i // cols) * (H + 14)
    pg.insert_text((x + 4, y + 10), f"p{p}", fontsize=9, color=(0.8, 0, 0))
    pg.show_pdf_page(pymupdf.Rect(x + 2, y + 13, x + W - 2, y + 13 + H), src, p - 1)
pg.get_pixmap(dpi=100).save(out)
print(out)
