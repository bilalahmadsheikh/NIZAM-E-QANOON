"""build_readings.py OUT.json -- the page readings that settle the AJK Interim Constitution 1974 (doc 11875), D-140.

Each page below was read (block dump: x0, y0, text; and its render). Read-only on the database; writes the readings
tools/record_curation_patch.py records, one per page, with a 60 dpi render and its sha256:

  * Art. 4(4) "The Rights" prints paragraphs 1-24 at x0 216, one step in from the Articles (x0 144), in the same
    "N. Heading.-" grammar: rule reviewed_paragraph_run, owner sub-Article (4) of Article 4, every block of the run
    (pages 21-35; footnotes, running heads and folios are not in it).
  * Ten amendment footnotes, "N. Subs./Ins./Omitted by the (... Amdt.) Act", printed below the page's text at x0 144
    (the Articles' margin) that the parser read as clauses: set aside (reviewed_apparatus_block).
  * The page numbers (folios): page minus 11 (page 12 prints 1), alone at the foot of the page, read into the law's
    text where a sentence crosses the page: set aside, as tools/recrawl/ajk_folio_patch.py does for released AJK laws.
  * The THIRD, FOURTH and FIFTH SCHEDULE headings print behind their amendment marker ('1[THIRD SCHEDULE'): page-read
    Schedule headings (reviewed_schedule_heading).
  * Article 30-A prints with no stop after its number ('2[30-A Restriction on discussion in Assembly, etc.-'), and the
    Third Schedule's two parts print in quotes ('‘PART-A’', '‘PART-B’'): reviewed printed openers.
The prototype tree (block positions) is mapped to the document's text blocks by reading order and text, and refuses
any block whose text differs."""
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
DOC = 11875
REL = ".artifacts/ajk-ic-2026-11-25/renders"
PROTO = json.loads(Path("/mnt/e/nizam-data/acquire/work/ajkic/blocks.json").read_text())
OPEN = re.compile(r"^\s*(?:\d{1,2}\s*\[\s*)?(\d{1,2})\s*\.\s+")
FOOTNOTES = [61, 321, 350, 553, 605, 745, 840, 899, 924, 1008]          # prototype positions, each read below
SCHEDULE_HEADS = [1042, 1116, 1120]
OPENERS = [(488, "30-A", None, "2[30-A Restriction on discussion"),
           (1044, "A", "part", "‘PART-A’"), (1088, "B", "part", "‘PART-B’")]
OWNER = 118                                                             # '(4) The Rights'


def main() -> int:
    out = Path(sys.argv[1])
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, page_no, text, x0, y0 FROM text_block WHERE document_id=%s ORDER BY reading_order", (DOC,))
        rows = cur.fetchall()
        cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (DOC,))
        pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        cur.execute("SELECT page_no, height FROM page WHERE document_id=%s", (DOC,))
        height = {p: float(h) for p, h in cur.fetchall()}
    if len(rows) != len(PROTO):
        raise SystemExit(f"{len(rows)} text blocks, prototype {len(PROTO)}")
    db = {}
    for p, (bid, page, text, _x, _y) in zip(PROTO, rows):
        if p["text"] != text or p["page_no"] != page:
            raise SystemExit(f"prototype block {p['id']} does not match text block {bid}")
        db[p["id"]] = bid
    by_page = defaultdict(list)
    for bid, page, text, x0, y0 in rows:
        by_page[page].append((bid, text or "", float(x0 or 0), float(y0 or 0)))
    proto = {p["id"]: p for p in PROTO}

    run = [p["id"] for p in PROTO if 119 <= p["id"] <= 251 and p["x0"] >= 200
           and not re.fullmatch(r"\d{1,3}", p["text"].strip())]
    openers = [i for i in run if 212 <= proto[i]["x0"] <= 220 and OPEN.match(proto[i]["text"])]
    if [int(OPEN.match(proto[i]["text"]).group(1)) for i in openers] != list(range(1, 25)):
        raise SystemExit("the run's openers are not paragraphs 1-24")
    # folios read as law: a block that is only a number, the lowest block of its page (bottom quarter of an A4 page;
    # its top sits at 79.8% of the height, so ajk_folio_patch.py's 80% line misses it), equal to page - 11, and body text
    # of a provision in the tree the other readings build (as ajk_folio_patch.py: only folios read into the law)
    from nizam.corpus.segment import segment
    seg = segment(PROTO, structural_overrides={
        "source_paragraph_runs": [{"owner_block_id": OWNER, "owner_label": "4", "owner_kind": "subsection",
                                   "opener_block_ids": openers, "run_block_ids": run}],
        "source_apparatus_blocks": FOOTNOTES, "source_schedule_heading_blocks": SCHEDULE_HEADS,
        "source_printed_rule_openers": [{"source_block_id": i, "label": lab, "source_prefix": pre,
                                         **({"kind": k} if k else {})} for i, lab, k, pre in OPENERS]})
    # body text of a provision, or a block a Schedule took into its text (the First and Fifth Schedules: role heading)
    body = {b for b, (role, n) in seg.block_roles.items() if n is not None and role in ("body", "heading", "schedule_row")}
    folios = [p["id"] for p in PROTO if re.fullmatch(r"\s*\d{1,3}\s*", p["text"]) and p["id"] in body
              and int(p["text"]) == p["page_no"] - 11 and p["y0"] > 0.75 * p["page_height"]
              and p["y0"] >= max(q["y0"] for q in PROTO if q["page_no"] == p["page_no"])]

    readings, used_lines = [], set()

    def locator(page: int, skip: set) -> str:
        """A line of law text on the page, 12+ chars, printed once on it (never in a block set aside)."""
        lines = sorted({ln.strip() for bid, t, _x, _y in by_page[page] if bid not in skip
                        for ln in t.split("\n") if len(ln.strip()) >= 12
                        and not re.fullmatch(r"AJ&K INTERIM CONSTITUTION", ln.strip())}, key=len, reverse=True)
        for ln in lines:
            if (sum(t.count(ln) for _b, t, _x, _y in by_page[page]) == 1
                    and sum(ln.casefold() in t.casefold() for _b, t, _x, _y in by_page[page]) == 1
                    and (page, ln) not in used_lines and not re.match(r"\s*\d{1,2}\.\s+(?:Subs|Ins|Omitted|Added|Sub\b)", ln)):
                used_lines.add((page, ln))
                return ln
        raise SystemExit(f"page {page}: no locator")

    def render(page: int) -> tuple[str, str]:
        path = f"{REL}/doc{DOC}-p{page}.png"
        if not (ROOT / path).exists():
            pdf[page - 1].get_pixmap(dpi=60).save(ROOT / path)
        return path, hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

    def reading(page: int, skip: set, **keys) -> dict:
        loc = locator(page, skip)
        path, sha = render(page)
        return {"document_id": DOC, "page_no": page, "match_text": loc, "before_text": loc, "after_text": loc,
                "render": path, "render_sha256": sha, **keys}

    # 1. the paragraph run (page 21, where Article 4 and its sub-Article (4) print)
    spec = {"owner_block_id": db[OWNER], "owner_label": "4", "owner_kind": "subsection",
            "opener_block_ids": [db[i] for i in openers], "run_block_ids": [db[i] for i in run]}
    readings.append(reading(
        21, set(), source_paragraph_runs=[spec],
        defect="the 24 rights of Art. 4(4) were read as Articles: paragraph 5 as Article 5, 6-24 as Articles 6-24, the "
               "real Articles 5-24 as clauses (33 repeated labels)",
        fixes="rule reviewed_paragraph_run: the run is rebuilt under sub-Article (4) of Article 4; Articles 5-24 follow "
              "Article 4 in sequence; no law text changes",
        observed="Page 21 prints Article 4 (x0 144), its sub-Articles (1)-(3) and '(4) The Rights' (x0 180), then "
                 "'1. Security of person.-' and '2. Safeguard as to arrest and detention.-' at x0 216; pages 22-35 "
                 "continue the paragraphs to '24. Preservation of language, script and culture.-' (page 35, x0 216), "
                 "after which page 35 prints '5. President.-' at the Articles' margin, x0 144. Each paragraph's own "
                 "sub-paragraphs (1), (a), (i) are indented further (x0 249-279). The run is the 95 blocks between, less "
                 "the footnotes (x0 144, below each page's rule), running heads and folios."))

    # 2. footnotes and folios set aside, one reading per page
    aside = defaultdict(list)
    for i in FOOTNOTES:
        aside[proto[i]["page_no"]].append(("note", i))
    for i in folios:
        aside[proto[i]["page_no"]].append(("folio", i))
    for page, items in sorted(aside.items()):
        ids = sorted(db[i] for _k, i in items)
        what = []
        for kind, i in items:
            t = re.sub(r"\s+", " ", proto[i]["text"]).strip()
            what.append(f"its folio '{t}' alone at its foot (block {db[i]}; the document's folios run at page - 11)"
                        if kind == "folio" else
                        f"the amendment footnote '{t[:70]}' below its text at x0 {proto[i]['x0']:.0f}, y0 "
                        f"{proto[i]['y0']:.0f} (block {db[i]})")
        try:
            readings.append(reading(
                page, set(ids), source_apparatus_blocks=ids,
                defect="page apparatus (an amendment footnote or the page's folio) read as law",
                fixes="rule reviewed_apparatus_block: the block is set aside; no law text changes",
                observed=f"Page {page} prints " + "; and ".join(what)))
        except SystemExit:
            # a page holding only apparatus (p99: Article 59's footnote 4, its running head and folio) has no law line
            # to anchor a reading: a reading on the page before names it, citing this page's render
            path, sha = render(page)
            anchored = reading(
                page - 1, set(), source_apparatus_blocks=ids,
                defect="page apparatus (an amendment footnote or the page's folio) read as law",
                fixes="rule reviewed_apparatus_block: the block is set aside; no law text changes",
                observed=f"Page {page}, which prints no law text (its additional render), prints " + "; and ".join(what))
            anchored["additional_render"], anchored["additional_render_sha256"] = path, sha
            readings.append(anchored)
    print("folio pages", sorted({proto[i]["page_no"] for i in folios}))

    # 3. Schedule headings behind their amendment marker
    for page in sorted({proto[i]["page_no"] for i in SCHEDULE_HEADS}):
        ids = [db[i] for i in SCHEDULE_HEADS if proto[i]["page_no"] == page]
        heads = [re.sub(r"\s+", " ", proto[i]["text"]).strip() for i in SCHEDULE_HEADS if proto[i]["page_no"] == page]
        readings.append(reading(
            page, set(), source_schedule_heading_blocks=ids,
            defect="a Schedule heading printed behind its amendment marker was not read as a Schedule",
            fixes="rule reviewed_schedule_heading: the block opens its Schedule; no law text changes",
            observed=f"Page {page} prints the centred display heading(s) {heads} (block(s) {ids}), each followed by "
                     "'[See Article ...]', opening a new Schedule after the one before it"))

    # 4. printed openers the grammar does not take
    for i, label, kind, prefix in OPENERS:
        page = proto[i]["page_no"]
        if not proto[i]["text"].lstrip().startswith(prefix):
            raise SystemExit(f"opener {i} does not start with {prefix!r}")
        entry = {"source_block_id": db[i], "label": label, "source_prefix": prefix, **({"kind": kind} if kind else {})}
        readings.append(reading(
            page, set(), source_printed_rule_openers=[entry],
            defect=("Article 30-A, printed with no stop after its number, was read into Article 30" if label == "30-A"
                    else f"the Third Schedule's Part-{label}, printed in quotes, was not read as a part"),
            fixes="rule reviewed_printed_rule_opener: the block opens the unit; no law text changes",
            observed=(f"Page {page} prints '{prefix} in Assembly, etc.- No discussion shall take place in the Assembly' at "
                      "the Articles' margin (x0 144), between Article 30's sub-Article (2) and '30-B. Finance Committee.-'"
                      if label == "30-A" else
                      f"Page {page} prints '{prefix}' alone, centred (block {db[i]}), above the Third Schedule's items "
                      "numbered from 1")))
    out.write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(readings)} readings; run {len(run)} blocks, {len(openers)} openers; footnotes {len(FOOTNOTES)}, "
          f"folios {len(folios)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
