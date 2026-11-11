"""Build one owner-verdict pack per document that has pages with no extracted text, plus one combined pack.

A page with no text_block row is invisible to every quality gate: it can be a blank back cover, a stamp, or a page of law the
extraction lost. Each pack shows only that document's empty pages (scan, a machine hint of how much ink the page carries) and
lets the owner give a verdict per page -- blank/no law text, law text (typed), illegible, or duplicate -- exported as
nizam.desk-pages/1 JSON. Read-only on the database; nothing is recorded or released.

    ./.venv/bin/python tools/build_empty_pages_packs.py --out .artifacts/owner-packs-2026-11-08/empty-pages
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import zipfile
from pathlib import Path

import pymupdf

from nizam.storage.db import connect

TEMPLATE = Path(__file__).with_name("offline_desk_template.html")
DATA = Path("/mnt/e/nizam-data")
INK = bytes(1 if i < 140 else 0 for i in range(256))


def hint(ink: float) -> tuple[str, str]:
    pct = f"{ink * 100:.2f}%"
    if ink < 0.003:
        return f"Machine hint: ink {pct}, looks BLANK", "nolaw"
    if ink < 0.02:
        return f"Machine hint: ink {pct}, mostly empty (stamp, short line or faint print?)", ""
    return f"Machine hint: ink {pct}, LOOKS LIKE IT CARRIES PRINT", ""


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:48] or "document"


def guidance(doc: int, title: str, released: bool, total: int, pages: list[int]) -> str:
    state = ("RELEASED (its text is live in the corpus without these pages)" if released
             else "NOT RELEASED yet")
    plist = ", ".join(map(str, pages))
    return f"""VERDICT PACK -- document {doc}: {title}
{'=' * 72}
Status: {state}.   Pages in the scan: {total}.   Pages with NO extracted text: {len(pages)} ({plist}).

WHY YOU ARE HERE
The extraction produced no text at all for the pages above, so no quality check ever looked at them. Each can be harmless
(blank back page, cover, library stamp, photograph) or can be law that was lost. Only a person looking at the scan can say.

HOW TO USE (offline)
1. Unzip the folder. Keep index.html, drafts.js and the img folder together. Open index.html in Chrome or Edge.
2. Each page of this document shows the scan on the left. A 'Machine hint' line tells you how much print the page carries:
   it is a guess to save you time, not a verdict. Click the image to zoom.
3. Choose ONE of the four options for every page:
     Blank or no law text  -> a blank page, a cover, a stamp, an imprint, a picture, only a page number.
                              In the note say what it is: 'blank', 'back cover', 'library stamp', 'photograph'.
     Checked (law text)    -> the page prints law. Type it in the box exactly as printed (rules below), then save.
     Checked, has [illegible] -> the page prints law but part cannot be read. Type what you can, [illegible] for the rest.
     Duplicate scan        -> the same page as an earlier scan. In the note say which page it repeats.
4. Press "Save page". When you are done press "Export this document (JSON)": a file named like desk-{doc}-<n>of{len(pages)}.json
   goes to your Downloads folder. Copy it into d:\\Download.

WHAT TO TELL ME (one line is enough)
   'doc {doc}: all {len(pages)} blank'   or   'doc {doc}: pages <numbers> have law text, rest blank'
and send the exported .json. If a page has law text, the text you type is what I use.

RULES FOR TYPING LAW TEXT (same as the Proofreading Desk)
- Type what the page prints and nothing else; keep old spellings and printer's errors; never fill in from memory.
- A word or figure you cannot read is [illegible], never a guess.
- Paragraph per line group, blank line between paragraphs; two columns: left first, then right.
- Marginal note on its own line starting "Side note:"; footnote on its own line starting "Footnote:".
- Leave out the running head, page number and imprint. Tables: one row per line, cells separated by " | ".

WHAT I DO WITH YOUR VERDICT
- Blank / no law text: nothing in the corpus changes; I record that the page was looked at and is empty.
- Law text on a RELEASED document: the corpus is currently missing that law. I add it through the OCR/promotion route
  using your typed text and re-check the document before it stays released.
- Law text on an unreleased document: it becomes part of the reading I record before release.
- Unsure about a page: choose 'Checked, has [illegible]' with a note, or leave it unsaved and say so; I never guess.
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-gap", type=int, default=1)
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()
    img_dir = a.out / "_all" / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    (a.out / "released").mkdir(exist_ok=True)
    (a.out / "unreleased").mkdir(exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("""SELECT d.id, d.page_count, b.object_key, d.lane,
                              (SELECT coalesce(i.short_title, '') FROM instrument i
                                WHERE i.document_id=d.id AND i.is_active AND i.duplicate_of IS NULL
                                ORDER BY i.expression_ordinal LIMIT 1),
                              EXISTS (SELECT 1 FROM instrument i JOIN v_release_instrument r ON r.id=i.id
                                       WHERE i.document_id=d.id)
                         FROM document d JOIN blob b ON b.sha256=d.sha256
                         JOIN (SELECT document_id, count(DISTINCT page_no) n FROM text_block GROUP BY 1) tb
                           ON tb.document_id=d.id
                        WHERE d.is_active AND d.page_count - tb.n >= %s ORDER BY d.page_count - tb.n DESC, d.id""",
                    (a.min_gap,))
        docs = cur.fetchall()
        ids = [r[0] for r in docs]
        cur.execute("SELECT document_id, page_no FROM text_block WHERE document_id = ANY(%s) GROUP BY 1, 2", (ids,))
        have: dict[int, set[int]] = {}
        for d, p in cur.fetchall():
            have.setdefault(d, set()).add(p)
    packs, rows = [], []
    for doc, n_pages, key, lane, title, released in docs:
        title = title or f"document {doc}"
        empty = [p for p in range(1, n_pages + 1) if p not in have.get(doc, set())]
        pdf = pymupdf.open(str(DATA / key))
        pages = []
        for p in empty:
            page = pdf[p - 1]
            small = page.get_pixmap(matrix=pymupdf.Matrix(50 / 72, 50 / 72), colorspace=pymupdf.csGRAY)
            ink = small.samples.translate(INK).count(b"\x01") / max(1, len(small.samples))
            h, default = hint(ink)
            big = page.get_pixmap(matrix=pymupdf.Matrix(a.dpi / 72, a.dpi / 72))
            big.save(str(img_dir / f"doc{doc}-p{p}.jpg"), jpg_quality=70)
            pages.append({"page": p, "img": f"img/doc{doc}-p{p}.jpg", "ocr": "", "hint": h, "defaultStatus": default})
        pdf.close()
        docs_entry = {"doc": doc, "title": f"{title} (document {doc})",
                      "note": ("RELEASED document: " if released else "Unreleased document: ")
                              + f"{len(empty)} of {n_pages} pages have no extracted text.",
                      "priority": [], "pages": pages}
        packs.append((doc, title, released, n_pages, empty, docs_entry))
        rows.append([doc, title, "released" if released else "unreleased", lane, n_pages, len(empty),
                     " ".join(map(str, empty)), sum(1 for x in pages if x["defaultStatus"] == "nolaw")])
        print(doc, title[:40], len(empty), "empty of", n_pages, flush=True)
    for doc, title, released, n_pages, empty, entry in packs:
        sub = a.out / ("released" if released else "unreleased")
        z = sub / f"doc-{doc}-{slug(title)}-{len(empty)}pages.zip"
        pk = {"pack": f"empty-{doc}", "title": f"Verdicts for empty pages: {title} ({doc})",
              "subtitle": "Pages the extraction produced no text for. Give a verdict per page.", "docs": [entry]}
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
            root = Path(f"doc-{doc}-empty-pages")
            zf.writestr(str(root / "drafts.js"), "window.PACK = " + json.dumps(pk, ensure_ascii=False) + ";\n")
            zf.write(TEMPLATE, root / "index.html")
            zf.writestr(str(root / "READ-ME-FIRST.txt"), guidance(doc, title, released, n_pages, empty))
            for pg in entry["pages"]:
                zf.write(img_dir / f"doc{doc}-p{pg['page']}.jpg", root / pg["img"])
    combo = {"pack": "empty-all", "title": "Verdicts for every empty page, all documents",
             "subtitle": f"{sum(len(p[4]) for p in packs)} pages in {len(packs)} documents. Released documents first.",
             "docs": [e for _d, _t, rel, _n, _e, e in sorted(packs, key=lambda x: (not x[2], -len(x[4])))]}
    allroot = a.out / "_all"
    (allroot / "drafts.js").write_text("window.PACK = " + json.dumps(combo, ensure_ascii=False) + ";\n", encoding="utf-8")
    shutil.copy(TEMPLATE, allroot / "index.html")
    (allroot / "READ-ME-FIRST.txt").write_text(
        "COMBINED VERDICT PACK -- every page that has no extracted text, all documents, one list\n"
        "=======================================================================================\n"
        "The per-document zips hold the same pages; use this pack to go quickly, or use those to work one document at a time.\n"
        "Unzip, keep index.html + drafts.js + img together, open index.html in Chrome or Edge. Released documents come first.\n\n"
        "For EVERY page choose one of: Blank or no law text (say what it is in the note: blank, back cover, stamp, picture) /\n"
        "Checked (law text typed in the box, exactly as printed) / Checked, has [illegible] / Duplicate scan (say which page).\n"
        "The 'Machine hint' line is only a time-saver (ink coverage of the scan), never a verdict.\n\n"
        "Export per document with 'Export this document (JSON)' (file desk-<doc>-<n>of<N>.json) or 'Export every document'.\n"
        "Copy the files into d:\\Download and tell me, per document, one line: 'doc N: all blank' or 'doc N: pages X,Y have law text'.\n"
        "The typing rules and what I do with each verdict are in READ-ME-FIRST.txt inside every per-document zip.\n",
        encoding="utf-8")
    with zipfile.ZipFile(a.out / "ALL-empty-pages-combined.zip", "w", zipfile.ZIP_STORED) as zf:
        for f in sorted(allroot.rglob("*")):
            if f.is_file():
                zf.write(f, Path("all-empty-pages") / f.relative_to(allroot))
    with (a.out / "INDEX.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["document", "title", "state", "lane", "pages_total", "empty_pages", "empty_page_numbers", "looks_blank"])
        w.writerows(rows)
    print("documents", len(packs), "pages", sum(len(p[4]) for p in packs))


if __name__ == "__main__":
    main()
