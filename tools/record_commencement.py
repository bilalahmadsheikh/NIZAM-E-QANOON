"""Record when a released instrument came into force, where its OWN text says so for the whole (0070, commenced_on).

docs/03b ('the two edges that cannot be extracted from statute text'): commencement by notification lives in the
Gazette, not in the Act, so it is never inferred here -- such an instrument keeps commenced_on NULL and the operative
view reports its commencement coverage as 'not_tracked'. Only two self-executing forms are recorded:

  * 'This Act shall come into force at once' (also 'forthwith', 'immediately', and 'It shall ...' inside section 1):
    commenced_on = the instrument's established printed enactment date (field enacted_on). This is the convention
    migration 0066 already uses to date a repeal ('a printed date AND a commencement clause "shall come into force
    at once"'). Without an established enacted_on nothing is recorded.
  * 'This Act shall come into force on the 1st day of July, 1957' (or 'with effect from'): that printed date,
    accepted only within [year - 3, year + 2] of the instrument's year.

REFUSED -- left NULL: commencement by notification or appointment; any 'except', 'different dates', 'different
provisions', 'section'/'clause' in the commencement sentence (partial commencement); an enumerated list ('—(a) in the
Federal Capital ...'); 'deemed to have' (retrospective deeming); two commencement sentences that disagree; Urdu or
Sindhi text (the English patterns do not apply).

The sentence is looked for in the instrument's first 15 provisions, in order. The quote is the sentence; the
source block is that provision's first block.

THE GENERAL CLAUSES DEFAULT (16 Nov 2026, method /2). An Act that says nothing about its commencement comes into
operation on the day its own general clauses statute names -- statutes the corpus holds and that were read for this:
  * federal -- General Clauses Act, 1897 (doc 4392) s.5(1): 'Where any Central Act is not expressed to come into
    operation on any particular day, then it shall come into operation on the day on which it receives the assent'
    ((b): 'in the case of a Central Act made after [23 March 1956], of the President'). Basis
    general_clauses_s5_assent, only where the established enacted_on is a PRINTED ASSENT STATEMENT: on the twin pairs
    (0075) the Pakistan Code's bracketed date equals the Gazette's assent statement in 4 of 7 and falls 2-12 days
    later in 3, so a bracket is not the assent day. Acts of 1898 onward.
  * Punjab, Khyber Pakhtunkhwa, Balochistan -- the General Clauses Act, 1956 s.3 of each (docs 4211, 2299, 1235): it
    comes into operation 'on the day on which the assent thereto of the Governor is first published in the official
    Gazette, and in every such Act the date of the first publication thereof shall be printed either above or below
    the title of the Act'. Basis general_clauses_s3_first_publication, only where the established enacted_on is that
    printed date under the title (a bracket or a date line), never an assent statement. Acts of 1957 onward.
Not applied: Sindh and AJK (the corpus holds only amending general clauses texts there, not the section), Ordinances
(applying 'assent ... published' to a promulgation is interpretation), and any instrument whose text anywhere speaks
of coming into force or operation, commencing on, taking effect, effect from, or deeming -- or whose section 1 heading
promises a commencement its text does not print (a segmentation loss, not silence). Section 1 must be present.

    python tools/record_commencement.py            # report
    python tools/record_commencement.py --apply    # write
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

from record_enacted_dates import DAY_RX, MONTH_RX, to_date  # noqa: E402
from record_instrument_numbers import latest_withdrawn, withdraw  # noqa: E402

METHOD = "nizam.self_executing_commencement/1"
DEFAULT_METHOD = "nizam.general_clauses_default_commencement/1"
# any words that make the text not silent about its commencement
SPEAKS = re.compile(r"come\s+into\s+(?:force|operation)|came\s+into\s+(?:force|operation)|commence\s+(?:on|from|with)|"
                    r"shall\s+commence|takes?\s+effect|with\s+effect\s+from|w\.\s*e\.\s*f|deemed\s+to\s+have", re.I)
SHORT_TITLE = re.compile(r"may\s+be\s+(?:called|cited)", re.I)
GCA = {
    "fed": ("general_clauses_s5_assent", {"printed_assent_statement"}, 1898,
            "General Clauses Act, 1897, s.5(1): a Central Act not expressed to come into operation on a particular day "
            "comes into operation on the day on which it receives the assent"),
}
for _j in ("punjab", "kp", "balochistan"):
    GCA[_j] = ("general_clauses_s3_first_publication",
               {"printed_assent_date", "printed_date_under_title", "printed_date_line_under_title"}, 1957,
               "General Clauses Act, 1956, s.3: an Act not expressed to come into operation on a particular day comes "
               "into operation on the day the Governor's assent is first published in the official Gazette, the date "
               "of which is printed above or below the title")


# a text filed 'fed' that is a provincial Act (the corpus files West Pakistan and older provincial Acts under fed,
# docs/SCHEMA.md 'number series collide'): the Central Act rule does not govern it
PROVINCIAL_TITLE = re.compile(r"\b(?:West\s+Pakistan|W\.\s*P\.|Bombay|Sind|Sindh|Bengal|Punjab|Baluchistan|"
                              r"Balochistan|N\.?\s*W\.?\s*F\.?\s*P|Frontier|Khyber|East\s+Pakistan|Madras|Bihar)\b", re.I)


def general_clauses_default(jur: str, kind: str, year: int, enacted: str | None, enacted_basis: str | None,
                            provisions: list[tuple], title: str = "") -> tuple[str | None, str]:
    """(value or None, basis or refusal) under the general clauses default; provisions are (label, heading, text) of
    EVERY provision of the instrument."""
    refusal = silent_under_general_clauses(jur, kind, year, provisions, title)
    if refusal:
        return None, refusal
    basis, accepted, _from, _ = GCA[jur]
    if not enacted or enacted_basis not in accepted:
        return None, "default_needs_its_date_form"
    return enacted, basis


def silent_under_general_clauses(jur: str, kind: str, year: int, provisions: list[tuple],
                                 title: str = "") -> str | None:
    """None when the instrument is an Act its general clauses statute governs and its text is silent about its
    commencement; otherwise the refusal. The DAY is a separate question (general_clauses_default): that it came into
    operation on its assent or first publication -- both in the past for a law the corpus holds -- is settled here."""
    rule = GCA.get(jur)
    if kind != "act" or rule is None:
        return "default_not_applicable"
    if jur == "fed" and PROVINCIAL_TITLE.search(title or ""):
        return "provincial_act_filed_fed"
    if year < rule[2]:
        return "default_before_its_statute"
    text = "\n".join(" ".join(filter(None, p)) for p in provisions)
    if SPEAKS.search(text):
        return "text_speaks_of_commencement"
    first = [p for p in provisions if (p[0] or "").strip() == "1"]
    if not first or not SHORT_TITLE.search(" ".join(filter(None, first[0]))):
        return "section_1_not_found"
    if re.search(r"commencement", " ".join(filter(None, first[0])), re.I):
        return "section_1_promises_a_commencement"
    return None
SUBJECT = r"(?:This|These|The\s+said|the\s+said|The)?\s*(?:Act|Ordinance|Order|Regulations?|Rules|Regulation|It|it)"
CLAUSE = re.compile(rf"{SUBJECT}\s+(?:shall|will)\s+(?:be\s+deemed\s+to\s+have\s+)?(?:come|came)\s+into\s+"
                    rf"(?:force|operation)(?P<tail>[^.;]{{0,200}})", re.S)
AT_ONCE = re.compile(r"^\s*,?\s*(?:at\s+once|forthwith|immediately)\b", re.I)
ON_DATE = re.compile(rf"^\s*,?\s*(?:on\s+(?:and\s+from\s+)?|with\s+effect\s+from\s+|from\s+)(?:the\s+)?{DAY_RX}\s+"
                     rf"(?:day\s+of\s+)?{MONTH_RX},?\s*(\d{{4}})", re.I)
PARTIAL = re.compile(r"\bexcept\b|different\s+dates|different\s+provisions|\bsections?\b|\bclauses?\b|"
                     r"notification|appoint|deemed|such\s+date|[—–-]\s*\(a\)|:\s*\(a\)|\bareas?\b|\bprovince\b",
                     re.I)


def classify(text: str, enacted: str | None, year: int) -> tuple[str | None, str, str]:
    """(value or None, basis or refusal reason, quote)."""
    results = []
    for m in CLAUSE.finditer(text):
        sentence = m.group(0)
        tail = m.group("tail")
        if PARTIAL.search(sentence):
            results.append((None, "partial_or_notified", sentence))
            continue
        if AT_ONCE.search(tail):
            results.append(("AT_ONCE", "commences_at_once_on_printed_enactment_date", sentence))
            continue
        d = ON_DATE.search(tail)
        if d:
            dt = to_date(d.group(1), d.group(2), d.group(3))
            if dt and year - 3 <= dt.year <= year + 2 and dt <= date.today():
                results.append((dt.isoformat(), "commences_on_printed_date", sentence))
                continue
        results.append((None, "unrecognised_form", sentence))
    if not results:
        return None, "no_commencement_sentence", ""
    if any(r[0] is None for r in results):
        bad = next(r for r in results if r[0] is None)
        return None, bad[1], bad[2]
    kinds = {r[0] for r in results}
    if len(kinds) > 1:
        return None, "disagreeing_sentences", results[0][2]
    value, basis, sentence = results[0]
    if value == "AT_ONCE":
        if not enacted:
            return None, "at_once_without_enacted_date", sentence
        value = enacted
    return value, basis, sentence


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dump")
    args = ap.parse_args()
    # always on: a run without the default would read its standing dates as 'not reproduced' and withdraw them
    args.general_clauses = True
    from nizam.storage.db import connect
    counts: dict[str, int] = {}
    dumped = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute("""SELECT i.id, i.source_observation_id, i.expression_ordinal, i.document_id, i.year,
                              i.enacted_on::text, i.jurisdiction::text, i.kind::text,
                              coalesce(i.display_title, i.short_title),
                              (SELECT c.basis FROM v_instrument_metadata_current c
                                WHERE c.instrument_id = i.id AND c.field = 'enacted_on')
                         FROM v_release_instrument i
                        WHERE i.year IS NOT NULL AND coalesce(i.text_language, 'en') = 'en'""")
        todo = cur.fetchall()
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'commenced_on'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        withdrawn = latest_withdrawn(cur, "commenced_on")
        for iid, obs, ordinal, doc, year, enacted, jur, kind, title, enacted_basis in todo:
            if (obs, ordinal) in withdrawn:
                continue
            cur.execute("""SELECT p.first_block, p.first_page,
                                  concat_ws(' ', p.heading, p.marginal_note, v.text_en)
                             FROM provision p
                             LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                            WHERE p.instrument_id = %s AND p.is_active
                            ORDER BY p.ordinal, p.path LIMIT 15""", (iid,))
            provisions = cur.fetchall()
            text = "\n".join(r[2] or "" for r in provisions)
            value, basis, sentence = classify(text, enacted, year)
            method = METHOD
            if basis == "no_commencement_sentence" and args.general_clauses:
                cur.execute("""SELECT p.label, concat_ws(' ', p.heading, p.marginal_note), v.text_en
                                 FROM provision p
                                 LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                                WHERE p.instrument_id = %s AND p.is_active ORDER BY p.ordinal, p.path""", (iid,))
                every = cur.fetchall()
                dvalue, dbasis = general_clauses_default(jur, kind, year, enacted, enacted_basis, every, title)
                counts[f"default: {dbasis}"] = counts.get(f"default: {dbasis}", 0) + 1
                if dvalue:
                    value, basis, method = dvalue, dbasis, DEFAULT_METHOD
                    first = next(p for p in every if (p[0] or "").strip() == "1")
                    sentence = " ".join(" ".join(filter(None, first)).split())[:200]
            counts[basis] = counts.get(basis, 0) + 1
            if value is None:
                if (obs, ordinal) in standing:
                    withdraw(cur, obs, ordinal, "commenced_on", METHOD, f"not reproduced: {basis}")
                    counts["withdrawn_on_recheck"] = counts.get("withdrawn_on_recheck", 0) + 1
                continue
            if standing.get((obs, ordinal)) == value:
                counts["unchanged"] = counts.get("unchanged", 0) + 1
                continue
            quote = " ".join(sentence.split())[:300]
            block, page = None, None
            for fb, fp, t in provisions:
                if t and sentence[:40] in " ".join(t.split()) or (t and sentence[:40] in t):
                    block, page = fb, fp
                    break
            if block is None:
                block, page = provisions[0][0], provisions[0][1]
            if block is None:
                counts["no_source_block"] = counts.get("no_source_block", 0) + 1
                continue
            if method == DEFAULT_METHOD:
                evidence = dict(reviewer_type="tool", year=year, enacted_on=enacted, enacted_on_basis=enacted_basis,
                                jurisdiction=jur, rule=GCA[jur][3],
                                silence="no provision speaks of coming into force or operation, commencing on, "
                                        "taking effect, effect from or deeming; section 1 is present and its heading "
                                        "names no commencement",
                                quote_is="section 1 as printed (the Act's silence is the fact; the date is "
                                         "enacted_on's own quoted evidence)")
            else:
                evidence = dict(reviewer_type="tool", year=year, enacted_on=enacted,
                                rule=("at once -> the printed enactment date (convention of migration 0066)"
                                      if basis.startswith("commences_at_once") else "printed commencement date"))
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'commenced_on', %s, 'asserted', %s, %s, %s, %s, %s, %s::jsonb, 'claude')""",
                        (obs, ordinal, value, basis, block, page, quote, method, json.dumps(evidence)))
            counts["recorded"] = counts.get("recorded", 0) + 1
            dumped.append(dict(document_id=doc, year=year, enacted=enacted, value=value, basis=basis, quote=quote))
        if not args.apply:
            conn.rollback()
    if args.dump:
        Path(args.dump).write_text(json.dumps(dumped, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps(dict(sorted(counts.items())), indent=1))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
