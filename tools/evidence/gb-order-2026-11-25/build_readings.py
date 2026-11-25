"""build_readings.py OUT.json -- page readings that repair the Government of Gilgit-Baltistan Order 2018 (doc 11635,
observation 15449, released D-113), D-143. Read-only on the database; one reading per page with a 60 dpi render.

Each page below was read (block dump: x0, y0, text; and its render):
  * The page numbers (folios): each page prints its own number alone at its foot (the lowest block of the page, in the
    page's bottom quarter), and the text layer read it into the sentence crossing the page ('it is found- 37'):
    set aside (reviewed_apparatus_block). 82 pages.
  * Page 37: s.70(5) runs "... shall form part of Federal Consolidated Fund established under / Article 78 of the
    Constitution of Islamic Republic of Pakistan: / Provided that the Federal Government shall provide funds to the
    Council." The wrapped line opens 'Article 78' and was read as an Article 78 of the Order: it is s.70(5)'s own text
    (reviewed_text_unit), and the proviso is s.70(5)'s.
  * Pages 15 and 39 print 'PART. IV-THE GOVERNMENT' and 'PART. XI-THE JUDICATURE', a stop after PART, centred; the part
    grammar took neither, so Part IV's sections sat in Part III and Part XI's heading ran into s.74(3) with ss.75-91
    under Part X (reviewed_printed_rule_opener, kind part).
  * Page 77 prints 'SECOND SCHEDULE / [see section 50(2)(d)]', centred, after the First Schedule's last oath; it was
    read into the First Schedule (reviewed_schedule_heading).
Not changed, as printed: the copy prints no Part V heading (Part IV is followed by Part VI), and 'CHAPTER' on page 4
with no number; no label is invented."""
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.corpus.segment import segment  # noqa: E402
from nizam.storage.db import connect  # noqa: E402

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
DOC = 11635
REL = ".artifacts/gb-order-2026-11-25/renders"
TEXT_UNIT = {"source_block_id": 2904930, "kind": "article", "label": "78"}
OPENERS = [{"source_block_id": 2904336, "label": "IV", "kind": "part", "source_prefix": "PART. IV-THE GOVERNMENT"},
           {"source_block_id": 2904997, "label": "XI", "kind": "part", "source_prefix": "PART. XI-THE JUDICATURE"}]
SCHEDULE = 2905844


def main() -> int:
    out = Path(sys.argv[1])
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    with connect() as c, c.cursor() as cur:
        cur.execute("""SELECT t.id, t.text, t.page_no, t.y0, pg.height, t.x0, t.x1 FROM text_block t
                       JOIN page pg ON pg.document_id=t.document_id AND pg.page_no=t.page_no
                       WHERE t.document_id=%s ORDER BY t.reading_order""", (DOC,))
        blocks = [{"id": i, "text": t or "", "page_no": p, "y0": float(y or 0), "page_height": float(h or 792),
                   "x0": float(x0 or 0), "x1": float(x1 or 0)} for i, t, p, y, h, x0, x1 in cur.fetchall()]
        cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (DOC,))
        pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
    by_id = {b["id"]: b for b in blocks}
    lowest = defaultdict(float)
    for b in blocks:
        lowest[b["page_no"]] = max(lowest[b["page_no"]], b["y0"])
    # folios read as law: only the number, the page's own, its lowest block, in its bottom quarter, and in a provision
    # of the tree the other readings build (as ajk_folio_patch.py: only folios read into the law)
    seg = segment(blocks, structural_overrides={"source_text_units": [TEXT_UNIT], "source_printed_rule_openers": OPENERS,
                                                "source_schedule_heading_blocks": [SCHEDULE]})
    in_law = {b for b, (role, n) in seg.block_roles.items() if n is not None and role in ("body", "heading", "schedule_row")}
    folios = [b["id"] for b in blocks if re.fullmatch(r"\s*\d{1,3}\s*", b["text"]) and int(b["text"]) == b["page_no"]
              and b["y0"] >= lowest[b["page_no"]] and b["y0"] > 0.75 * b["page_height"] and b["id"] in in_law]
    by_page = defaultdict(list)
    for b in blocks:
        by_page[b["page_no"]].append(b)
    used = set()

    def locator(page: int, skip: set) -> str:
        lines = sorted({ln.strip() for b in by_page[page] if b["id"] not in skip for ln in b["text"].split("\n")
                        if len(ln.strip()) >= 12}, key=len, reverse=True)
        for ln in lines:
            if (sum(b["text"].count(ln) for b in by_page[page]) == 1
                    and sum(ln.casefold() in b["text"].casefold() for b in by_page[page]) == 1 and (page, ln) not in used):
                used.add((page, ln))
                return ln
        raise SystemExit(f"page {page}: no locator")

    def reading(page: int, skip: set, **keys) -> dict:
        loc = locator(page, skip)
        path = f"{REL}/doc{DOC}-p{page}.png"
        if not (ROOT / path).exists():
            pdf[page - 1].get_pixmap(dpi=60).save(ROOT / path)
        return {"document_id": DOC, "page_no": page, "match_text": loc, "before_text": loc, "after_text": loc,
                "render": path, "render_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), **keys}

    readings = [reading(37, set(), source_text_units=[TEXT_UNIT],
                        defect="a wrapped cross-reference ('Article 78 of the Constitution of Islamic Republic of "
                               "Pakistan:') was read as an Article 78 of the Order",
                        fixes="rule reviewed_text_unit: the line is s.70(5)'s text, and its proviso s.70(5)'s",
                        observed="Page 37 prints s.70(5) 'All revenues and other moneys raised under the authority of "
                                 "the Prime Minister of Pakistan shall form part of Federal Consolidated Fund "
                                 "established under' (x0 72), then at the same margin 'Article 78 of the Constitution of "
                                 "Islamic Republic of Pakistan:' (block 2904930), then 'Provided that the Federal "
                                 "Government shall provide funds to the Council.' (x0 108), then '71. Budget.-'")]
    for e in OPENERS:
        b = by_id[e["source_block_id"]]
        readings.append(reading(b["page_no"], set(), source_printed_rule_openers=[e],
                                defect=f"Part {e['label']}'s heading, printed with a stop after PART, was not read",
                                fixes="rule reviewed_printed_rule_opener: the block opens the Part; no text changes",
                                observed=f"Page {b['page_no']} prints '{e['source_prefix']}' alone, centred (x0 "
                                         f"{b['x0']:.0f}, block {b['id']}), as every other Part heading of the Order "
                                         "('PART- X', 'PART-XII') is printed"))
    b = by_id[SCHEDULE]
    readings.append(reading(b["page_no"], set(), source_schedule_heading_blocks=[SCHEDULE],
                            defect="the Second Schedule's heading was read into the First Schedule",
                            fixes="rule reviewed_schedule_heading: the block opens its Schedule; no text changes",
                            observed=f"Page {b['page_no']} prints 'SECOND SCHEDULE' (x0 {b['x0']:.0f}, block {SCHEDULE}) "
                                     "and '[see section 50(2)(d)]' centred at its head, after the First Schedule's "
                                     "last oath on page 76"))
    for f in folios:
        b = by_id[f]
        readings.append(reading(b["page_no"], {f}, source_apparatus_blocks=[f],
                                defect="the page's printed number (folio) was read into a provision's text",
                                fixes="rule reviewed_apparatus_block: the folio block is set aside; no law text changes",
                                observed=f"Page {b['page_no']} prints its own number '{b['text'].strip()}' alone at its "
                                         f"foot (block {f}, y0 {b['y0']:.0f} of {b['page_height']:.0f}, the page's "
                                         "lowest block)"))
    out.write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(readings)} readings; folios {len(folios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
