"""contents_folio_patch.py DOC FIRST LAST BODY OUT.json [--rows none|sections] [--label TEXT]

Build a page-read patch (append-only curation lane) for a compiled volume whose CONTENTS was read as law and whose
printed page numbers were read into provisions (ICT CDA Service Regulations, 15 Nov 2026):

  * on the body's first page, one entry carrying `source_contents_region` {FIRST..LAST is the contents, BODY opens the
    body, rows as given, skip_apparatus} -- rule reviewed_contents_region;
  * on every body page, the page's bare printed number set aside -- rule reviewed_apparatus_block. A block is a page
    number only when it is the LAST block of its page in reading order, its whole text is 1-3 digits, and it starts
    in the bottom tenth of the page (y0 >= 0.9 x the page's lowest block bottom).

Renders are written for every page named (tools/recrawl/fill_patch.py then adds sha256 and identity locators).
Read-only on the database."""
import argparse, json, re, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon"); REL = ".artifacts/release-work-2026-09-24/claude/renders"
ap = argparse.ArgumentParser()
ap.add_argument("doc", type=int); ap.add_argument("first", type=int); ap.add_argument("last", type=int)
ap.add_argument("body", type=int); ap.add_argument("out")
ap.add_argument("--rows", default="none", choices=["none", "sections"])
ap.add_argument("--label", default="the compiled volume")
a = ap.parse_args()
blocks = legal_write.blocks_for(a.doc)
by_id = {b["id"]: b for b in blocks}
body_page = by_id[a.body]["page_no"]
pages: dict = {}
for b in blocks:
    pages.setdefault(b["page_no"], []).append(b)
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (a.doc,))
    pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
FOLIO = re.compile(r"^\s*\d{1,3}\s*$")
out = []
for page in sorted(p for p in pages if p >= body_page):
    pb = pages[page]                                   # blocks_for returns reading order
    height = pdf[page - 1].rect.height
    last = pb[-1]
    folio = [last["id"]] if FOLIO.match(last["text"] or "") and last["y0"] >= 0.9 * height else []
    if page != body_page and not folio:
        continue
    render = f"{REL}/doc{a.doc}-p{page}.png"
    pdf[page - 1].get_pixmap(dpi=110).save(ROOT / render)
    r = {"document_id": a.doc, "page_no": page, "render": render}
    if folio:
        r["source_apparatus_blocks"] = folio
    if page == body_page:
        r["source_contents_region"] = {"first_block_id": a.first, "last_block_id": a.last,
                                       "body_start_block_id": a.body, "rows": a.rows, "skip_apparatus": True}
        r["defect"] = (f"{a.label}'s CONTENTS (INDEX) pages were read as law: their rows became parts and subsections, "
                       "and the body's opening chapters were nested under the contents' last part")
        r["fixes"] = ("rule reviewed_contents_region: the INDEX from block %d (p%d) to block %d (p%d) is contents only "
                      "(rows not linked); the body opens at block %d (p%d)"
                      % (a.first, by_id[a.first]["page_no"], a.last, by_id[a.last]["page_no"], a.body, body_page))
        r["observed"] = (f"Pages {by_id[a.first]['page_no']}-{by_id[a.last]['page_no']} print the INDEX table "
                         f"(chapter, subject, page); page {body_page} opens the body "
                         f"'{(by_id[a.body]['text'] or '').strip()[:60]}'"
                         + (f"; its page number '{last['text'].strip()}' is printed at the foot" if folio else ""))
    else:
        r["defect"] = "the page's printed page number was read into a provision's text"
        r["fixes"] = "rule reviewed_apparatus_block: the page-number block is set aside; no law text changes"
        r["observed"] = (f"Page {page} prints its page number '{last['text'].strip()}' alone at the foot "
                         f"(block {last['id']}, the page's last block, y={last['y0']:.0f} of {height:.0f})")
    out.append(r)
Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(out)} entries; {sum(1 for r in out if 'source_apparatus_blocks' in r)} page numbers; body page {body_page}")
