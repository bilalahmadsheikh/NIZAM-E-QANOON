"""c_crop.py DOC PAGE TOPFRAC BOTFRAC [DPI] : a horizontal strip of a page (fractions of height) for reading only ->
.artifacts/recrawl-queue/sheets-C/crop-DOC-pPAGE.png (read-only on the database)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
import pymupdf
from nizam.storage.db import connect
doc, page, t, b = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
dpi = int(sys.argv[5]) if len(sys.argv) > 5 else 150
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (doc,))
    key = cur.fetchone()[0]
src = pymupdf.open("/mnt/e/nizam-data/" + key)
pg = src[page - 1]
r = pg.rect
clip = pymupdf.Rect(r.x0, r.y0 + r.height * t, r.x1, r.y0 + r.height * b)
out = f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/sheets-C/crop-{doc}-p{page}.png"
pg.get_pixmap(dpi=dpi, clip=clip).save(out)
print(out, "rotation", pg.rotation)
