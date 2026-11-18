"""Record repeals that remove a federal-text law from ONE territory (migration 0095, table territorial_repeal).

statutory_repeal (0066, tools/record_statutory_repeals.py) records whole repeals within one jurisdiction. A province
cannot repeal a federal law everywhere: when a released provincial ACT prints '<Title>, <year> ... is hereby
repealed', and that title and year name a law the corpus holds as a FEDERAL text, the law stops running in that
province only (the Punjab Child Marriage Restraint Act, 2026 s.15 and the Child Marriage Restraint Act, 1929; the
Punjab Defamation Act, 2024 s.28 and the Defamation Ordinance, 2002). Likewise a clause that itself confines the
repeal to a territory: 'is hereby repealed to the extent of Islamabad Capital Territory' (ICT Child Marriage Restraint
Act, 2025 s.13(1)), 'in its application to the extent of Balochistan Province' (Balochistan Act, 2025 s.14(1)).

A row is recorded only when ALL of these hold:
  * the repealing instrument is a released Act (an Ordinance's repeal can lapse with it, as in 0066);
  * the clause names a whole enactment (record_statutory_repeals.REPEAL; not 'section N of', not a run-on title);
  * any qualifier is territorial and names the repealer's own territory -- its province, or ICT for a federal law
    that confines the repeal to ICT; any other qualifier ('except', 'so far as it relates to', a section) skips it;
  * a federal repealer without an ICT qualifier is NOT used (Parliament repeals everywhere: that is 0066's record);
  * title and year match exactly one released FEDERAL-text law (or the twin texts of one law), not the repealer;
  * that law reaches the territory, and no released provision speaks of reviving it.

    python tools/record_territorial_repeals.py            # report every row it would write
    python tools/record_territorial_repeals.py --apply    # record
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_statutory_repeals import (PART_BEFORE, REPEAL, norm, printed_commencement,  # noqa: E402
                                      resolve_hits, title_key)

METHOD = "nizam.territorial_repeal_text/1"
PROVINCES = {"punjab", "sindh", "kp", "balochistan"}
PLACE = {
    "punjab": r"(?:the\s+)?(?:province\s+of\s+(?:the\s+)?)?punjab(?:\s+province)?",
    "sindh": r"(?:the\s+)?(?:province\s+of\s+)?sindh?(?:\s+province)?",
    "kp": r"(?:the\s+)?(?:province\s+of\s+)?(?:khyber\s+pakhtunkhwa|north\W*west\W*frontier\s+province|n\.?w\.?f\.?p\.?)"
          r"(?:\s+province)?",
    "balochistan": r"(?:the\s+)?(?:province\s+of\s+)?ba[lu]ochistan(?:\s+province)?",
    "ict": r"(?:the\s+)?islamabad\s+capital\s+territory",
}
TERRITORIAL = re.compile(
    r"(?:in\s+(?:its|their)\s+application\s+(?:to\s+)?(?:the\s+extent\s+of\s+)?|to\s+the\s+extent\s+of\s+|"
    r"in\s+so\s+far\s+as\s+it\s+(?:applies|extends)\s+to\s+|so\s+far\s+as\s+it\s+(?:applies|extends)\s+to\s+|"
    # 'as applicable to the extent of the Province of Balochistan' (Balochistan Antiquities Act, 2014 s.41(1); D-078)
    r"in\s+relation\s+to\s+|as\s+applicable\s+to\s+(?:the\s+extent\s+of\s+)?)(?P<place>[^.;,:]{3,80})", re.I)
OTHER_QUALIFIER = re.compile(r"\bexcept\b|\bsave\s+as\b|\bsection\b|\bclause\b|\bschedule\b|\brule\s+\d|\barticle\b|"
                             r"so\s+far\s+as\s+it\s+relates", re.I)


def place_of(text: str) -> str | None:
    t = " ".join(text.lower().split()).strip(" ,")
    t = re.sub(r"\s+(?:and|with)\b.*$", "", t)
    for terr, rx in PLACE.items():
        if re.fullmatch(rx, t):
            return terr
    return None


def clause_territory(qual: str, after: str, repealer_territory: str | None) -> tuple[str | None, str]:
    """(territory, why) for one repeal clause. qual: words between the year and 'is repealed'; after: the rest of the
    sentence. repealer_territory: the repealer's province, 'ict' for a federal law, None otherwise."""
    words = f"{qual} || {after}"
    hits = list(TERRITORIAL.finditer(words))
    stripped = TERRITORIAL.sub(" ", words)
    if OTHER_QUALIFIER.search(stripped):
        return None, "skipped: a non-territorial qualifier"
    if not hits:
        if repealer_territory in PROVINCES:
            return repealer_territory, "a provincial Act repeals for its own province"
        return None, "skipped: a federal repeal not confined to ICT (whole repeal: 0066's record)"
    places = {place_of(h.group("place")) for h in hits}
    if len(places) != 1 or None in places:
        return None, "skipped: the qualifier names a place not read"
    place = places.pop()
    if place != repealer_territory:
        return None, "skipped: the qualifier names another territory than the repealer's"
    return place, "the clause confines the repeal to the repealer's territory"


def plan(instruments, provisions, revival_texts, twins, reach) -> tuple[list[dict], dict]:
    """instruments: (id, jurisdiction, kind, title, year, observation, ordinal, display title);
    provisions: (instrument id, relative path, first block, text); reach: instrument id -> territories."""
    fed_by_key = collections.defaultdict(list)
    meta = {}
    for iid, jur, kind, title, year, obs, ordinal, display in instruments:
        meta[iid] = (jur, kind, title, obs, ordinal)
        if jur == "fed":
            for t in {title_key(title), title_key(display) if display else ""}:
                if t and iid not in fed_by_key[(t, year)]:
                    fed_by_key[(t, year)].append(iid)
    revived = " ".join(norm(t) for t in revival_texts)
    stats, rows, seen = collections.Counter(), [], set()
    for iid, rel_path, block, text in provisions:
        jur, kind, _t, obs, ordinal = meta[iid]
        own = jur if jur in PROVINCES else ("ict" if jur == "fed" else None)
        if own is None:
            continue
        for m in REPEAL.finditer(text or ""):
            stats["clauses"] += 1
            before = text[max(0, m.start() - 60):m.start()]
            num = (m.group("num") or "").strip()
            if (num and not re.search(r"\d|\b[IVXLC]+\b", num)) or re.search(r"\bof\s*$", before, re.I) \
                    or PART_BEFORE.search(before):
                stats["skipped: not a whole enactment"] += 1; continue
            if kind != "act":
                stats["skipped: repealer is not an Act"] += 1; continue
            after = re.split(r"(?<=[.;])\s", text[m.end():m.end() + 160], maxsplit=1)[0]
            terr, why = clause_territory(m.group("qual") or "", after, own)
            if terr is None:
                stats[why] += 1; continue
            title, year = m.group("title").strip(), int(m.group("year"))
            hits = [h for h in fed_by_key.get((norm(title), year), []) if h != iid]
            targets = resolve_hits(hits, title, meta, twins)
            if not targets:
                stats["skipped: no federal-text law of that title and year" if not hits
                      else "skipped: ambiguous"] += 1; continue
            if norm(title) in revived:
                stats["skipped: a revival names it"] += 1; continue
            for target in targets:
                if terr not in (reach.get(target) or []):
                    stats["skipped: the law does not reach that territory"] += 1; continue
                t_jur, _k, t_title, t_obs, t_ord = meta[target]
                key = (t_obs, t_ord, terr, obs, ordinal, rel_path)
                if key in seen:
                    continue
                seen.add(key)
                stats["recordable"] += 1
                rows.append(dict(repealed_observation_id=t_obs, repealed_expression_ordinal=t_ord,
                                 repealing_observation_id=obs, repealing_expression_ordinal=ordinal,
                                 repealing_source_block_id=block, repealing_relative_path=rel_path, territory=terr,
                                 clause_text=" ".join(m.group(0).split() + after.split())[:600],
                                 matched_title=t_title, matched_year=year, why=why,
                                 repealed_instrument_id=target, repealing_instrument_id=iid))
    return rows, dict(stats)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--clauses", action="store_true", help="print each row's clause for review")
    a = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.jurisdiction::text, i.kind::text, i.short_title, i.year,
                              i.source_observation_id, i.expression_ordinal, i.display_title
                         FROM v_release_instrument r JOIN instrument i ON i.id = r.id""")
        instruments = cur.fetchall()
        cur.execute("""SELECT i.id::text, subpath(p.path, 3)::text, p.first_block, v.text_en
                         FROM v_release_instrument r JOIN instrument i ON i.id = r.id
                         JOIN provision p ON p.instrument_id = i.id AND p.is_active AND nlevel(p.path) > 3
                         JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                        WHERE v.text_en ~* 'repealed' AND p.first_block IS NOT NULL
                          AND i.jurisdiction::text IN ('punjab', 'sindh', 'kp', 'balochistan', 'fed')""")
        provisions = cur.fetchall()
        cur.execute("""SELECT v.text_en FROM v_release_instrument r JOIN instrument i ON i.id = r.id
                         JOIN provision p ON p.instrument_id = i.id AND p.is_active
                         JOIN provision_version v ON v.provision_id = p.id WHERE v.text_en ~* 'reviv'""")
        revival = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT as_made_instrument_id::text, consolidated_instrument_id::text FROM v_consolidated_twin_current")
        twins = frozenset(frozenset(r) for r in cur.fetchall())
        cur.execute("SELECT instrument_id::text, territory_reach FROM v_instrument_currency")
        reach = dict(cur.fetchall())
        rows, stats = plan(instruments, provisions, revival, twins, reach)
        dated = {}
        for repealing in {r["repealing_instrument_id"] for r in rows}:
            cur.execute("SELECT document_id, source_start_block_id FROM instrument WHERE id = %s", (repealing,))
            doc, start = cur.fetchone()
            cur.execute("""SELECT string_agg(t.text, ' ' ORDER BY t.page_no, t.reading_order) FROM (
                             SELECT * FROM text_block t WHERE t.document_id = %s AND (%s::bigint IS NULL OR t.id >= %s)
                              ORDER BY t.page_no, t.reading_order LIMIT 40) t""", (doc, start, start))
            head = cur.fetchone()[0] or ""
            cur.execute("""SELECT coalesce(bool_or(v.text_en ~* 'come\\s+into\\s+force\\s+at\\s+once'), false)
                             FROM provision p JOIN provision_version v ON v.provision_id = p.id
                            WHERE p.instrument_id = %s AND p.is_active""", (repealing,))
            dated[repealing] = printed_commencement(head, cur.fetchone()[0])
        for r in rows:
            r["repealed_on"], r["repealed_on_basis"] = dated[r["repealing_instrument_id"]]
        print(json.dumps(dict(sorted(stats.items(), key=lambda kv: -kv[1])), indent=1))
        titles = {i[0]: i[7] or i[3] for i in instruments}
        for r in rows:
            print(f"  [{r['territory']:>11}] {r['repealed_on'] or 'from repealer'}  "
                  f"{titles[r['repealed_instrument_id']][:55]!r} <- {titles[r['repealing_instrument_id']][:50]!r}")
            if a.clauses:
                print(f"        {r['clause_text'][:260]}")
        written = 0
        if a.apply:
            for r in rows:
                cur.execute("""SELECT 1 FROM territorial_repeal WHERE repealed_observation_id = %s
                                 AND repealed_expression_ordinal = %s AND territory = %s
                                 AND repealing_observation_id = %s AND repealing_expression_ordinal = %s
                                 AND repealing_relative_path = %s""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"], r["territory"],
                             r["repealing_observation_id"], r["repealing_expression_ordinal"],
                             r["repealing_relative_path"]))
                if cur.fetchone():
                    continue
                cur.execute("""INSERT INTO territorial_repeal
                    (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id,
                     repealing_expression_ordinal, repealing_source_block_id, repealing_relative_path, territory,
                     clause_text, matched_title, matched_year, repealed_on, repealed_on_basis, assertion, method,
                     evidence, recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'repealed',%s,%s,'tools/record_territorial_repeals.py')""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealing_observation_id"], r["repealing_expression_ordinal"],
                             r["repealing_source_block_id"], r["repealing_relative_path"], r["territory"],
                             r["clause_text"], r["matched_title"], r["matched_year"], r["repealed_on"],
                             r["repealed_on_basis"], METHOD,
                             json.dumps({"reviewer_type": "rule", "why": r["why"],
                                         "repealing_instrument_id_at_record": r["repealing_instrument_id"],
                                         "repealed_instrument_id_at_record": r["repealed_instrument_id"]})))
                written += 1
        print(f"{'recorded' if a.apply else 'would record'} {written if a.apply else len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
