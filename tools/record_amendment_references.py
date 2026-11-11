"""Record the amendment footnotes of released instruments (migration 0072, amendment_reference).

SOURCE. The consolidated texts print, at the foot of a page, one entry per amendment:
    '1Subs. by the Law Reforms Ordinance, 1972 (XII of 1972), s. 2, for "..."'
    '2Ins. by Act IV of 2017, s. 4 (w.e.f. 3-10-2017).'
The segmenter sets these aside as role 'footnote' blocks (no provision). This reads every footnote block of a
released English expression (within its block span) that carries amendment wording, splits it at its markers and
records each entry that parses, verbatim.

PARSING -- an entry is recorded only when it OPENS with operation words followed by 'by'/'vide'
('Subs.', 'Ins.', 'Added', 'Omitted', 'Renumbered', 'Rep.', 'Amended', combined with ',', 'and', '&'). Entries in
other shapes ('The words ... were omitted by ...', 'For Statement of Objects ...') are counted and skipped.
  * cited law: the text after 'by' up to the section reference / 'for' / 'w.e.f.' / end;
  * number, kind, year: 'Act XV of 2010', 'Ord. XXI of 2000', 'P.O. No. 4 of 1975', or a title followed by
    '(XII of 1972)'; a two-digit year ('Act I of 05') is read as the earliest year >= the amended instrument's year;
    digits are written as Roman numerals for Acts, Ordinances and Regulations (the corpus's numbering form);
  * title and year: 'the Law Reforms Ordinance, 1972';
  * effective date: 'w.e.f. 3-10-2017' read day-month-year, only if a real date;
  * target: the ONE body/heading/schedule block on the same page whose text carries the same marker before '['
    or '*' ('1[(3) The ...', '1* * *'); otherwise NULL.

Idempotent: a (observation, ordinal, footnote block, entry) already recorded with the same parse is skipped.

    python tools/record_amendment_references.py            # report
    python tools/record_amendment_references.py --apply    # write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_enacted_dates import to_date  # noqa: E402
from record_instrument_numbers import to_roman  # noqa: E402

METHOD = "nizam.amendment_footnote/1"
WORDING = r"(?:subs|ins|added|inserted|substituted|omitted|renumbered|re-numbered|rep|repealed|amended)"
PREFILTER = rf"\m{WORDING}\M\.?,?\s+(by|vide)"
# a footnote marker: 1-3 digits at a boundary, optionally '.', then (optionally one space and) a capital letter --
# '1Subs.', '1 Subs.', '11. Subs'
MARKER = re.compile(r"(?:^|(?<=[\s.;:)\]]))(\d{1,3})\.?\s?(?=[A-Z])")
# what was changed, printed before the operation: 'Section 5-B with marginal heading,', 'New section 6-B,'
LEAD = r"(?:(?:New\s+)?(?:sections?|sub-sections?|clauses?|sub-clauses?|provisos?|explanations?|paragraphs?|paras?|" \
       r"words?|figures?|schedules?)\b[^.;]{0,60}?,?\s*)?"
# what was replaced, printed between the operation and 'by': 'sub-section (3)', 'for the figures "1500",'
MIDDLE = r"(?:\s*(?:sections?|sub-sections?|clauses?|provisos?)\s*[\w().\-]{0,12})?" \
         r"(?:\s*,?\s*for\s+the\s+(?:existing\s+)?(?:words?|figures?|expression|letters?|clause|sub-section|section|" \
         r"full\s*stop|colon|semi-colon|comma)\s*(?:[\"“'‘][^\"”’]{0,200}[\"”’])?\s*,?)?"
OPS = re.compile(rf"^\s*{LEAD}(?P<ops>(?:{WORDING}\.?\s*(?:,|and|&)?\s*)+?){MIDDLE}\s*(?:by|vide)\b\s*(?P<rest>.+)$",
                 re.I | re.S)
OP_MAP = {"subs": "substituted", "substituted": "substituted", "ins": "inserted", "inserted": "inserted",
          "added": "added", "omitted": "omitted", "renumbered": "renumbered", "re-numbered": "renumbered",
          "rep": "repealed", "repealed": "repealed", "amended": "amended"}
CITE_END = re.compile(r",\s*ss?\.\s*\d|,\s*sections?\s+\d|,\s*Art(?:icle)?s?\.?\s*\d|\s+for\s|\(\s*w\.?\s*e\.?\s*f|"
                      r"\bw\.\s*e\.\s*f|;|:|\.\s*$|,?\s*(?:published|passed|made|assented|effective|dated|see)\b|"
                      r",\s*in\s+its\s+application", re.I)
SECTION = re.compile(r",\s*(ss?\.\s*[\dA-Za-z()\-–, ]{1,20}?|sections?\s+[\dA-Za-z()\-–, ]{1,20}?|"
                     r"Art(?:icle)?s?\.?\s*[\dA-Za-z()\-–, ]{1,20}?)(?=[,.(;]|\s+for\s|\s+w\.|$)", re.I)
KIND_NUM = re.compile(r"\b(Act|Ordinance|Ord\.?|President'?s\s+Order|P\.\s*O\.?|Order|Regulation|Reg\.?)\.?\s*"
                      r"(?:No\.?\s*)?([IVXLC]{1,9}|\d{1,3})\s+of\s+(\d{4}|\d{2})\b", re.I)
PAREN_NUM = re.compile(r"\(\s*(?:[A-Za-z. ]+\s)?([IVXLC]{1,9}|\d{1,3})\s+of\s+(\d{4})\s*\)")
# a title may carry parentheses -- 'the Group Insurance (Amendment) Act, 2011' -- but no comma
TITLE = re.compile(r"(?:the\s+)?(?P<title>[A-Z][^,]{2,160}?\b(?P<kw>Act|Ordinance|Order|Regulations?))\s*,?\s*"
                   r"(?P<year>\d{4})\b")
WEF = re.compile(r"(?:w\.?\s*e\.?\s*f\.?|effective\s+from|with\s+effect\s+from)\s*:?\s*(?:the\s+)?"
                 r"(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})", re.I)
WEF_WORDS = re.compile(r"(?:w\.?\s*e\.?\s*f\.?|effective\s+from|with\s+effect\s+from)\s*:?\s*(?:the\s+)?"
                       r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?([A-Za-z]+)\.?,?\s*(\d{4})", re.I)
KIND_OF = {"act": "act", "ordinance": "ordinance", "ord": "ordinance", "ord.": "ordinance", "order": "order",
           "p.o": "order", "p.o.": "order", "po": "order", "regulation": "regulation", "regulations": "regulation",
           "reg": "regulation", "reg.": "regulation"}


def kind_of(word: str) -> str | None:
    w = re.sub(r"\s+", "", word.lower())
    if w.startswith("president"):
        return "order"
    return KIND_OF.get(w) or KIND_OF.get(w.rstrip("."))


def expand_year(y: str, floor: int) -> int | None:
    if len(y) == 4:
        return int(y)
    for century in (1800, 1900, 2000):
        cand = century + int(y)
        if floor <= cand <= date.today().year:
            return cand
    return None


def number_form(raw: str, kind: str | None) -> str | None:
    if raw.isdigit():
        n = int(raw)
        if not 0 < n < 400:
            return None
        return to_roman(n) if kind in ("act", "ordinance", "regulation") else str(n)
    return raw.upper() if re.fullmatch(r"[IVXLC]+", raw.upper()) and raw == raw.upper() else None


def parse_entry(entry: str, amended_year: int) -> dict | None:
    m = OPS.match(entry)
    if not m:
        return None
    ops = sorted({OP_MAP[w.lower().rstrip(".")] for w in re.findall(WORDING, m.group("ops"), re.I)})
    rest = m.group("rest")
    end = CITE_END.search(rest)
    cited = rest[:end.start()] if end else rest
    cited = " ".join(cited.split()).strip(" ,.")
    if len(cited) < 3:
        return None
    out = dict(operations=ops, cited_text=cited[:400], cited_title=None, cited_kind=None, cited_number=None,
               cited_year=None, cited_section=None, effective_from=None)
    kn = KIND_NUM.search(cited)
    t = TITLE.search(cited)
    if t:
        out["cited_title"] = " ".join(t.group("title").split())[:300]
        out["cited_year"] = int(t.group("year"))
        out["cited_kind"] = kind_of(t.group("kw"))
    if kn:
        kind = kind_of(kn.group(1))
        yr = expand_year(kn.group(3), amended_year)
        if kind and yr and (out["cited_year"] in (None, yr)):
            out["cited_kind"], out["cited_year"] = kind, yr
            out["cited_number"] = number_form(kn.group(2), kind)
    elif t:
        p = PAREN_NUM.search(cited)
        if p and int(p.group(2)) == out["cited_year"]:
            out["cited_number"] = number_form(p.group(1), out["cited_kind"])
    if out["cited_year"] and not 1800 <= out["cited_year"] <= 2100:
        out["cited_year"] = None
    s = SECTION.search(rest)
    if s:
        out["cited_section"] = " ".join(s.group(1).split()).strip(" ,")[:40]
    w = WEF.search(rest)
    if w:
        yr = expand_year(w.group(3), 1800 if len(w.group(3)) == 4 else amended_year)
        try:
            d = date(yr, int(w.group(2)), int(w.group(1))) if yr else None
        except ValueError:
            d = None
        if d and d <= date.today():
            out["effective_from"] = d.isoformat()
    if out["effective_from"] is None:
        w = WEF_WORDS.search(rest)
        if w:
            d = to_date(w.group(1), w.group(2), w.group(3))
            if d and d <= date.today():
                out["effective_from"] = d.isoformat()
    return out


def split_entries(text: str) -> list[tuple[str | None, str]]:
    marks = list(MARKER.finditer(text))
    if not marks:
        return [(None, text)]
    out = []
    if marks[0].start() > 0 and text[:marks[0].start()].strip():
        out.append((None, text[:marks[0].start()]))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), text[m.end():end]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dump")
    args = ap.parse_args()
    from nizam.storage.db import connect
    counts: dict[str, int] = {}
    dumped, others = [], []

    def bump(k: str, n: int = 1) -> None:
        counts[k] = counts.get(k, 0) + n

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute(f"""
            SELECT i.source_observation_id, i.expression_ordinal, i.year, i.document_id, t.id, t.page_no, t.text
              FROM v_release_instrument i
              JOIN block_assignment_set s ON s.source_observation_id = i.source_observation_id AND s.is_active
              JOIN provision_block pb ON pb.assignment_set_id = s.id AND pb.role = 'footnote'
              JOIN text_block t ON t.id = pb.block_id
             WHERE coalesce(i.text_language, 'en') = 'en'
               AND t.id BETWEEN coalesce(i.source_start_block_id, t.id) AND coalesce(i.source_end_block_id, t.id)
               AND t.text ~* %s
             ORDER BY i.document_id, t.page_no, t.id""", (PREFILTER,))
        footnotes = cur.fetchall()
        bump("footnote_blocks", len(footnotes))
        cur.execute("""SELECT source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal
                         FROM amendment_reference""")
        done = {tuple(r) for r in cur.fetchall()}
        page_cache: dict[tuple[int, int], list[tuple[int, str]]] = {}
        for obs, ordinal, year, doc, block, page, text in footnotes:
            key = (doc, page)
            if key not in page_cache:
                cur.execute("""SELECT t.id, t.text FROM text_block t
                                 JOIN provision_block pb ON pb.block_id = t.id
                                 JOIN block_assignment_set s ON s.id = pb.assignment_set_id AND s.is_active
                                WHERE t.document_id = %s AND t.page_no = %s
                                  AND pb.role IN ('body', 'heading', 'schedule_row', 'preamble')
                                  AND pb.provision_id IS NOT NULL""", (doc, page))
                page_cache = {key: cur.fetchall()}          # one page at a time keeps memory flat
            body = page_cache[key]
            for n, (marker, entry) in enumerate(split_entries(text or "")):
                if not re.search(PREFILTER.replace(r"\m", r"\b").replace(r"\M", r"\b"), entry, re.I):
                    bump("entries_without_amendment_wording"); continue
                parsed = parse_entry(entry, year or 1800)
                if parsed is None:
                    bump("entries_other_shape")
                    if args.dump and len(others) < 120:
                        others.append(" ".join(entry.split())[:160])
                    continue
                bump("entries_parsed")
                if (obs, ordinal, block, n) in done:
                    bump("already_recorded"); continue
                target = None
                if marker:
                    rx = re.compile(rf"(?<!\d){re.escape(marker)}\s*[\[*]")
                    hits = [b for b, bt in body if bt and rx.search(bt)]
                    if len(hits) == 1:
                        target = hits[0]
                bump("with_target" if target else "without_target")
                bump("with_number" if parsed["cited_number"] else "without_number")
                bump("with_wef" if parsed["effective_from"] else "without_wef")
                evidence = dict(reviewer_type="tool", document_id=doc)
                cur.execute("""INSERT INTO amendment_reference
                        (source_observation_id, expression_ordinal, footnote_block_id, entry_ordinal, source_page,
                         marker, footnote_text, operations, cited_text, cited_title, cited_kind, cited_number,
                         cited_year, cited_section, effective_from, target_block_id, assertion, method, evidence,
                         recorded_by)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'recorded',%s,%s::jsonb,'claude')""",
                            (obs, ordinal, block, n, page, marker, " ".join(entry.split())[:1000],
                             parsed["operations"], parsed["cited_text"], parsed["cited_title"],
                             parsed["cited_kind"], parsed["cited_number"], parsed["cited_year"],
                             parsed["cited_section"], parsed["effective_from"], target, METHOD,
                             json.dumps(evidence)))
                bump("recorded")
                if args.dump and len(dumped) < 3000:
                    dumped.append(dict(doc=doc, page=page, marker=marker, entry=" ".join(entry.split())[:200],
                                       target=target, **parsed))
        if not args.apply:
            conn.rollback()
    if args.dump:
        Path(args.dump).write_text(json.dumps(dict(recorded=dumped, other_shape=others), ensure_ascii=False,
                                              indent=0), encoding="utf-8")
    print(json.dumps(dict(sorted(counts.items())), indent=1))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
