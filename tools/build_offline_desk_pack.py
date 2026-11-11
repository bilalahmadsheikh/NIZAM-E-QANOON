"""Build an offline proofreading-desk pack: one folder (and zip) holding the page images, the machine OCR text of every
page and a standalone desk page that saves in the browser and exports nizam.desk-pages/1 JSON -- the same export the
claude.ai Gazette Proofreading Desk makes, so tools/recrawl desk2read.py reads it unchanged. Read-only on the database.

    ./.venv/bin/python tools/build_offline_desk_pack.py --pack p1 --out .artifacts/owner-packs/pack-1 \
        --title "..." --subtitle "..." --doc 9633 --doc 9764 --priority 9854=22,47 --note 9854="why"

The pack never adjudicates, records or releases anything; the owner's export is checked against the page images
before anything is recorded."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from nizam.storage.db import connect

TEMPLATE = Path(__file__).with_name("offline_desk_template.html")
DATA = Path("/mnt/e/nizam-data")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--doc", type=int, action="append", required=True)
    ap.add_argument("--priority", action="append", default=[], help="DOC=p1,p2,...")
    ap.add_argument("--note", action="append", default=[], help="DOC=text")
    ap.add_argument("--readme", type=Path, help="text file copied in as READ-ME-FIRST.txt")
    ap.add_argument("--dpi", type=int, default=120)
    ap.add_argument("--pages", action="append", default=[], help="DOC=FIRST-LAST: only these pages of that document")
    ap.add_argument("--pick", action="append", default=[], help="DOC=p1,p2,...: exactly these pages of that document")
    ap.add_argument("--drafts", type=Path, help="JSON {\"DOC:PAGE\": text}: the text shown as the page draft instead of the stored OCR")
    ap.add_argument("--hints", type=Path, help="JSON {\"DOC:PAGE\": hint}: a line shown above the page (what to look at)")
    ap.add_argument("--tesseract-empty", action="store_true",
                    help="a page with no stored text gets a local tesseract draft (a typing aid, not evidence)")
    a = ap.parse_args()
    page_range = {int(k): tuple(int(x) for x in v.split("-")) for k, v in (s.split("=", 1) for s in a.pages)}
    prio = {int(k): [int(x) for x in v.split(",")] for k, v in (s.split("=", 1) for s in a.priority)}
    pick = {int(k): [int(x) for x in v.split(",")] for k, v in (s.split("=", 1) for s in a.pick)}
    drafts = json.loads(a.drafts.read_text(encoding="utf-8")) if a.drafts else {}
    hints = json.loads(a.hints.read_text(encoding="utf-8")) if a.hints else {}
    notes = {int(k): v for k, v in (s.split("=", 1) for s in a.note)}
    img_dir = a.out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    docs = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        for doc in a.doc:
            cur.execute("""SELECT b.object_key, coalesce(i.short_title, ''), d.page_count
                             FROM document d JOIN blob b ON b.sha256=d.sha256
                             LEFT JOIN instrument i ON i.document_id=d.id AND i.is_active AND i.duplicate_of IS NULL
                            WHERE d.id=%s AND d.is_active LIMIT 1""", (doc,))
            key, title, n_pages = cur.fetchone()
            cur.execute("SELECT page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order, id", (doc,))
            ocr: dict[int, list[str]] = {}
            for p, t in cur.fetchall():
                if (t or "").strip():
                    ocr.setdefault(p, []).append(t.strip())
            tmp = a.out / f"_r{doc}"
            tmp.mkdir(exist_ok=True)
            lo, hi = page_range.get(doc, (1, n_pages))
            plist = pick.get(doc) or list(range(lo, hi + 1))
            if doc in pick:     # a list of pages (the ones that failed the text gate), not one range
                for p in plist:
                    subprocess.run(["pdftoppm", "-r", str(a.dpi), "-jpeg", "-jpegopt", "quality=72", "-f", str(p), "-l", str(p),
                                    "-singlefile", str(DATA / key), str(tmp / f"p-{p}")], check=True)
            else:
                subprocess.run(["pdftoppm", "-r", str(a.dpi), "-jpeg", "-jpegopt", "quality=72", "-f", str(lo), "-l", str(hi),
                                str(DATA / key), str(tmp / "p")], check=True)
            if a.tesseract_empty:
                for p in plist:
                    if p in ocr:
                        continue
                    png = tmp / f"o{p}"
                    subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png", "-f", str(p), "-l", str(p), "-singlefile",
                                    str(DATA / key), str(png)], check=True)
                    out = subprocess.run(["tesseract", str(png) + ".png", "stdout", "--psm", "4", "-l", "eng"],
                                         capture_output=True, text=True).stdout
                    ocr[p] = [x.strip() for x in re.split(r"\n\s*\n", out) if x.strip()]
                    print("  tesseract page", p, len(out), "chars", flush=True)
            for f in tmp.glob("p-*.jpg"):
                n = int(re.search(r"-(\d+)\.jpg$", f.name).group(1))
                f.replace(img_dir / f"doc{doc}-p{n}.jpg")
            shutil.rmtree(tmp)
            pages = [{"page": p, "img": f"img/doc{doc}-p{p}.jpg",
                      "ocr": drafts.get(f"{doc}:{p}", "\n\n".join(ocr.get(p, []))),
                      **({"hint": hints[f"{doc}:{p}"]} if f"{doc}:{p}" in hints else {})}
                     for p in plist if (img_dir / f"doc{doc}-p{p}.jpg").exists()]
            docs.append({"doc": doc, "title": f"{title} (document {doc})", "note": notes.get(doc, ""),
                         "priority": prio.get(doc, []), "pages": pages})
            print(doc, title[:50], len(pages), "pages", flush=True)
    pack = {"pack": a.pack, "title": a.title, "subtitle": a.subtitle, "docs": docs}
    (a.out / "drafts.js").write_text("window.PACK = " + json.dumps(pack, ensure_ascii=False) + ";\n", encoding="utf-8")
    shutil.copy(TEMPLATE, a.out / "index.html")
    if a.readme:
        shutil.copy(a.readme, a.out / "READ-ME-FIRST.txt")
    zpath = a.out.with_suffix(".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(a.out.rglob("*")):
            if f.is_file():
                z.write(f, Path(a.pack + "-pack") / f.relative_to(a.out))
    print("zip", zpath, zpath.stat().st_size // 1_000_000, "MB")


if __name__ == "__main__":
    main()

