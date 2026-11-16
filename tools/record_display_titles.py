"""Record each released instrument's display title from the reviewed names table (migration 0070, field display_title).

Input: .artifacts/instrument-names-2026-11-11/instrument-names.csv (built 11 Nov 2026 from each instrument's own
first pages; README.md beside it explains every column). Only rows whose name was VERIFIED or NEAR-MATCHED in the
instrument's printed text and that need no review are recorded. The 636 rows marked needs_review=yes are not
recorded: they keep rendering short_title until a person has read their page.

Refused, whatever the CSV says: an instrument that is no longer active and canonical; a name carrying a catalogue
artefact ('NA-', 'Baln', 'official website', 'under review', '.docx', '.pdf'); a name with no letters.

Idempotent: an expression whose standing display title already equals the name is skipped.

--reviewed FILE (12 Nov 2026): a person's decision on needs_review rows (.artifacts/instrument-names-2026-11-11/
reviewed-2026-11-12.json, built by reviewed-2026-11-12.py beside it): 'accept' records the cleaned name (basis
reviewed_printed_name), 'fix' records the corrected name given in full (basis reviewed_corrected_name), 'reject'
records nothing. An Urdu-script name is recorded only for an instrument whose text_language is 'ur'.

Page-read decisions (pass 2, 12 Nov 2026: reviewed-2026-11-12-pass2.json, built by pass2/build_reviewed.py): rows the
names table could only give a catalogue title for. A decision carrying "page_read": true was made by reading the
instrument's own short-title clause or its page render, so the printed-text check is not required of it; its
"evidence" line is recorded. Such a row is matched to the active instrument of the same document and ordinal when the
table's instrument id was retired by a later repair replay (6548, 7585, 8607 on 12 Nov).

New instruments (14 Nov 2026, reviewed-2026-11-14-new-laws.json): a decision with "not_in_names_table": true names an
instrument landed after the table was built; it carries instrument_id, page_read, action and name, and is recorded
directly (same refusals).

SHORT-TITLE CLAUSE PASS (16 Nov 2026, --short-title-clause, method /2). The names table was built before AJK landed
(1,420 AJK laws had no display title) and left 169 others. Every law prints its own name in its short-title clause:
'This Act may be called the Azad Jammu and Kashmir ... Act, 2014'. For a released instrument with NO standing display
title, the name that clause prints is recorded (basis printed_short_title_clause) when it is a law's title: it ends
'<Act|Ordinance|Order|Rules|Regulations|Code|...>, <year>' (or the bracketed citation the AJK prints after it is
dropped), the year equals the instrument's year (or its printed number's year, within two), and it is 8-200
characters. Exactly one such clause in the first three provisions. 'the' is printed lower-case inside the sentence:
the recorded name starts with a capital. A name with catalogue artefacts is refused as above.

    python tools/record_display_titles.py            # report
    python tools/record_display_titles.py --apply    # write
    python tools/record_display_titles.py --short-title-clause [--apply]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CSV = ROOT / ".artifacts/instrument-names-2026-11-11/instrument-names.csv"
METHOD = "nizam.display_title_from_printed_text/1"
ACCEPT = {"verified_in_printed_text", "near_match_in_printed_text"}
ARTEFACT = re.compile(r"^\s*NA\s*-|\bBaln\b|official website|under review|\.docx|\.pdf", re.I)


CLAUSE_METHOD = "nizam.display_title_from_short_title_clause/1"
CALLED = re.compile(r"\bmay\s+be\s+(?:called|cited\s+as)\s*,?\s*(?P<name>.{6,240}?)\s*(?:[.;:](?:\s|$)|\n|$)", re.I | re.S)
TITLE_END = re.compile(r"\b(?:Act|Ordinance|Order|Orders|Rules|Regulations?|Code|Bye-?laws|Scheme|Statutes?|"
                       r"Notification|Resolution|Constitution)\s*,?\s*(?:\(\s*\d{4}\s*\)|(1[89]\d\d|20\d\d))$", re.I)
TRAILING_CITATION = re.compile(r"\s*\(\s*(?:act|ordinance|ord|regulation|order|p\.\s*o)\.?\s*(?:no\.?\s*)?"
                               r"[ivxlc0-9]+\s+of\s+\d{4}\s*\)\s*$", re.I)


def clause_name(text: str, year: int) -> tuple[str | None, str]:
    """(name or None, refusal) from the short-title clause in `text`."""
    names = set()
    for m in CALLED.finditer(text or ""):
        n = " ".join(m.group("name").split())
        n = re.sub(r"^\d{1,2}\[|\]\s*$", "", n)                   # footnote brackets around a substituted name
        n = re.sub(r"\s*\d{1,2}\[|\]", "", n)
        n = TRAILING_CITATION.sub("", n).strip(" ,'\"’‘“”")
        m2 = TITLE_END.search(n)
        if not m2:
            continue
        y = m2.group(1)
        if y and abs(int(y) - (year or int(y))) > 2:
            continue
        if not 8 <= len(n) <= 200 or ARTEFACT.search(n):
            continue
        names.add(n[0].upper() + n[1:])
    if len(names) != 1:
        return None, "no_clause" if not names else "two_clauses_disagree"
    return names.pop(), "ok"


# a catalogue title that is a file name: '.docx', '1102014', 'XIVJuvenile ...' (a numeral glued to the name -- case
# sensitive, or 'The' would match), a trailing '23.06' upload stamp, underscores
FILE_ARTEFACT = re.compile(r"(?i:\.docx?|\.pdf)|^\s*\d+\s*$|^[IVXLC]{1,6}(?=[A-Z][a-z])|\b\d{1,2}\.\d{2}\s*$|_")


def _words(t: str) -> set[str]:
    t = re.sub(r"&", " and ", (t or "").lower())
    return {w for w in re.findall(r"[a-z0-9]+", t) if w not in ("the", "of", "and")}


def choose(short: str, clause: str) -> tuple[str | None, str]:
    """The display title from the catalogue short title and the printed clause name: (name or None, basis).
    The clause CHECKS the catalogue title. They agree (>= 85% of words in common): the catalogue title, cleaned of its
    trailing printed citation, is kept for its spelling and capitals ('The he Penal Code', 'That Antiquities', OCR in
    the clause) -- unless it carries no year, when the clause's form is taken. The catalogue title is a file-name
    artefact: the clause's name. Otherwise they disagree and nothing is recorded."""
    cleaned = TRAILING_CITATION.sub("", short or "").strip(" ,")
    # a file-name title, or one carrying the catalogue's own abbreviations ('Baln ... Add Subject', 'NA-'): the
    # printed clause is the better witness, not a second opinion
    if FILE_ARTEFACT.search(short or "") or ARTEFACT.search(short or ""):
        return clause, "printed_short_title_clause"
    a, b = _words(cleaned), _words(clause)
    if not a or not b:
        return None, "empty"
    sim = len(a & b) / len(a | b)
    if sim >= 0.85:
        if TITLE_END.search(cleaned) and not ARTEFACT.search(cleaned):
            return cleaned[0].upper() + cleaned[1:], "verified_by_short_title_clause"
        return clause, "printed_short_title_clause"
    return None, "clause_disagrees_with_catalogue_title"


def short_title_clause_pass(apply: bool) -> int:
    from nizam.storage.db import connect
    counts: dict = {}
    shown = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.year, i.short_title,
                              i.document_id
                         FROM v_release_instrument i
                        WHERE NOT EXISTS (SELECT 1 FROM v_instrument_metadata_current c
                                           WHERE c.instrument_id = i.id AND c.field = 'display_title')""")
        todo = cur.fetchall()
        for iid, obs, ordinal, year, short, doc in todo:
            cur.execute("""SELECT p.first_block, p.first_page, concat_ws(' ', p.heading, v.text_en)
                             FROM provision p
                             LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                            WHERE p.instrument_id = %s AND p.is_active ORDER BY p.ordinal, p.path LIMIT 3""", (iid,))
            provs = cur.fetchall()
            printed, why = clause_name("\n".join(p[2] or "" for p in provs), year)
            name, basis = choose(short, printed) if printed else (None, why)
            counts[basis] = counts.get(basis, 0) + 1
            if not name:
                continue
            block = next((p for p in provs if p[2] and CALLED.search(p[2])), provs[0])
            evidence = {"reviewer_type": "tool", "short_title_at_recording": short, "clause_name": printed,
                        "rule": "the instrument's own short-title clause ('may be called ...') checks the catalogue "
                                "title; see record_display_titles.choose"}
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'display_title', %s, 'asserted', %s,
                                   %s, %s, %s, %s, %s::jsonb, 'claude')""",
                        (obs, ordinal, name, basis, block[0], block[1], " ".join((block[2] or "").split())[:300],
                         CLAUSE_METHOD, json.dumps(evidence, ensure_ascii=False)))
            counts["recorded"] = counts.get("recorded", 0) + 1
            if len(shown) < 25:
                shown.append(f"  {doc}: {short!r} -> {name!r}")
        if not apply:
            conn.rollback()
    print(json.dumps(counts, indent=1))
    print("\n".join(shown))
    print("applied" if apply else "dry run (rolled back); pass --apply to write")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reviewed", action="append", default=[],
                    help="JSON of reviewer decisions on needs_review rows (see above); may be given more than once")
    ap.add_argument("--short-title-clause", action="store_true",
                    help="record the name each untitled instrument's own short-title clause prints")
    args = ap.parse_args()
    if args.short_title_clause:
        return short_title_clause_pass(args.apply)
    decisions, source = {}, {}
    for f in args.reviewed:
        for k, v in json.loads(Path(f).read_text(encoding="utf-8")).items():
            assert k not in decisions, f"{k} decided in two files"
            decisions[k] = v; source[k] = Path(f).as_posix()
    with CSV.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    from nizam.storage.db import connect
    counts = dict(rows=len(rows), review=0, not_verified=0, artefact=0, inactive=0, unchanged=0, recorded=0)
    refused: list[str] = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id::text, source_observation_id, expression_ordinal FROM instrument
                        WHERE is_active AND duplicate_of IS NULL""")
        active = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        cur.execute("""SELECT source_observation_id, expression_ordinal, value FROM v_instrument_metadata_current
                        WHERE field = 'display_title'""")
        standing = {(r[0], r[1]): r[2] for r in cur.fetchall()}
        cur.execute("SELECT id::text, text_language FROM instrument WHERE is_active AND duplicate_of IS NULL")
        language = dict(cur.fetchall())
        cur.execute("""SELECT document_id || ':' || expression_ordinal, id::text FROM instrument
                        WHERE is_active AND duplicate_of IS NULL""")
        by_doc = dict(cur.fetchall())
        seen: set = set()
        for row in rows:
            basis, reviewer, decision = row["name_check"], "tool", None
            if row["needs_review"].strip().lower() != "no":
                decision = decisions.get(f"{row['document_id']}:{row['expression_ordinal']}")
                if decision is None or decision["action"] == "reject"                         or decision.get("instrument_id") != row["instrument_id"]:
                    counts["review"] += 1; continue
                page_read = bool(decision.get("page_read"))
                iid = row["instrument_id"]
                if page_read and iid not in active:
                    iid = by_doc.get(f"{row['document_id']}:{row['expression_ordinal']}", iid)
                urdu = bool(re.search(r"[؀-ۿ]", decision.get("name") or ""))
                if (decision.get("urdu_only_if_text_is_urdu") or (page_read and urdu)) and language.get(iid) != "ur":
                    counts["urdu_name_on_non_urdu_text"] = counts.get("urdu_name_on_non_urdu_text", 0) + 1
                    continue
                basis = "reviewed_printed_name" if decision["action"] == "accept" else "reviewed_corrected_name"
                reviewer = "claude"
            if row["name_check"] not in ACCEPT and not (decision and decision.get("page_read")):
                counts["not_verified"] += 1; continue
            name = (decision["name"] if decision else row["actual_name"]).strip()
            if not name or ARTEFACT.search(name) or not re.search(r"[A-Za-z؀-ۿ]", name):
                counts["artefact"] += 1; refused.append(f"{row['instrument_id']}: {name!r}"); continue
            iid = row["instrument_id"]
            if decision and decision.get("page_read") and iid not in active:
                iid = by_doc.get(f"{row['document_id']}:{row['expression_ordinal']}", iid)
            key = active.get(iid)
            if key is None:
                counts["inactive"] += 1; continue
            if key in seen:
                continue
            seen.add(key)
            if standing.get(key) == name:
                counts["unchanged"] += 1; continue
            evidence = {
                "reviewer_type": reviewer,
                **({"review_decision": decision["action"], "review_flags": row["review_flags"],
                    "reviewed_file": source[f"{row['document_id']}:{row['expression_ordinal']}"],
                    **({"page_read": True, "review_evidence": decision.get("evidence")} if decision.get("page_read") else {}),
                    **({"corrected_from": decision["was"]} if decision["action"] == "fix" else {})}
                   if decision else {}),
                "names_table": str(CSV.relative_to(ROOT)).replace("\\", "/"),
                "name_check": row["name_check"],
                "basis_detail": row["basis"],
                "catalogue_name_original": row["catalogue_name_original"],
                "short_title_at_recording": None,
            }
            cur.execute("SELECT short_title FROM instrument WHERE id = %s", (iid,))
            evidence["short_title_at_recording"] = cur.fetchone()[0]
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis, method,
                              evidence, recorded_by)
                           VALUES (%s, %s, 'display_title', %s, 'asserted', %s, %s, %s::jsonb, 'claude')""",
                        (key[0], key[1], name, basis, METHOD, json.dumps(evidence, ensure_ascii=False)))
            counts["recorded"] += 1
        # Instruments landed after the names table was built (recrawl of 14 Nov 2026) have no row in it. A page-read
        # decision marked "not_in_names_table" names one directly: it is recorded only if that instrument is active
        # and canonical, the decision is 'accept' or 'fix', and the name passes the same artefact refusal.
        listed = {f"{r['document_id']}:{r['expression_ordinal']}" for r in rows}
        for k, decision in sorted(decisions.items()):
            if not decision.get("not_in_names_table"):
                continue
            assert k not in listed, f"{k} is in the names table; decide it there"
            assert decision.get("page_read") and decision["action"] in ("accept", "fix"), k
            iid, name = decision["instrument_id"], decision["name"].strip()
            key = active.get(iid)
            if key is None or by_doc.get(k) != iid:
                counts["inactive"] += 1; continue
            if not name or ARTEFACT.search(name) or not re.search(r"[A-Za-z]", name):
                counts["artefact"] += 1; refused.append(f"{iid}: {name!r}"); continue
            if standing.get(key) == name:
                counts["unchanged"] += 1; continue
            cur.execute("SELECT short_title FROM instrument WHERE id = %s", (iid,))
            evidence = {"reviewer_type": "claude", "review_decision": decision["action"], "page_read": True,
                        "review_evidence": decision["evidence"], "reviewed_file": source[k],
                        "not_in_names_table": True, "short_title_at_recording": cur.fetchone()[0],
                        **({"corrected_from": decision["was"]} if decision["action"] == "fix" else {})}
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis, method,
                              evidence, recorded_by)
                           VALUES (%s, %s, 'display_title', %s, 'asserted', %s, %s, %s::jsonb, 'claude')""",
                        (key[0], key[1], name,
                         "reviewed_printed_name" if decision["action"] == "accept" else "reviewed_corrected_name",
                         METHOD, json.dumps(evidence, ensure_ascii=False)))
            counts["recorded"] += 1
            counts["not_in_names_table"] = counts.get("not_in_names_table", 0) + 1
        if not args.apply:
            conn.rollback()
    print(json.dumps(counts, indent=1))
    for r in refused[:20]:
        print("refused:", r)
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
