"""cropzoom.py DOC PAGE X0 Y0 X1 Y1 DPI OUT.png : crop a region (fractions 0-1 of the page) at DPI (read-only)"""
import os, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
d, p = int(sys.argv[1]), int(sys.argv[2]); x0, y0, x1, y1 = map(float, sys.argv[3:7]); dpi = int(sys.argv[7])
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
    pg = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])[p - 1]
r = pg.rect; clip = pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height, r.x0 + x1 * r.width, r.y0 + y1 * r.height)
rot = int(os.environ.get("ROT", "0"))       # ROT=90/180/270 turns the crop for a page printed sideways
pg.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72).prerotate(rot), clip=clip).save(sys.argv[8]); print(sys.argv[8])
