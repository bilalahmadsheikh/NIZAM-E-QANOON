"""Record whole-enactment repeals that the corpus's own released Acts print (migration 0066).

Reads every released provision mentioning 'repealed' and keeps a clause only when ALL of these hold:

  * it names a whole enactment: '<Title> <Act|Ordinance|Regulation(s)|Rules|Order>, <year> [(number)] is/are/shall
    stand [hereby] repealed';
  * the repealing instrument is an ACT (an Ordinance's repeal can lapse with it: not settled here);
  * no partial or qualifying words sit in the clause or just before it ('in its application to', 'so far as',
    'to the extent', 'except', 'save as', 'section/clause/rule/article/schedule N of');
  * title and year match EXACTLY ONE released canonical instrument of the SAME jurisdiction (titles folded for
    case, punctuation, footnote markers and the old spelling 'Sind'), and it is not the repealing instrument;
  * no released provision anywhere speaks of reviving that enactment (a revival makes the repeal's effect a legal
    question, so the clause is skipped).

Nothing is inferred beyond the clause: no repeal date (the repealing Act's commencement is not in the corpus), no
in-force claim for anything else. Dry run by default; --apply writes the rows not already standing.

    python tools/record_statutory_repeals.py            # report
    python tools/record_statutory_repeals.py --apply    # record
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METHOD = "nizam.statutory_repeal_text/1"
KIND = r"(?:Act|Ordinance|Regulations?|Rules|Order)"
REPEAL = re.compile(
    r"(?:^|[.;:]\s+|\(\d+\)\s*|\b(?:The|the)\s+)"
    r"(?P<title>(?:the\s+)?[A-Z][^.;:()\n]{2,160}?\b" + KIND + r"),?\s*(?P<year>1[89]\d\d|20\d\d)"
    r"(?P<num>\s*\((?:[^()]|\([^()]*\))*\))?"
    r"(?P<qual>[^.;]{0,120}?)\s+(?:is|are|shall\s+stand|stands)\s+(?:hereby\s+)?repealed", re.S)
QUALIFIER = re.compile(r"in\s+its\s+application|so\s+far\s+as|to\s+the\s+extent|insofar|in\s+so\s+far|"
                       r"except|save\s+as|section|clause|schedule|rule\s+\d|article", re.I)
AFTER_QUALIFIER = re.compile(r"in\s+(?:its|their)\s+application|so\s+far\s+as|to\s+the\s+extent|insofar|"
                             r"in\s+so\s+far|in\s+relation\s+to|as\s+applicable\s+to|except|save\s+as", re.I)
PART_BEFORE = re.compile(r"(section|clause|sub-section|rule|article|schedule)\s*[\dIVX()a-z]*\s*(of|in)\s*$", re.I)


MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")
PRINTED_DATE = re.compile(r"\[\s*(\d{1,2})(?:st|nd|rd|th)?\s*(?:day of\s+)?(" + "|".join(MONTHS)
                          + r"),?\s*(\d{4})\s*\]", re.I)


def printed_commencement(head: str, comes_into_force_at_once: bool):
    """The repealing Act's commencement date, or None: exactly one bracketed date under its title (the first 3,000
    characters of its own text) AND a 'shall come into force at once' clause. Returns (date, basis)."""
    import datetime
    dates = {(int(d), m.lower(), int(y)) for d, m, y in PRINTED_DATE.findall((head or "")[:3000])}
    if len(dates) != 1 or not comes_into_force_at_once:
        return None, None
    d, m, y = dates.pop()
    try:
        on = datetime.date(y, MONTHS.index(m) + 1, d)
    except ValueError:
        return None, None
    return on, (f"the repealing Act prints '[{d} {m.title()}, {y}]' under its title and that it 'shall come into "
                "force at once'")


def norm(title: str | None) -> str:
    """A title folded for matching: case, punctuation, footnote markers, a leading 'the', 'Sind' -> 'Sindh'."""
    t = re.sub(r"\d{1,2}\[", "", title or "").replace("’", "'").replace("‘", "'").lower()
    t = re.sub(r"\b\d{1,2}(?=[a-z])", "", t)
    t = re.sub(r"[\[\]]", "", t)
    t = re.sub(r"^the\s+", "", t.strip())
    t = re.sub(r"\bsind\b", "sindh", t)
    return re.sub(r"[^a-z0-9]+", " ", t.replace("'", "")).strip()


def title_key(short_title: str | None) -> str:
    """An instrument's stored title without its trailing year."""
    return norm(re.sub(r",?\s*(1[89]\d\d|20\d\d)\s*\.?\s*$", "", short_title or ""))


def repeal_clauses(text: str) -> list[dict]:
    """Every whole-enactment repeal clause in `text`, with `qualified` True when partial or qualifying words apply."""
    found = []
    for m in REPEAL.finditer(text or ""):
        before = text[max(0, m.start() - 60):m.start()]
        # the qualifier may also FOLLOW the verb: '... is hereby repealed in its application to the Islamabad
        # Capital Territory' / '... repealed so far as it relates to ...' (up to the end of the sentence)
        after = re.split(r"(?<=[.;])\s", text[m.end():m.end() + 160], maxsplit=1)[0]
        found.append({"title": m.group("title").strip(), "year": int(m.group("year")),
                      "clause": " ".join(m.group(0).split()),
                      "qualified": bool(QUALIFIER.search(m.group("qual") or "") or PART_BEFORE.search(before)
                                        or AFTER_QUALIFIER.search(after))})
    return found


def plan(instruments: list[tuple], provisions: list[tuple], revival_texts: list[str]) -> tuple[list[dict], dict]:
    """Decide the rows. instruments: (id, jurisdiction, kind, title, year, observation, ordinal);
    provisions: (instrument id, relative path, first block, text)."""
    by_key: dict = collections.defaultdict(list)
    meta = {}
    for iid, jur, kind, title, year, obs, ordinal in instruments:
        by_key[(jur, title_key(title), year)].append(iid)
        meta[iid] = (jur, kind, title, obs, ordinal)
    revived = " ".join(norm(t) for t in revival_texts)
    stats: collections.Counter = collections.Counter()
    rows, seen = [], set()
    for iid, rel_path, block, text in provisions:
        jur, kind, _title, obs, ordinal = meta[iid]
        for c in repeal_clauses(text):
            stats["clauses"] += 1
            if c["qualified"]:
                stats["skipped: partial or qualified"] += 1; continue
            if kind != "act":
                stats["skipped: repealing instrument is not an Act"] += 1; continue
            hits = by_key.get((jur, norm(c["title"]), c["year"]), [])
            if len(hits) != 1:
                stats["skipped: not held" if not hits else "skipped: ambiguous"] += 1; continue
            target = hits[0]
            if target == iid:
                stats["skipped: names itself"] += 1; continue
            if norm(c["title"]) and norm(c["title"]) in revived:
                stats["skipped: a revival names it"] += 1; continue
            t_jur, _k, t_title, t_obs, t_ord = meta[target]
            key = (t_obs, t_ord, obs, ordinal, rel_path)
            if key in seen:
                continue
            seen.add(key)
            stats["recordable"] += 1
            rows.append({"repealed_observation_id": t_obs, "repealed_expression_ordinal": t_ord,
                         "repealing_observation_id": obs, "repealing_expression_ordinal": ordinal,
                         "repealing_source_block_id": block, "repealing_relative_path": rel_path,
                         "clause_text": c["clause"], "matched_title": t_title, "matched_year": c["year"],
                         "repealed_instrument_id": target, "repealing_instrument_id": iid})
    stats["instruments"] = len({r["repealed_instrument_id"] for r in rows})
    return rows, dict(stats)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true", help="list every row, not the first fifteen")
    args = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('statutory_repeal')")
        if cur.fetchone()[0] is None:
            print("migration 0066 is not applied"); return 1
        cur.execute("""SELECT i.id::text, i.jurisdiction::text, i.kind::text, i.short_title, i.year,
                              i.source_observation_id, i.expression_ordinal
                         FROM v_release_instrument r JOIN instrument i ON i.id=r.id""")
        instruments = cur.fetchall()
        cur.execute("""SELECT i.id::text, subpath(p.path,3)::text, p.first_block, v.text_en
                         FROM v_release_instrument r JOIN instrument i ON i.id=r.id
                         JOIN provision p ON p.instrument_id=i.id AND p.is_active AND nlevel(p.path) > 3
                         JOIN provision_version v ON v.provision_id=p.id
                        WHERE v.text_en ~* 'repealed' AND p.first_block IS NOT NULL""")
        provisions = cur.fetchall()
        cur.execute("""SELECT v.text_en FROM v_release_instrument r JOIN instrument i ON i.id=r.id
                         JOIN provision p ON p.instrument_id=i.id AND p.is_active
                         JOIN provision_version v ON v.provision_id=p.id WHERE v.text_en ~* 'reviv'""")
        revival = [r[0] for r in cur.fetchall()]
        rows, stats = plan(instruments, provisions, revival)
        dated = {}
        for repealing in {r["repealing_instrument_id"] for r in rows}:
            cur.execute("""SELECT i.document_id, i.source_start_block_id FROM instrument i WHERE i.id=%s""",
                        (repealing,))
            doc, start = cur.fetchone()
            cur.execute("""SELECT string_agg(t.text, ' ' ORDER BY t.page_no, t.reading_order) FROM (
                             SELECT * FROM text_block t WHERE t.document_id=%s AND (%s::bigint IS NULL OR t.id >= %s)
                              ORDER BY t.page_no, t.reading_order LIMIT 40) t""", (doc, start, start))
            head = cur.fetchone()[0] or ""
            cur.execute("""SELECT coalesce(bool_or(v.text_en ~* 'come\\s+into\\s+force\\s+at\\s+once'), false)
                             FROM provision p JOIN provision_version v ON v.provision_id=p.id
                            WHERE p.instrument_id=%s AND p.is_active""", (repealing,))
            dated[repealing] = printed_commencement(head, cur.fetchone()[0])
        for r in rows:
            r["repealed_on"], r["repealed_on_basis"] = dated[r["repealing_instrument_id"]]
        stats["dated"] = sum(1 for r in rows if r["repealed_on"])
        print(json.dumps(stats, indent=1))
        written = 0
        if args.apply:
            for r in rows:
                cur.execute("""SELECT 1 FROM statutory_repeal WHERE repealed_observation_id=%s
                                 AND repealed_expression_ordinal=%s AND repealing_observation_id=%s
                                 AND repealing_expression_ordinal=%s AND repealing_relative_path=%s""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealing_observation_id"], r["repealing_expression_ordinal"],
                             r["repealing_relative_path"]))
                if cur.fetchone():
                    continue
                cur.execute("""INSERT INTO statutory_repeal
                    (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id,
                     repealing_expression_ordinal, repealing_source_block_id, repealing_relative_path, clause_text,
                     matched_title, matched_year, repealed_on, repealed_on_basis, assertion, method, evidence,
                     recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'repealed',%s,%s,'tools/record_statutory_repeals.py')""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealing_observation_id"], r["repealing_expression_ordinal"],
                             r["repealing_source_block_id"], r["repealing_relative_path"], r["clause_text"],
                             r["matched_title"], r["matched_year"], r["repealed_on"], r["repealed_on_basis"], METHOD,
                             json.dumps({"reviewer_type": "rule",
                                         "rule": "whole-enactment repeal in a released Act; exact unique same-"
                                                 "jurisdiction match; no qualifier; no revival",
                                         "repealing_instrument_id_at_record": r["repealing_instrument_id"],
                                         "repealed_instrument_id_at_record": r["repealed_instrument_id"]})))
                written += 1
        print(f"{'recorded' if args.apply else 'would record'} {written if args.apply else len(rows)} row(s)")
        jur = {i[0]: (i[1], i[3]) for i in instruments}
        for r in (rows if args.all else rows[:15]):
            print(f"  [{jur[r['repealed_instrument_id']][0]}] {r['repealed_on'] or 'undated'} "
                  f"{r['matched_title'][:60]!r} <- "
                  f"{jur[r['repealing_instrument_id']][1][:60]!r}: {r['clause_text'][:120]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
