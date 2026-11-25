"""build_readings.py OUT.json -- page readings that open sub-Article/sub-section (1) where it prints on its heading's
line, in the AJK Interim Constitution 1974 (doc 11875, D-140) and the Government of Gilgit-Baltistan Order 2018 (doc
11635, D-143), D-144. Read-only on the database; one reading per page, with a 60 dpi render.

Each block below was read (its text and its page's render): the Article or section number, its heading closed by a
dash, and '(1)' on the same printed line, the sub-Article's words following ('42. Supreme Court of Azad Jammu and
Kashmir.-(1) There shall be ...'; '5. President.- 1[(1) There shall be ...'; '30. 2[Voting in Assembly and quorum.-]
(1) Subject to ...'). The released tree kept (1) in the Article's own text, so its clauses and provisos hung on the
Article and Art. 42(1) had no unit to cite, while (2) onwards were units. Rule reviewed_hyphen_first_subsection (rule
F, doc 4450), with its second form (D-144) for a note marker or a bracketed heading close, cuts the block after the
heading's dash. Four GB sections (7, 51, 77, 91) print their heading and (1) in one block and the sub-section's words
in the next; the rule cuts within one block, so they are not read here (open).
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
BLOCKS = {
    11875: [2913596, 2913827, 2913858, 2913871, 2913912, 2913921, 2914031, 2914054, 2914153, 2914166, 2914411,
            2914420, 2914430, 2914454, 2914491],
    11635: [2903998, 2904272, 2904296, 2904389, 2904401, 2904814, 2904999, 2905103, 2905130, 2905139, 2905329,
            2905351, 2905358, 2905389, 2905398, 2905428, 2905578],
}
NAME = {11875: ("the AJK Interim Constitution 1974", "Article", "sub-Article"),
        11635: ("the Government of Gilgit-Baltistan Order 2018", "section", "sub-section")}
OPENER = re.compile(r"\(\s*1\s*\)")


def main() -> int:
    out = Path(sys.argv[1])
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    readings = []
    with connect() as c, c.cursor() as cur:
        for doc, ids in BLOCKS.items():
            cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id = %s", (doc,))
            rows = cur.fetchall()
            by_id = {i: (p, t or "") for i, p, t in rows}
            by_page = defaultdict(list)
            for i, p, t in rows:
                by_page[p].append(t or "")
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256 = x.sha256 WHERE x.id = %s", (doc,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            pages = defaultdict(list)
            for i in ids:
                if i not in by_id:
                    raise SystemExit(f"doc {doc}: block {i} is not its text block")
                pages[by_id[i][0]].append(i)
            law, unit, sub = NAME[doc]
            for page, pids in sorted(pages.items()):
                printed = []
                for i in pids:
                    text = re.sub(r"\s+", " ", by_id[i][1]).strip()
                    m = OPENER.search(text)
                    if not m:
                        raise SystemExit(f"block {i} prints no (1)")
                    printed.append(f"'{text[:m.end() + 25]} ...' (block {i})")
                # the locator: the first printed line of the first block, unique on the page
                loc = next((ln.strip() for i in pids for ln in by_id[i][1].split("\n") if len(ln.strip()) >= 12
                            and sum(t.count(ln.strip()) for t in by_page[page]) == 1), None)
                if loc is None:
                    raise SystemExit(f"doc {doc} page {page}: no locator line")
                path = f"{REL}/doc{doc}-p{page}.png"
                if not (ROOT / path).exists():
                    pdf[page - 1].get_pixmap(dpi=60).save(ROOT / path)
                readings.append({
                    "document_id": doc, "page_no": page, "match_text": loc, "before_text": loc, "after_text": loc,
                    "render": path, "render_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                    "source_hyphen_first_subsection_blocks": sorted(pids),
                    "defect": f"{sub} (1), printed on its {unit}'s heading line, was read into the {unit}'s own text: "
                              f"(1) had no unit and its clauses and provisos hung on the {unit}",
                    "fixes": "rule reviewed_hyphen_first_subsection: the block is cut after the heading's dash, so "
                             f"{sub} (1) opens; no law text changes",
                    "observed": f"Page {page} of {law} prints " + "; and ".join(printed) + f", each {unit}'s number, "
                                "its heading closed by a dash, and (1) on one line, the words of (1) following"})
    out.write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(readings)} readings over {sum(map(len, BLOCKS.values()))} blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
