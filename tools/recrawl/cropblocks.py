"""cropblocks.py IN.json OUT.png : crop each proposal's block (padded) onto one sheet, numbered (read-only)"""
import json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
items = json.load(open(sys.argv[1], encoding="utf-8"))
W = 620
out = pymupdf.open(); pg = out.new_page(width=W + 20, height=len(items) * 120 + 40); y = 6
with connect() as conn, conn.cursor() as cur:
    for n, x in enumerate(items, 1):
        cur.execute("SELECT b.object_key, t.x0, t.y0, t.x1, t.y1, t.page_no FROM text_block t JOIN document d ON d.id=t.document_id "
                    "JOIN blob b ON b.sha256=d.sha256 WHERE t.id=%s", (x["block"],))
        key, x0, y0, x1, y1, p = cur.fetchone()
        src = pymupdf.open(Path("/mnt/e/nizam-data") / key)
        r = src[p - 1].rect
        clip = pymupdf.Rect(max(r.x0, x0 - 40), max(r.y0, y0 - 6), min(r.x1, x0 + 260), min(r.y1, y0 + 34))
        h = clip.height * W / clip.width
        pg.insert_text((10, y + 9), f"#{n} doc {x['doc']} p{p} block {x['block']} read {x['label']!r} proposed {x['proposed']!r}",
                       fontsize=8, color=(0.8, 0, 0))
        pg.show_pdf_page(pymupdf.Rect(10, y + 12, 10 + W, y + 12 + h), src, p - 1, clip=clip)
        y += 18 + h
pg.get_pixmap(dpi=80, clip=pymupdf.Rect(0, 0, W + 20, y)).save(sys.argv[2]); print(sys.argv[2])
