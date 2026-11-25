"""build_readings_d147.py OUT.json -- page readings that open sub-section (1) in the four sections of the Government of
Gilgit-Baltistan Order 2018 (doc 11635) that D-145 left open (D-147). Read-only on the database; one reading per page,
with a 60 dpi render (build_readings.py's form).

Each block below was read (its text and its page's render):
  - ss.7 and 91 print the heading over two lines; the dash and (1) close the second, the sub-section's words following
    on that line ('void.-(1) Any law, ...'; 'etc.-(1) The Chief Court shall ...'). The block read is the second line's.
  - ss.51 and 77 print the heading and (1) on one line, closing it ('... circumstances.- (1)'), and the sub-section's
    words open the next line ('The seat of a member ...'); rule F's third form (D-147) cuts after the dash when (1)
    closes the block.
The released tree kept (1) in the section's own text, so s.51's clauses (a)-(e) hung on the section beside (2)-(4).
"""
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect  # noqa: E402

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/first-subsection-2026-11-25/renders"
DOC = 11635
BLOCKS = {2904022: "7", 2904580: "51", 2905112: "77", 2905344: "91"}
LOCATOR_BLOCK = {2905344: 2905343}
OPENER = re.compile(r"\(\s*1\s*\)")


def main() -> int:
    out = Path(sys.argv[1])
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    readings = []
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id = %s", (DOC,))
        rows = cur.fetchall()
        by_id = {i: (p, t or "") for i, p, t in rows}
        by_page = defaultdict(list)
        for i, p, t in rows:
            by_page[p].append(t or "")
        cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256 = x.sha256 WHERE x.id = %s", (DOC,))
        pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        pages = defaultdict(list)
        for i in BLOCKS:
            if i not in by_id:
                raise SystemExit(f"block {i} is not a text block of doc {DOC}")
            pages[by_id[i][0]].append(i)
        for page, pids in sorted(pages.items()):
            printed = []
            for i in pids:
                text = re.sub(r"\s+", " ", by_id[i][1]).strip()
                m = OPENER.search(text)
                if not m:
                    raise SystemExit(f"block {i} prints no (1)")
                printed.append(f"s.{BLOCKS[i]}: '{text[:m.end() + 25]}' (block {i})")
            # page 52's first line of block 2905344 is already the locator of a D-143 patch, which the recorder reads
            # as this patch recorded; the heading's first line (block 2905343) locates this one
            src = [LOCATOR_BLOCK.get(i, i) for i in pids]
            loc = next((ln.strip() for i in src for ln in by_id[i][1].split("\n") if len(ln.strip()) >= 12
                        and sum(t.count(ln.strip()) for t in by_page[page]) == 1), None)
            if loc is None:
                raise SystemExit(f"page {page}: no locator line")
            path = f"{REL}/doc{DOC}-p{page}.png"
            if not (ROOT / path).exists():
                pdf[page - 1].get_pixmap(dpi=60).save(ROOT / path)
            readings.append({
                "document_id": DOC, "page_no": page, "match_text": loc, "before_text": loc, "after_text": loc,
                "render": path, "render_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                "source_hyphen_first_subsection_blocks": sorted(pids),
                "defect": "sub-section (1), printed at its section's heading, was read into the section's own text: "
                          "(1) had no unit and its clauses hung on the section",
                "fixes": "rule reviewed_hyphen_first_subsection (its third form where (1) closes the block, D-147): "
                         "the block is cut after the heading's dash, so sub-section (1) opens; no law text changes",
                "observed": f"Page {page} of the Government of Gilgit-Baltistan Order 2018 prints "
                            + "; and ".join(printed) + ": the heading closed by a dash and (1), the words of (1) "
                            "following on that line or opening the next"})
    out.write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(readings)} readings over {len(BLOCKS)} blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
