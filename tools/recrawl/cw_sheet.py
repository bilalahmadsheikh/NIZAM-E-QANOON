"""Contact sheet for catchword candidates: page foot + next page head (read-only). cw_sheet.py IN.json OUT.png"""
import json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
items = json.load(open(sys.argv[1], encoding="utf-8"))
W = 560
doc_out = pymupdf.open(); pg = doc_out.new_page(width=W + 20, height=len(items) * 260 + 20)
y = 6
with connect() as conn, conn.cursor() as cur:
    for n, x in enumerate(items, 1):
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (x["doc"],))
        src = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        for p, frac0, frac1, cap in ((x["page"], 0.72, 1.0, "FOOT"), (x["next_page"], 0.0, 0.22, "NEXT HEAD")):
            r = src[p - 1].rect
            clip = pymupdf.Rect(r.x0, r.y0 + r.height * frac0, r.x1, r.y0 + r.height * frac1)
            h = clip.height * W / clip.width
            pg.insert_text((10, y + 9), f"#{n} doc {x['doc']} label {x['label']} {cap} p{p}  {x['text'][:30]}", fontsize=8, color=(0.8, 0, 0))
            pg.show_pdf_page(pymupdf.Rect(10, y + 12, 10 + W, y + 12 + h), src, p - 1, clip=clip)
            y += 16 + h
        pg.draw_line((0, y), (W + 20, y), color=(0, 0, 0.8), width=1.5); y += 4
pg.get_pixmap(dpi=90, clip=pymupdf.Rect(0, 0, W + 20, y)).save(sys.argv[2])
print(sys.argv[2])
