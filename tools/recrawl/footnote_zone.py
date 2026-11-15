"""footnote_zone.py OUT.json DOC... : page footnotes read into provisions, found from the printed footnote rule.

AJK code volumes (law.gok.pk, landed 14 Nov 2026) print amendment footnotes below a short horizontal rule at the foot of
the page, and a revised volume's note often reproduces the superseded text in full ('The original extract of the Sec. 6
is reproduced as under:- "6. Aims and Objectives ... (a) ... (e) ..."', doc 10092 p6). The segmenter's footnote grammar
took the notes it recognises; the rest -- notes opening 'Sec. 6 subs. by', 'A. Cl (e) ...', and every block of a
reproduced original -- were read into the law as provisions.

The rule is read from the PDF itself (pymupdf drawings): a horizontal stroke or thin filled rectangle, at most 2pt tall,
5-60% of the page width, starting in the left 40% of the page, below the top 25% of the page; on a page with several,
the lowest one with footnote text below it. A block is in the footnote zone when its top lies below the rule, it is
set at least 1pt smaller than the law (the size carrying most characters in the document, from the PDF's spans) and it
is not a bare folio ('567'). The size test is what tells a footnote rule from a heading's underline, which the drawings
alone cannot (doc 10092 p1: an underline at y=438 followed by '(a) "Board" means ...' at the law's size). Read-only on
the database. Writes, per page with zone blocks that the active tree reads as 'body'
(provision_block), one tools/recrawl/patch.sh record setting those blocks aside (rule reviewed_apparatus_block: the
block stays in the ledger as a footnote and cannot open or absorb a provision). Prints a census line per document."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
import pymupdf  # noqa: E402

from nizam.storage.db import connect  # noqa: E402

CORPUS = Path("/mnt/e/nizam-data")
FOLIO = re.compile(r"^\s*\d{1,4}\s*$")
# --star-notes: an editor's note as the CDA compilations print it -- stars (and '&') then the note's own words, never a
# '*' bullet before law text ('*  Study leave up to 3 months ...', doc 9911 p92)
STAR_NOTE = re.compile(r"\s*\*+[&*\s]*(?:Inserted|Substituted|Added|Omitted|Amended|Deleted|No\s*\.)", re.I)
MARKER = re.compile(r"^\s*(?:\d{1,3}\s|[A-Z]\.\s|\*+|_{5,}|\(\s*[a-z]{1,2}\s*\)\s|\(\s*[ivx]{1,5}\s*\)\s)")


def mid(b) -> float:
    """Where a block counts as lying: 3pt above its bottom edge. A footnote's superscript marker lifts a one-line note's
    top edge -- even its centre -- above the rule (doc 10861 p3: block 630-642, rule 638), while law text printed above
    a rule ends above it."""
    return float(b[3]) - 3


def rules_on(page) -> list[float]:
    """Candidate footnote rules. A stroke with a VERTICAL stroke anywhere below it on the page is a table's line, not a
    footnote rule: the schedule pages of doc 10912 carry 25-35 vertical strokes and their small-type rows ('6 Services
    provided by property developers ... 9818.1000 Sixteen Percent') are law; no footnote page read carries any."""
    w, h = page.rect.width, page.rect.height
    ys, verticals = [], []
    for d in page.get_drawings():
        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                x0, x1, y0, y1 = min(p1.x, p2.x), max(p1.x, p2.x), min(p1.y, p2.y), max(p1.y, p2.y)
            elif item[0] == "re":
                r = item[1]; x0, x1, y0, y1 = r.x0, r.x1, r.y0, r.y1
            else:
                continue
            if x1 - x0 <= 2 and y1 - y0 > 2:
                verticals.append(y1)
            elif y1 - y0 <= 2 and 0.05 * w <= x1 - x0 <= 0.6 * w and x0 <= 0.4 * w and y0 >= 0.25 * h:
                ys.append((y0 + y1) / 2)
    # >= y - 1: a table's bottom line is where its verticals end
    return sorted(y for y in ys if not any(v >= y - 1 for v in verticals))


def span_sizes(page) -> list[tuple[float, float, float, float, float, int]]:
    """(x0, y0, x1, y1, size, chars) for every non-blank span on the page."""
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for s in line["spans"]:
                n = len(s["text"].strip())
                if n:
                    x0, y0, x1, y1 = s["bbox"]
                    out.append((x0, y0, x1, y1, round(s["size"], 1), n))
    return out


def block_size(spans, x0, y0, x1, y1, largest: bool = False) -> float | None:
    """The size carrying most characters among the spans whose centre lies in the block's box (largest=True: the
    largest size any of them carries)."""
    tally: dict[float, int] = defaultdict(int)
    for sx0, sy0, sx1, sy1, size, n in spans:
        cx, cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
        if x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1:
            tally[size] += n
    if not tally:
        return None
    return max(tally) if largest else max(tally, key=tally.get)


def page_zone(blocks: list, rules: list[float], small: set, zone_before: bool) -> tuple[float | None, list, bool]:
    """(rule, zone blocks, page prints a footnote zone) for one page.

    blocks are (id, page_no, y0, y1, text, ...); rules the candidate rule ys; small the ids set smaller than the law.
    The rule is the HIGHEST stroke below which every non-folio block is small (and one is): a heading's underline in the
    law has law-sized text below it, and an underline inside a note ('Aims and Objectives', doc 10092 p6: strokes at
    263, 446, 505; the rule is 446) lies below the real rule. The zone is the small, non-folio blocks below it, top first;
    it counts only when its first block opens with a note marker or the previous page printed a zone."""
    # below a rule: ends below it and does not START well above it. A block that straddles the rule fuses the law's last
    # lines with the note (doc 9958 p2: '3["(3) Fund.- (1) There shall be ...' at 12pt running past the rule) -- it is
    # neither law below the rule nor a note to set aside, and is left for a page-read text cut.
    def below(y):
        return [b for b in blocks if mid(b) > y and float(b[2]) > y - 12 and not FOLIO.match(b[4])]
    rule = next((y for y in sorted(rules) if below(y) and all(b[0] in small for b in below(y))), None)
    if rule is None:
        return None, [], False
    zone = sorted((b for b in below(rule) if b[0] in small), key=lambda b: float(b[2]))
    opens = bool(zone) and (MARKER.match(zone[0][4]) is not None or zone_before)
    return rule, zone if opens else [], opens


def main() -> int:
    # --star-notes (ICT CDA compilations, 15 Nov 2026): the editor's notes there open with '*' ('*Inserted vide
    # No.CDA-7(01)(21)-HRD-III(Sec-VI)/2022/516 Dated 15-06-2022') and are set at the LAW's size, so the size test never
    # takes them; with the flag a block below the rule that opens with '*' counts as small. The rule and the
    # every-block-below-is-a-note test still apply.
    star = "--star-notes" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--star-notes"]
    out, docs = args[0], [int(d) for d in args[1:]]
    recs, census = [], []
    with connect() as conn, conn.cursor() as cur:
        for doc in docs:
            cur.execute("""SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s""", (doc,))
            key = cur.fetchone()[0]
            cur.execute("""SELECT b.id, b.page_no, b.y0, b.y1, b.text,
                                  (SELECT pb.role FROM provision_block pb JOIN provision p ON p.id=pb.provision_id
                                     AND p.is_active WHERE pb.block_id=b.id LIMIT 1), b.x0, b.x1
                             FROM text_block b WHERE b.document_id=%s ORDER BY b.reading_order""", (doc,))
            by_page = defaultdict(list)
            for row in cur.fetchall():
                by_page[row[1]].append(row)
            pdf = pymupdf.open(CORPUS / key)
            # the law's own type size: the size carrying most characters ABOVE each page's lowest candidate rule (where
            # notes outweigh the law -- docs 10912, 9958 -- a whole-page count would make the note size the law's)
            sizes = {p: span_sizes(pdf[p - 1]) for p in by_page}
            rules = {p: rules_on(pdf[p - 1]) for p in by_page}
            weight: dict[float, int] = defaultdict(int)
            for p, spans in sizes.items():
                top = min(rules[p]) if rules[p] else float("inf")
                for _x0, sy0, _x1, _y1, size, n in spans:
                    if sy0 < top:
                        weight[size] += n
            body_size = max(weight, key=weight.get) if weight else None
            taken_doc = 0
            zone_before = False   # the previous page printed a footnote zone (a note may run on to the next page)
            for page_no, blocks in sorted(by_page.items()):
                ys = rules[page_no]
                # a block is a footnote when it lies below a printed rule AND is set at least 1pt smaller than the law
                # (a heading's underline is followed by text at the law's size, and is never taken)
                # EVERY span small, not most of its characters: a block that fuses the law's last line with the note
                # under it (doc 11262 p2: '(b) The rates of income-tax and super-tax referred to in' + the note) is not
                # set aside -- that would cut law text; it is left for a page-read text cut
                small = {b[0] for b in blocks if body_size and (bs := block_size(sizes[page_no], float(b[6]), float(b[2]),
                                                                                  float(b[7]), float(b[3]), largest=True))
                         is not None and bs <= body_size - 1}
                if star:
                    small |= {b[0] for b in blocks if STAR_NOTE.match(b[4] or "")}
                # a footnote zone opens with a note marker ('1 Sec. 6 subs. by', 'A. Cl (e)', '*', a second rule '____')
                # or continues the previous page's notes; small text under a table rule does neither and is not taken
                rule, zone, zone_before = page_zone(blocks, ys, small, zone_before)
                body = [b for b in zone if b[5] == "body"]
                if not body:
                    continue
                taken_doc += len(body)
                first = re.sub(r"\s+", " ", body[0][4]).strip()
                recs.append({"document_id": doc, "page_no": page_no, "source_apparatus_blocks": [b[0] for b in body],
                             "defect": "page footnotes printed below the footnote rule (amendment notes, and the "
                                       "superseded text a revised volume reproduces in them) were read into the law as "
                                       "provision text",
                             "fixes": "rule reviewed_apparatus_block: the blocks below the printed footnote rule are set "
                                      "aside as footnotes; no law text changes",
                             "observed": f"Page {page_no} prints a footnote rule at y={rule:.0f} of "
                                         f"{pdf[page_no - 1].rect.height:.0f}; below it {len(zone)} block(s) set smaller "
                                         f"than the law's {body_size}pt, "
                                         f"{len(body)} read as body, the first {first[:120]!r}",
                             "render": f".artifacts/release-work-2026-09-24/claude/renders/doc{doc}-p{page_no}.png"})
            census.append((doc, taken_doc))
            print(f"{doc}: {taken_doc} footnote-zone block(s) read as body", flush=True)
    json.dump(recs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{sum(1 for _, n in census if n)} of {len(census)} documents, {len(recs)} pages, "
          f"{sum(n for _, n in census)} blocks -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
