"""Build owner packs for the empty pages that still have NO verdict (after the owner's blank audit and three transcription batches).

Input: a JSON {"pending_left": [[doc, page], ...]} (pages of the owner's manifest not yet certified blank or transcribed).
Output: one zip per big document and one zip for all the small ones, each an offline desk (index.html + drafts.js + img) that exports
nizam.desk-pages/1 JSON. A page that carries print (ink >= 2%) gets a local tesseract draft as a typing aid -- never evidence.
Read-only on the database; nothing is recorded or released.

    ./.venv/bin/python tools/build_remaining_empty_packs.py --pending pending_left.json --out .artifacts/owner-packs-2026-11-08/remaining-empty-pages
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pymupdf

from nizam.storage.db import connect

TEMPLATE = Path(__file__).with_name("offline_desk_template.html")
DATA = Path("/mnt/e/nizam-data")
INK = bytes(1 if i < 140 else 0 for i in range(256))
BIG = {8421: "A", 8524: "B", 8428: "C"}      # one pack each; every other document goes into pack D


def hint(ink: float) -> tuple[str, str]:
    pct = f"{ink * 100:.2f}%"
    if ink < 0.003:
        return f"Machine hint: ink {pct}, looks BLANK", "nolaw"
    if ink < 0.02:
        return f"Machine hint: ink {pct}, mostly empty (stamp, short line or faint print?)", ""
    return f"Machine hint: ink {pct}, LOOKS LIKE IT CARRIES PRINT (a machine draft is in the box; correct it against the scan)", ""


README = """VERDICT AND TRANSCRIPTION PACK {tag} -- {what}
{rule}
WHY YOU ARE HERE
  These are pages the extraction produced NO text for, and that are not yet certified blank or transcribed in your earlier batches.
  {docs}
  Each page is either harmless (blank, cover, stamp, picture) or law the corpus does not have. {state}

HOW TO USE (offline)
  1. Unzip. Keep index.html, drafts.js and the img folder together. Open index.html in Chrome or Edge.
  2. Pick the document in the list (top left), then each page: the scan is on the left; the box on the right holds a MACHINE DRAFT
     for pages that carry print (empty for pages that look blank). The draft is a typing aid only: correct it against the scan.
  3. Choose one status per page:
       Blank or no law text      blank page, cover, stamp, imprint, picture, only a page number. Say which in the note.
       Checked (law text)        the page prints law: the box must hold exactly what the page prints.
       Checked, has [illegible]  part cannot be read: type what you can, [illegible] for the rest.
       Duplicate scan            the same page as an earlier scan; say which page in the note.
  4. Save each page, then press "Export this document (JSON)" (or "Export every document") at the end of each sitting; copy the
     file(s) desk-<doc>-<n>of<N>.json into d:\\Download and tell me.

RULES FOR TYPING LAW TEXT (same as before)
  Type what the page prints; keep old spellings and printer's errors; never fill in from memory; a word or figure you cannot read is
  [illegible]. A paragraph per line group, blank line between paragraphs; two columns: left first. A margin note on its own line
  starting "Side note:", a footnote starting "Footnote:". Leave out the running head, page number and imprint. Tables: one row per
  line, cells separated by " | ". A map or diagram: say so in the note and type its readable labels; I will not guess a figure.

WHAT I DO WITH IT
  Blank: the page is recorded as looked at and empty. Law text: for a released document I add it through the OCR/promotion route and
  re-check the document before it stays released; for an unreleased document it becomes part of the reading I record before release.
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pending", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()
    pend: dict[int, list[int]] = {}
    for d, p in json.loads(a.pending.read_text())["pending_left"]:
        pend.setdefault(int(d), []).append(int(p))
    a.out.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[dict]] = {}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        for doc in sorted(pend):
            cur.execute("""SELECT b.object_key, coalesce((SELECT i.short_title FROM instrument i WHERE i.document_id=d.id AND i.is_active
                                   AND i.duplicate_of IS NULL ORDER BY i.expression_ordinal LIMIT 1), ''), d.page_count,
                                  EXISTS (SELECT 1 FROM instrument i JOIN v_release_instrument r ON r.id=i.id WHERE i.document_id=d.id)
                             FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s AND d.is_active""", (doc,))
            key, title, n_pages, released = cur.fetchone()
            title = (title or f"document {doc}").replace("\n", " ")
            tag = BIG.get(doc, "D")
            img_dir = a.out / f"_pack{tag}" / "img"
            img_dir.mkdir(parents=True, exist_ok=True)
            pdf = pymupdf.open(str(DATA / key))
            pages = []
            for p in sorted(pend[doc]):
                page = pdf[p - 1]
                small = page.get_pixmap(matrix=pymupdf.Matrix(50 / 72, 50 / 72), colorspace=pymupdf.csGRAY)
                ink = small.samples.translate(INK).count(b"\x01") / max(1, len(small.samples))
                h, default = hint(ink)
                big = page.get_pixmap(matrix=pymupdf.Matrix(a.dpi / 72, a.dpi / 72))
                big.save(str(img_dir / f"doc{doc}-p{p}.jpg"), jpg_quality=70)
                draft = ""
                if ink >= 0.02:
                    png = a.out / f"_o{doc}-{p}"
                    page.get_pixmap(matrix=pymupdf.Matrix(200 / 72, 200 / 72), colorspace=pymupdf.csGRAY).save(str(png) + ".png")
                    out = subprocess.run(["tesseract", str(png) + ".png", "stdout", "--psm", "4", "-l", "eng"],
                                         capture_output=True, text=True).stdout
                    Path(str(png) + ".png").unlink()
                    draft = "\n\n".join(x.strip() for x in re.split(r"\n\s*\n", out) if x.strip())
                pages.append({"page": p, "img": f"img/doc{doc}-p{p}.jpg", "ocr": draft, "hint": h, "defaultStatus": default})
            pdf.close()
            groups.setdefault(tag, []).append({
                "doc": doc, "title": f"{title} (document {doc})", "priority": [],
                "note": ("RELEASED document: " if released else "Unreleased document: ") + f"{len(pages)} pages still need a verdict (of {n_pages} scans).",
                "pages": pages, "_released": released})
            print(doc, title[:40], len(pages), "pages", flush=True)
    names = {"A": "8421 The Securities Brokers (Licensing and Operations) Rules, 70 pages",
             "B": "8524 The Islamabad Building Regulations, 1963, 55 pages",
             "C": "8428 Regulations for Appointments/Promotions, 21 pages",
             "D": "all the smaller documents"}
    for tag, docs in sorted(groups.items()):
        n = sum(len(d["pages"]) for d in docs)
        root = a.out / f"_pack{tag}"
        rel = [d for d in docs if d["_released"]]
        state = ("All are unreleased: law text typed here becomes part of the reading recorded before release; blank pages are simply recorded."
                 if not rel else f"{len(rel)} of these documents are already RELEASED (their live text lacks the page) and {len(docs) - len(rel)} are not.")
        for d in docs:
            d.pop("_released")
        pk = {"pack": f"remaining-{tag}", "title": f"Remaining empty pages, pack {tag}: {names[tag]}",
              "subtitle": f"{n} pages in {len(docs)} document(s)", "docs": docs}
        (root / "drafts.js").write_text("window.PACK = " + json.dumps(pk, ensure_ascii=False) + ";\n", encoding="utf-8")
        shutil.copy(TEMPLATE, root / "index.html")
        (root / "READ-ME-FIRST.txt").write_text(README.format(
            tag=tag, what=names[tag], rule="=" * 78, docs=f"{n} pages in {len(docs)} document(s): " + ", ".join(
                f"{d['doc']} ({len(d['pages'])})" for d in docs), state=state), encoding="utf-8")
        z = a.out / f"remaining-empty-pages-pack-{tag}-{n}pages.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
            for f in sorted(root.rglob("*")):
                if f.is_file():
                    zf.write(f, Path(f"remaining-pack-{tag}") / f.relative_to(root))
        print("zip", z.name, round(z.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
