"""Record the printed number of released Acts, Ordinances, Orders and Regulations that have none (0070, field number).

Pakistani instruments print their number under the title: 'ACT NO. X OF 2014', 'Ordinance No. XII of 2001',
'(Balochistan Act No. XIV of 2015)', '(West Pakistan Act XX of 1958)', '(XVI of 1950)'. The segmenter left 4,391
released instruments without one. This reads it from the instrument's own TITLE REGION and records it with the
verbatim quote and block.

THE TITLE REGION. The instrument's blocks from source_start_block_id (at most 80, never past source_end_block_id),
cut at the first long-title / preamble / enacting / first-section marker ('An Act to', 'An Ordinance further to',
'WHEREAS', 'It is hereby enacted', 'Preamble', section 1 in its BODY form '1. (1) This Act' or 'Short title ...
—(1)'; a contents line '1. Short title and commencement' does not cut). With no marker the region is only the first
20 blocks. A number cited in the long title or body (the Act being amended, a repealed Ordinance) is therefore never
read. Earlier assertions of this method that the current rules no longer reproduce are withdrawn on each run.

A NUMBER IS RECORDED ONLY WHEN
  * its year equals the instrument's year;
  * a kind word, if printed with it, agrees with the instrument's kind (Act/act, Ordinance/ordinance,
    Order/order, Regulation/regulation); the bare '(XVI of 1950)' form is accepted for acts and ordinances only;
  * it is a canonical Roman numeral (1..399) or a plain number (1..999) -- OCR noise such as 'XIl' is refused;
  * it is the ONLY distinct number in the title region satisfying the above.
Everything else stays NULL. A number is never inferred from the catalogue or from neighbouring instruments.

    python tools/record_instrument_numbers.py            # report
    python tools/record_instrument_numbers.py --apply    # write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METHOD = "nizam.printed_instrument_number/1"
KINDS = {"act": ("act",), "ordinance": ("ordinance",), "order": ("order",), "regulation": ("regulation",)}
OF = r"(?:of|oF|Of|OF|0f|or|OR)"   # 'or' is the common OCR reading of 'of'; the year must still match exactly
NUM = r"([IVXLC]{1,9}|\d{1,3})"
# 'Act No. X of 2014', 'ORDINANCE NUMBER XVIII OF 1959', 'Act XX of 1958'
WITH_KIND = re.compile(rf"\b(Act|Ordinance|Order|Regulation)\s*(?:No\.?|Number|No)?\s*[:.]?\s*{NUM}\s+{OF}\s*(\d{{4}})\b",
                       re.I)
# A different instrument's title closing just before the number ('... ABAD ACT, 2009 SINDH ACT NO: XIX OF 2010'):
# the number then belongs to the instrument printed before this one in the same file.
FOREIGN_TITLE = re.compile(r"\b(?:ACT|ORDINANCE|ORDER|REGULATIONS?|RULES)\s*,?\s*(\d{4})\b", re.I)
# '(XVI of 1950)'
BARE = re.compile(rf"\(\s*{NUM}\s+{OF}\s+(\d{{4}})\s*\)")
STOP = re.compile(r"\bAn?\s+(?:Act|Ordinance|Order|Regulation)\s+(?:to|further|for|so|relating|providing|"
                  r"making|whereby)\b|\bWHEREAS\b|\bWhereas\b|It is hereby (?:enacted|ordained)|\bPreamble\b|"
                  # section 1 in its BODY form only: a contents line '1. Short title and commencement' must not cut
                  # the region before the title that follows the contents page
                  r"(?:^|\s)1\.\s*(?:\(1\)\s*)?(?:This|These)\b|Short title[^.\n]{0,60}?[—–-]+\s*\(1\)", re.S)
BLOCKS = 80   # a long contents page can put the title past block 40
NO_STOP_BLOCKS = 20   # with no title-end marker the region is only the first 20 blocks: past that is body text
                      # (doc 6701: 'Election Commission Order, 2002 (C.E's Order No. I of 2002)' cited in section 3)


def title_region(blocks: list[tuple[int, int, str]]) -> tuple[str, list[tuple[int, int, int, int]], object]:
    """(region text, [(start, end, block_id, page)], stop match) for an instrument's leading blocks."""
    text, spans = "", []
    for bid, page, btxt in blocks:
        spans.append((len(text), len(text) + len(btxt), bid, page))
        text += btxt + "\n"
    stop = STOP.search(text)
    if stop:
        return text[:stop.start()], spans, stop
    cut = spans[min(NO_STOP_BLOCKS, len(spans)) - 1][1] if spans else 0
    return text[:cut], spans, None
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_value(s: str) -> int | None:
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total if 0 < total < 400 and to_roman(total) == s else None


def to_roman(n: int) -> str:
    out = ""
    for v, r in ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += r; n -= v
    return out


def normalise(raw: str) -> str | None:
    raw = raw.strip()
    if raw.isdigit():
        n = int(raw)
        # a lone '1' is as often the OCR reading of the numeral 'I' as a printed '1'; it is not recorded
        return str(n) if 1 < n < 1000 else None
    up = raw.upper()
    if raw != up:          # mixed case such as 'XIl' or 'Il' is OCR noise, not a numeral
        return None
    return up if roman_value(up) else None


def withdraw(cur, obs: int, ordinal: int, field: str, method: str, reason: str) -> None:
    cur.execute("""INSERT INTO instrument_metadata_assertion
                     (source_observation_id, expression_ordinal, field, value, assertion, basis, method, evidence,
                      recorded_by)
                   VALUES (%s, %s, %s, NULL, 'withdrawn', 'recheck_not_reproduced', %s, %s::jsonb, 'claude')""",
                (obs, ordinal, field, method, json.dumps(dict(reviewer_type="tool", reason=reason))))


def latest_withdrawn(cur, field: str) -> set[tuple[int, int]]:
    """Expressions whose latest assertion for `field` is a withdrawal: a recorder never re-asserts those."""
    cur.execute("""SELECT source_observation_id, expression_ordinal FROM (
                       SELECT DISTINCT ON (source_observation_id, expression_ordinal) *
                         FROM instrument_metadata_assertion WHERE field = %s
                        ORDER BY source_observation_id, expression_ordinal, recorded_at DESC, id DESC) l
                    WHERE assertion = 'withdrawn'""", (field,))
    return {(r[0], r[1]) for r in cur.fetchall()}


def candidates(text: str, kind: str, year: int) -> set[tuple[str, int, int]]:
    """(number, start, end) of every acceptable number in the title-region text."""
    found = set()
    for m in WITH_KIND.finditer(text):
        word, raw, yr = m.group(1).lower(), m.group(2), int(m.group(3))
        if yr != year or word not in KINDS.get(kind, ()):
            continue
        if any(int(f.group(1)) != year for f in FOREIGN_TITLE.finditer(text[max(0, m.start() - 80):m.start()])):
            continue
        n = normalise(raw)
        if n:
            found.add((n, m.start(), m.end()))
    if kind in ("act", "ordinance"):
        for m in BARE.finditer(text):
            if int(m.group(2)) != year:
                continue
            if any(int(f.group(1)) != year for f in FOREIGN_TITLE.finditer(text[max(0, m.start() - 80):m.start()])):
                continue
            n = normalise(m.group(1))
            if n:
                found.add((n, m.start(), m.end()))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=25, help="print this many recorded samples")
    ap.add_argument("--dump", help="write every recorded (instrument_id, number, quote) to this JSON file")
    ap.add_argument("--correct-stored", action="store_true",
                    help="instead: check numbers the SEGMENTER stored against the title region; where exactly one "
                         "printed number disagrees, record it with basis printed_number_corrects_stored (the only "
                         "basis tools/apply_instrument_metadata.py lets overwrite a stored number)")
    args = ap.parse_args()
    dumped = []
    from nizam.storage.db import connect
    counts = dict(considered=0, recorded=0, none_printed=0, ambiguous=0, unchanged=0)
    samples, ambiguous = [], []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        correcting = args.correct_stored
        basis = "printed_number_corrects_stored" if correcting else "printed_in_title_region"
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id, i.kind::text,
                              i.year, i.source_start_block_id, i.source_end_block_id, i.number
                         FROM v_release_instrument i
                        WHERE i.year IS NOT NULL
                          AND i.kind::text IN ('act', 'ordinance', 'order', 'regulation')
                          AND CASE WHEN %s
                              -- a stored number with no standing assertion, or one this mode asserted
                              THEN i.number IS NOT NULL AND NOT EXISTS (
                                   SELECT 1 FROM v_instrument_metadata_current c
                                    WHERE c.instrument_id = i.id AND c.field = 'number'
                                      AND c.basis IS DISTINCT FROM 'printed_number_corrects_stored')
                              -- no number yet, or a number THIS tool asserted (re-checked under the current rules)
                              ELSE (i.number IS NULL OR EXISTS (
                                   SELECT 1 FROM v_instrument_metadata_current c
                                    WHERE c.instrument_id = i.id AND c.field = 'number' AND c.method = %s
                                      AND c.basis = 'printed_in_title_region')) END""",
                    (correcting, METHOD))
        todo = cur.fetchall()
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'number'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        withdrawn = latest_withdrawn(cur, "number")
        for iid, obs, ordinal, doc, kind, year, start, end, stored in todo:
            counts["considered"] += 1
            if (obs, ordinal) in withdrawn:      # a person withdrew it; the tool does not re-assert it
                counts["withdrawn_kept"] = counts.get("withdrawn_kept", 0) + 1
                continue
            cur.execute("""SELECT t.id, t.page_no, coalesce(t.text, '') FROM text_block t
                            WHERE t.document_id = %s AND t.id >= %s AND t.id <= coalesce(%s, t.id)
                            ORDER BY t.id LIMIT %s""", (doc, start, end, BLOCKS))
            blocks = cur.fetchall()
            region, spans, stop = title_region(blocks)
            found = candidates(region, kind, year)
            numbers = {f[0] for f in found}
            if len(numbers) != 1:
                if not numbers:
                    counts["none_printed"] += 1
                else:
                    counts["ambiguous"] += 1; ambiguous.append((doc, sorted(numbers)))
                if (obs, ordinal) in standing:   # an earlier, looser run asserted one; the current rules do not
                    withdraw(cur, obs, ordinal, "number", METHOD, "not reproduced by the current title-region rules")
                    counts["withdrawn_on_recheck"] = counts.get("withdrawn_on_recheck", 0) + 1
                continue
            number = numbers.pop()
            if standing.get((obs, ordinal)) == number:
                counts["unchanged"] += 1; continue
            if correcting and stored == number:      # the segmenter's number is the printed one
                counts["agree"] = counts.get("agree", 0) + 1; continue
            first = min(found, key=lambda f: f[1])
            quote = " ".join(region[max(0, first[1] - 20):first[2] + 5].split())
            bid, page = next(((b, p) for s, e, b, p in spans if s <= first[1] < e), (blocks[0][0], blocks[0][1]))
            evidence = dict(reviewer_type="tool", kind=kind, year=year,
                            region_cut_at=(stop.group(0)[:40] if stop else None),
                            matches=len(found), **({"stored_by_segmenter": stored} if correcting else {}))
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'number', %s, 'asserted', %s, %s, %s, %s, %s, %s::jsonb, 'claude')""",
                        (obs, ordinal, number, basis, bid, page, quote, METHOD, json.dumps(evidence)))
            counts["recorded"] += 1
            dumped.append(dict(instrument_id=iid, document_id=doc, kind=kind, year=year, number=number, quote=quote,
                               stored=stored))
            if len(samples) < args.show:
                samples.append((doc, kind, year, number, quote))
        if not args.apply:
            conn.rollback()
    if args.dump:
        Path(args.dump).write_text(json.dumps(dumped, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps(counts, indent=1))
    for s in samples:
        print("recorded:", s)
    for a in ambiguous[:15]:
        print("ambiguous:", a)
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
