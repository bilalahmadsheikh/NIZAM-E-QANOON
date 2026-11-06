"""gapsheet.py OUT.png OUT.json DOC [DOC ...] : for each pending contents gap, crop the contents row and the best body
candidate block (heading words found in the body) side by side (read-only). JSON lists gap rows and candidates."""
import json, re, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
docs = list(map(int, sys.argv[3:]))
W = 640
out = pymupdf.open(); pg = out.new_page(width=W + 20, height=14000); y = 6; items = []
srcs = {}
def crop(cur, bid, yy, label):
    cur.execute("SELECT b.object_key, t.x0, t.y0, t.x1, t.y1, t.page_no, d.id FROM text_block t JOIN document d ON d.id=t.document_id JOIN blob b ON b.sha256=d.sha256 WHERE t.id=%s", (bid,))
    key, x0, y0, x1, y1, p, d = cur.fetchone()
    src = srcs.setdefault(key, pymupdf.open(Path("/mnt/e/nizam-data") / key))
    r = src[p - 1].rect
    clip = pymupdf.Rect(max(r.x0, x0 - 30), max(r.y0, y0 - 4), min(r.x1, max(x1, x0 + 250) + 10), min(r.y1, y0 + 46))
    h = clip.height * (W / 2 - 10) / clip.width
    return src, p, clip, h
with connect() as conn, conn.cursor() as cur:
    for d in docs:
        cur.execute("""SELECT g.printed_label, coalesce(g.printed_heading,''), g.source_block_id, g.source_page FROM v_toc_gap_pending g WHERE g.document_id=%s""", (d,))
        gaps = cur.fetchall()
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (d,))
        blocks = cur.fetchall()
        for lab, head, rb, rp in gaps:
            words = re.findall(r"[A-Za-z]{4,}", head)[:3]
            cand = next((b for b in blocks if b[0] != rb and words and all(w.lower() in b[2].lower() for w in words) and b[1] != rp), None)
            items.append({"doc": d, "label": lab, "heading": head[:80], "row_block": rb, "row_page": rp, "body_block": cand[0] if cand else None,
                          "body_page": cand[1] if cand else None, "body_text": re.sub(r"\s+", " ", cand[2])[:160] if cand else None})
            n = len(items)
            pg.insert_text((10, y + 9), f"#{n} doc {d} row '{lab}' {head[:50]!r} | body {cand[0] if cand else '-'} p{cand[1] if cand else '-'}", fontsize=8, color=(0.8, 0, 0))
            hmax = 0
            for k, bid in enumerate([rb] + ([cand[0]] if cand else [])):
                if bid is None:
                    continue
                src, p, clip, h = crop(cur, bid, y, lab)
                pg.show_pdf_page(pymupdf.Rect(10 + k * (W / 2), y + 12, 10 + k * (W / 2) + W / 2 - 10, y + 12 + h), src, p - 1, clip=clip)
                hmax = max(hmax, h)
            y += 18 + hmax
pg.get_pixmap(dpi=80, clip=pymupdf.Rect(0, 0, W + 20, y)).save(sys.argv[1])
json.dump(items, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(items), "gaps")
for i, x in enumerate(items, 1):
    print(i, x["doc"], repr(x["label"]), repr(x["heading"][:40]), "body", x["body_block"], x["body_page"], repr((x["body_text"] or "")[:90]))
