"""Record where a federal-text law runs, from its own extent clause (migration 0095, field 'territorial_extent').

territory_reach3 (0087) reads a federal law's TITLE. A law's own section 1 usually prints where it runs: "It extends
to the whole of Pakistan" (826 laws, 16 Nov 2026), "It extends to the Islamabad Capital Territory" (ICT laws that
do not say so in their title), "It extends to the Islamabad Capital Territory and the Provinces of Balochistan,
Khyber Pakhtunkhwa and Punjab" (the Hindu Marriage Act, 2017 -- not Sindh). Where the clause is read, it decides the
law's reach in v_instrument_currency.

A clause is recorded only when EVERY word of it is understood (parse_extent): the whole of Pakistan, all the
territories of Pakistan, West Pakistan (the four provinces; its excepted tribal/special areas lie inside them), each
province by its current or older name, ICT by any of its names (the Federal Capital, the capital of the Federation),
"all the provinces" WITH the capital. Anything else -- British India, a port, cantonments, named districts, "all the
provinces" without the capital, "such areas as ..." -- is not recorded and the title reading stands.

    python tools/record_territorial_extent.py            # report
    python tools/record_territorial_extent.py --apply    # record (and withdraw a standing value no longer read)
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METHOD = "nizam.territorial_extent_clause/1"
ORDER = ["punjab", "sindh", "kp", "balochistan", "ict"]
ALL5 = list(ORDER)
FOUR = ["punjab", "sindh", "kp", "balochistan"]

CLAUSE = re.compile(r"\b(?:it|this\s+(?:act|ordinance|order|regulation|code|law))\s+(?:shall\s+)?extends?\s+to\s+"
                    r"(?P<ext>[^.;:]{3,240})", re.I)

# phrase -> token; longest first. Each must cover its words exactly.
PHRASES = [
    (r"all\s+the\s+territories\s+of\s+pakistan", "ALL5"),
    (r"(?:the\s+)?whole\s+of\s+(?:the\s+)?pakistan", "ALL5"),
    (r"pakistan", "ALL5"),
    (r"all\s+the\s+provinces(?:\s+of\s+pakistan)?", "ALLPROV"),
    (r"(?:the\s+)?(?:whole\s+of\s+)?(?:the\s+)?(?:province\s+of\s+)?(?:the\s+)?west\s+pakistan", "FOUR"),
    (r"(?:the\s+)?(?:whole\s+of\s+)?(?:the\s+)?islamabad\s+capital\s+territory(?:\s*\(\s*ict\s*\))?", "ict"),
    # 'the capital of the Federation' / 'the Federal Capital' is KARACHI in laws of 1948-1960 (the Federal Capital
    # Area, merged into West Pakistan in 1961) and Islamabad only later: resolved by the law's year (CAPITAL)
    (r"(?:the\s+)?capital\s+of\s+the\s+federation", "CAPITAL"),
    (r"(?:the\s+)?federal\s+capital(?:\s*,?\s*including\s+the\s+cantonments\s+in\s+the\s+federal\s+capital)?",
     "CAPITAL"),
    (r"(?:the\s+)?(?:whole\s+of\s+)?(?:the\s+)?(?:province\s+of\s+(?:the\s+)?)?punjab", "punjab"),
    (r"(?:the\s+)?(?:whole\s+of\s+)?(?:the\s+)?(?:province\s+of\s+)?sindh?", "sindh"),
    (r"(?:the\s+)?(?:whole\s+of\s+)?(?:the\s+)?(?:province\s+of\s+)?(?:khyber\s+pakhtunkhwa|north\W*west\W*frontier"
     r"\s+province|n\.?\s*w\.?\s*f\.?\s*p\.?)", "kp"),
    (r"(?:the\s+)?(?:whole\s+of\s+)?(?:the\s+)?(?:province\s+of\s+)?(?:balochistan|baluchistan|beluchistan)",
     "balochistan"),
    (r"(?:the\s+)?karachi\s+division", "sindh"),
    (r"(?:the\s+)?rural\s+areas\s+of\s+the\s+(?:islamabad\s+)?capital\s+territory", "ict"),
]
# a sub-area excepted from a province stays inside that province's reach
EXCEPT_INSIDE = re.compile(r",?\s*except\s+(?:the\s+)?(?:tribal\s+areas|special\s+areas|federal\s+capital)"
                           r"(?:\s+and\s+(?:the\s+)?(?:tribal\s+areas|special\s+areas|federal\s+capital))*", re.I)
APPLIES_TAIL = re.compile(r",?\s+(?:and\s+)?(?:it\s+)?(?:shall\s+)?(?:also\s+)?appl(?:y|ies)\b.*$"
                          r"|,?\s+and\s+(?:it\s+)?shall\s+(?:come\s+into\s+force|have\s+effect)\b.*$", re.I | re.S)


def clean(ext: str) -> str:
    t = re.sub(r"\d{1,2}\s*\[", " ", ext)
    t = re.sub(r"[\[\]'’‘\"]|\*\s*\*\s*\*", " ", t)
    t = t.replace("­", "-").lower()
    t = re.sub(r"\bof\s*pakistan\b", "of pakistan", re.sub(r"ofpakistan", "of pakistan", t))
    t = re.sub(r"\bpakisian\b", "pakistan", re.sub(r"\brvhole\b", "whole", t))       # OCR slips seen in the corpus
    t = APPLIES_TAIL.sub("", t)
    return " ".join(t.split()).strip(" ,")


def capital_of(year: int | None) -> str | None:
    """Which territory 'the capital of the Federation' names in a law of `year`: Karachi (Sindh) to 1960, Islamabad
    (ICT) from 1963; 1961-1962 (Rawalpindi interim, ICT not yet carved out) and an unknown year are not read."""
    if year is None:
        return None
    return "sindh" if year <= 1960 else "ict" if year >= 1963 else None


def parse_extent(ext: str, year: int | None = None) -> list[str] | None:
    """The territories an extent phrase names, or None when any word of it is not understood."""
    t = clean(ext)
    four_except = bool(EXCEPT_INSIDE.search(t))
    t = EXCEPT_INSIDE.sub("", t)
    tokens = []
    rest = t
    while rest:
        prev = None
        while prev != rest:               # connectors may stack: 'and the Provinces of ...'
            prev = rest
            rest = re.sub(r"^(?:and|to|the\s+provinces\s+of|provinces\s+of)\s+", "", rest.strip(" ,"))
        if not rest:
            break
        for rx, tok in PHRASES:
            m = re.match(rx + r"(?=$|[\s,])", rest)
            if m:
                tokens.append(tok); rest = rest[m.end():]; break
        else:
            return None
    if not tokens:
        return None
    if four_except and "FOUR" not in tokens and not set(tokens) & set(FOUR):
        return None                       # an exception attached to something other than provinces
    out = set()
    for tok in tokens:
        if tok == "ALL5":
            out |= set(ALL5)
        elif tok == "FOUR":
            out |= set(FOUR)
        elif tok == "ALLPROV":
            out |= set(FOUR)
        elif tok == "CAPITAL":
            cap = capital_of(year)
            if cap is None:
                return None
            out.add(cap)
        else:
            out.add(tok)
    if "ALLPROV" in tokens and not ({"ict", "ALL5"} & set(tokens)) and not (
            "CAPITAL" in tokens and capital_of(year) == "ict"):
        return None                       # 'all the provinces' alone: whether ICT is meant is not printed
    return [x for x in ORDER if x in out]


def first_clause(provisions: list[tuple]) -> tuple | None:
    """provisions: (ordinal, path, first_block, first_page, text) in order. The first extent clause found."""
    for ordinal, path, block, page, text in provisions:
        # 'Sections 13 and 17 of this Act shall extend to the whole of the Punjab' (Public Gambling Act, 1867 s.2) is
        # the extent of some sections, not of the law: a subject preceded by 'of' is not the law's extent clause
        m = next((x for x in CLAUSE.finditer(text or "")
                  if not re.search(r"\bof\s*$", (text or "")[max(0, x.start() - 6):x.start()], re.I)), None)
        if m and block:
            sentence = " ".join(text[m.start():m.end()].split())
            return sentence, m.group("ext"), block, page, path
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=12, help="list this many unread clauses")
    a = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.year,
                              p.ordinal, p.path::text, p.first_block, p.first_page, v.text_en
                         FROM v_release_instrument i
                         JOIN provision p ON p.instrument_id = i.id AND p.is_active AND p.ordinal <= 8
                         JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                        WHERE i.jurisdiction = 'fed' AND v.text_en ~* 'extends?\\s+to\\s'
                        ORDER BY i.id, p.ordinal, p.path""")
        by = collections.defaultdict(list)
        ident = {}
        year_of = {}
        for iid, obs, ordn, year, *rest in cur.fetchall():
            by[iid].append(tuple(rest)); ident[iid] = (obs, ordn); year_of[iid] = year
        cur.execute("""SELECT instrument_id::text, value FROM v_instrument_metadata_current
                        WHERE field = 'territorial_extent'""")
        standing = dict(cur.fetchall())
        cur.execute("""SELECT i.id::text, coalesce(i.display_title, i.short_title), i.document_id,
                              territory_reach3(i.jurisdiction::text, coalesce(i.display_title, i.short_title),
                                               i.source_url)
                         FROM v_release_instrument i WHERE i.jurisdiction = 'fed'""")
        title_reach = {r[0]: r[1:] for r in cur.fetchall()}
        changes = []
        stats, unread, rows = collections.Counter(), collections.Counter(), []
        for iid, provs in by.items():
            hit = first_clause(provs)
            if not hit:
                stats["no extent sentence"] += 1
                if iid in standing:
                    rows.append(("withdraw", iid, None, None, None, None, None, ""))
                continue
            sentence, ext, block, page, path = hit
            parsed = parse_extent(ext, year_of[iid])
            if parsed is None:
                stats["not read (title reading stands)"] += 1
                unread[clean(ext)[:90]] += 1
                if iid in standing:
                    rows.append(("withdraw", iid, None, sentence, block, page, path, ext))
                continue
            value = ",".join(parsed)
            stats["read: " + ("whole of Pakistan" if parsed == ALL5 else value)] += 1
            title, doc, old = title_reach.get(iid, ("?", None, []))
            if list(old or []) != parsed:
                changes.append(f"   doc {doc}: {','.join(old or []) or '(none)'} -> {value}  | {title[:70]} | "
                               f"{clean(ext)[:70]}")
            if standing.get(iid) != value:
                rows.append(("assert", iid, value, sentence, block, page, path, ext))
        for iid in set(standing) - set(by):      # no 'extends to' text left at all
            cur.execute("SELECT source_observation_id, expression_ordinal FROM instrument WHERE id = %s", (iid,))
            ident[iid] = cur.fetchone()
            rows.append(("withdraw", iid, None, None, None, None, None, ""))
        print(json.dumps(dict(sorted(stats.items(), key=lambda kv: -kv[1])), indent=1))
        print(f"{len(rows)} row(s) to write ({sum(1 for r in rows if r[0] == 'withdraw')} withdrawals)")
        for phrase, n in unread.most_common(a.show):
            print(f"   unread x{n}: {phrase}")
        print(f"{len(changes)} law(s) whose reach the clause changes from the title reading:")
        for line in changes:
            print(line)
        if a.apply:
            for kind, iid, value, sentence, block, page, path, ext in rows:
                obs, ordn = ident[iid]
                cur.execute("""INSERT INTO instrument_metadata_assertion
                                 (source_observation_id, expression_ordinal, field, value, assertion, basis,
                                  source_block_id, source_page, quote, method, evidence, recorded_by)
                               VALUES (%s, %s, 'territorial_extent', %s, %s, 'printed_extent_clause', %s, %s, %s, %s,
                                       %s::jsonb, 'tools/record_territorial_extent.py')""",
                            (obs, ordn, value, "asserted" if kind == "assert" else "withdrawn",
                             block, page, (sentence or "")[:400] or None, METHOD,
                             json.dumps(dict(reviewer_type="rule", provision_path=path, extent_phrase=ext.strip(),
                                             rule="every word of the extent phrase mapped to a territory"))))
            print(f"recorded {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
