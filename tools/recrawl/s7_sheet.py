"""Contact sheets for pending S7 units: the printed region around each demoted and kept opener (read-only).

    python tools/recrawl/s7_sheet.py OUTDIR --docs 4744 4837 ...     or   --year-min 2020 [--limit N]

For every unit: a full-page evidence render (claude/renders/docD-pP.png, 70 dpi, made once, sha256 recorded) and
two crops of that page set on a sheet -- the demoted unit's opener and the kept unit's opener. The sheet is for
reading; a reading cites the full-page render and its sha, never the sheet. manifest.json maps U# to the unit.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect  # noqa: E402

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
RENDERS = ROOT / ".artifacts/release-work-2026-09-24/claude/renders"
REL = ".artifacts/release-work-2026-09-24/claude/renders"
DATA = Path("/mnt/e/nizam-data")
PER_SHEET = int(__import__("os").environ.get("PER_SHEET", "4"))
W = 560

SQL = r"""
SELECT c.id::text, c.document_id, c.printed_label, i.year, b.object_key,
       (SELECT array[t.page_no, t.x0, t.y0, t.x1, t.y1, t.id] FROM provision_block pb JOIN text_block t ON t.id=pb.block_id
         WHERE pb.provision_id=cp.id ORDER BY t.page_no, t.reading_order LIMIT 1),
       (SELECT array[t.page_no, t.x0, t.y0, t.x1, t.y1, t.id] FROM provision_block pb JOIN text_block t ON t.id=pb.block_id
         WHERE pb.provision_id=kp.id ORDER BY t.page_no, t.reading_order LIMIT 1),
       c.source_page, c.canonical_source_page,
       length(coalesce(cv.text_en,'')), length(coalesce(kv.text_en,'')),
       left(regexp_replace(coalesce(cv.text_en,''),'\\s+',' ','g'),90), left(regexp_replace(coalesce(kv.text_en,''),'\\s+',' ','g'),90)
  FROM v_structural_adjudication_pending p
  JOIN segmentation_structural_candidate c ON c.id=p.id
  JOIN instrument i ON i.id=c.instrument_id
  JOIN document d ON d.id=c.document_id JOIN blob b ON b.sha256=d.sha256
  JOIN provision cp ON cp.id=c.candidate_provision_id LEFT JOIN provision_version cv ON cv.provision_id=cp.id
  JOIN provision kp ON kp.id=c.canonical_provision_id LEFT JOIN provision_version kv ON kv.provision_id=kp.id
 WHERE NOT (c.document_id = ANY(%(skip)s::bigint[])) AND (%(docs)s::bigint[] IS NULL OR c.document_id = ANY(%(docs)s))
   AND (%(ymin)s::int IS NULL OR i.year >= %(ymin)s)
   AND (%(ymax)s::int IS NULL OR i.year <= %(ymax)s)
 ORDER BY i.year DESC NULLS LAST, c.document_id, c.source_page
"""


def evidence(doc_id, src, page_no):
    out = RENDERS / f"doc{doc_id}-p{page_no}.png"
    if not out.exists():
        src[page_no - 1].get_pixmap(dpi=70).save(out)
    return f"{REL}/{out.name}", hashlib.sha256(out.read_bytes()).hexdigest()


def panel(sheet, y, src, box, caption, above, below):
    page_no, x0, y0, x1, y1 = box[:5]
    pg = src[int(page_no) - 1]
    r = pg.rect
    if not box[5]:
        above, below, y0 = 0, r.height, r.y0
    clip = pymupdf.Rect(r.x0, max(r.y0, float(y0) - above), r.x1, min(r.y1, float(y0) + below))
    h = clip.height * W / clip.width
    sheet.insert_text((10, y + 10), caption, fontsize=8, color=(0.7, 0, 0))
    dst = pymupdf.Rect(10, y + 14, 10 + W, y + 14 + h)
    sheet.show_pdf_page(dst, src, int(page_no) - 1, clip=clip)
    sheet.draw_rect(dst, color=(0.6, 0.6, 0.6), width=0.4)
    # mark the opener line
    sy = dst.y0 + (float(y0) - clip.y0) * W / clip.width
    sheet.draw_line((4, sy), (9, sy + 4), color=(1, 0, 0), width=1.2)
    return y + 18 + h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--docs", type=int, nargs="*")
    ap.add_argument("--year-min", type=int)
    ap.add_argument("--year-max", type=int)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--skip", type=int, nargs="*", default=[])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SQL, {"docs": a.docs or None, "ymin": a.year_min, "ymax": a.year_max, "skip": a.skip})
        rows = cur.fetchall()
    if a.limit:
        rows = rows[: a.limit]
    manifest, srcs = [], {}
    out_doc, sheet, y, n_on = None, None, 0, 0
    sheets = []
    for n, (cid, doc, label, year, key, dbox, kbox, dpage, kpage, dlen, klen, dtxt, ktxt) in enumerate(rows, 1):
        if doc not in srcs:
            srcs[doc] = pymupdf.open(DATA / key)
        src = srcs[doc]
        if dbox is None:
            dbox = [dpage, 0, 0, 0, 0, 0]
        if kbox is None:
            kbox = [kpage, 0, 0, 0, 0, 0]
        dr, dsha = evidence(doc, src, int(dbox[0]))
        kr, ksha = evidence(doc, src, int(kbox[0]))
        manifest.append({"u": n, "candidate_id": cid, "document_id": doc, "year": year, "printed_label": label,
                         "demoted_page": int(dbox[0]), "kept_page": int(kbox[0]),
                         "demoted_block": int(dbox[5] or 0), "kept_block": int(kbox[5] or 0), "demoted_len": dlen, "kept_len": klen,
                         "demoted_text": dtxt, "kept_text": ktxt,
                         "demoted_render": dr, "demoted_render_sha256": dsha, "kept_render": kr, "kept_render_sha256": ksha})
        if sheet is None or n_on == PER_SHEET or y > 2200:
            if sheet is not None:
                sheets.append((out_doc, y))
            out_doc = pymupdf.open()
            sheet = out_doc.new_page(width=W + 20, height=4000)
            y, n_on = 6, 0
        manifest[-1]["sheet"] = len(sheets) + 1
        y = panel(sheet, y, src, dbox, f"U{n}  doc {doc} ({year})  label {label!r}  DEMOTED p{int(dbox[0])} [{dlen}c]", 30, int(__import__("os").environ.get("BELOW", "130")))
        y = panel(sheet, y, src, kbox, f"U{n}  KEPT p{int(kbox[0])} [{klen}c]", 12, int(__import__("os").environ.get("KBELOW", "80"))) + 8
        sheet.draw_line((0, y - 4), (W + 20, y - 4), color=(0, 0, 0.8), width=1.5)
        n_on += 1
    if sheet is not None:
        sheets.append((out_doc, y))
    for i, (d, ylast) in enumerate(sheets, 1):
        d[0].get_pixmap(dpi=110, clip=pymupdf.Rect(0, 0, W + 20, min(4000, ylast))).save(a.out / f"sheet-{i:03d}.png")
    (a.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"units {len(rows)}  sheets {len(sheets)}  -> {a.out}")


if __name__ == "__main__":
    main()
