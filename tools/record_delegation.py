"""Record the law each released subordinate instrument says it was made under (migration 0089, delegation_record ->
legal_edge 'empowers'), and the earlier instrument its 'in supersession of' clause supersedes (instrument_supersession,
basis 'supersession_clause').

WHAT IS READ. The instrument's first 60 blocks (its notification and enacting formula):
  'In exercise of the powers conferred by section 25 of the Balochistan Civil Servants Act, 1974 (Act No. IX of 1974),
   the Government of Balochistan is pleased to make the following rules'
  'In exercise of the powers conferred by sub-section (3) of Section 4 of the PEMRA Ordinance 2002 ...'
  '... and in supersession of the West Pakistan Factories Rules, 1962, ...'

A DELEGATION IS RECORDED ONLY WHEN the law the formula names resolves, by title key and year, to exactly one released
instrument that is not itself subordinate -- in the instrument's own jurisdiction, else in the federation (provincial
rules made under the Code of Criminal Procedure) -- and is not the instrument itself. The first section the formula
names is the enabling section ('25'); every section it names is in the evidence. One delegation per enabling law.

A SUPERSESSION IS RECORDED ONLY WHEN the clause is not partial ('in partial supersession of' is refused), the earlier
instrument resolves to exactly one released subordinate instrument of the same jurisdiction by title key and year,
and it is no later than the superseding one. Owner decision: standing delegation, 16 Nov 2026 ('yes do it').

    python tools/record_delegation.py            # report
    python tools/record_delegation.py --apply    # write
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

from record_statutory_repeals import norm, title_key  # noqa: E402

METHOD = "nizam.delegation_from_enacting_formula/1"
SUP_METHOD = "nizam.supersession_clause/1"
SUBORDINATE = {"rules", "regulation", "order", "notification"}
WINDOW = 60
POWERS = re.compile(r"(?i)in\s+exercise\s+of\s+(?:the\s+)?powers?\s+conferred\s+(?:by|under|upon\s+it\s+by|on\s+it\s+by)\s+"
                    r"(?P<sec>[^.;]{0,140}?)\bof\s+the\s+"
                    r"(?P<title>[A-Z][^.;:()]{3,160}?\b(?:Act|Ordinance|Order|Regulations?|Code))\s*,?\s*"
                    r"(?P<year>1[89]\d\d|20\d\d)")
SECTION = re.compile(r"(?i)\b(?:sections?|articles?)\s+(\d{1,3}[A-Z]{0,2})\b")
SUPER = re.compile(r"(?i)in\s+(?P<partial>partial\s+)?supersession\s+of\s+(?:the\s+)?"
                   r"(?P<title>[A-Z][^.;:()]{3,160}?\b(?:Rules|Regulations?|Order|Orders|Notification|By-?laws))"
                   r"\s*,?\s*(?P<year>1[89]\d\d|20\d\d)")
OWNER = "standing delegation, owner 16 Nov 2026: 'yes do it' (link subordinate law to its enabling law)"


def sections(sec_text: str) -> list[str]:
    return [m.group(1).upper() for m in SECTION.finditer(sec_text or "")]


CONSOLIDATED = re.compile(r"pakistancode|punjabcode|sindhlaws|kpcode|balochistancode", re.I)


def one_law(hits: list[str], as_made: set[str], url_of: dict, ident: dict | None = None,
            size: dict | None = None) -> list[str]:
    """Several texts of ONE law are one parent:
      * the as-made text of a linked twin pair, or a Gazette copy beside the official consolidated text: the
        consolidated text (the one operative_provision serves);
      * otherwise, when every candidate has the same jurisdiction, kind and year (the title key already matched) --
        the Balochistan Code publishes the Balochistan Civil Servants Act, 1974 twice -- the fullest text (most
        provisions). Anything else stays ambiguous."""
    if len(hits) <= 1:
        return hits
    rest = [h for h in hits if h not in as_made]
    if len(rest) == 1:
        return rest
    cons = [h for h in rest if CONSOLIDATED.search(url_of.get(h) or "")]
    if len(cons) == 1:
        return cons
    pool = cons or rest
    if ident and size and len({ident.get(h) for h in pool}) == 1:
        return [max(pool, key=lambda h: (size.get(h, 0), h))]
    return hits


def resolve(index: dict, jur: str, title: str, year: int, exclude: str, allow_fed: bool = True,
            as_made: set[str] = frozenset(), url_of: dict | None = None, ident: dict | None = None,
            size: dict | None = None) -> list[str]:
    k = norm(re.sub(r",?\s*(1[89]\d\d|20\d\d)\s*$", "", title or ""))
    hits = sorted({i for i in index.get((jur, k, year), []) if i != exclude})
    if not hits and allow_fed and jur != "fed":
        hits = sorted({i for i in index.get(("fed", k, year), []) if i != exclude})
    return one_law(hits, as_made, url_of or {}, ident, size)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=20)
    args = ap.parse_args()
    from nizam.storage.db import connect
    counts: collections.Counter = collections.Counter()
    shown = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id,
                              i.jurisdiction::text, i.kind::text, i.year, i.short_title, i.display_title,
                              i.source_start_block_id, i.source_end_block_id
                         FROM v_release_instrument i""")
        rows = cur.fetchall()
        meta = {r[0]: r for r in rows}
        primary = collections.defaultdict(list)      # (jur, key, year) -> non-subordinate instrument ids
        subord = collections.defaultdict(list)       # (jur, key, year) -> subordinate instrument ids
        for iid, obs, o, doc, jur, kind, year, short, disp, s, e in rows:
            target = subord if kind in SUBORDINATE else primary
            for t in {title_key(short), title_key(disp) if disp else None}:
                if t and year and iid not in target[(jur, t, year)]:
                    target[(jur, t, year)].append(iid)
        cur.execute("SELECT as_made_instrument_id::text FROM v_consolidated_twin_current")
        as_made = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT id::text, source_url FROM v_release_instrument")
        url_of = dict(cur.fetchall())
        ident = {r[0]: (r[4], r[5], r[6]) for r in rows}           # jurisdiction, kind, year
        cur.execute("""SELECT p.instrument_id::text, count(*) FROM provision p
                         JOIN v_release_instrument i ON i.id = p.instrument_id
                        WHERE p.is_active AND i.kind::text NOT IN ('rules', 'regulation', 'order', 'notification')
                        GROUP BY 1""")
        size = dict(cur.fetchall())
        cur.execute("""SELECT delegated_observation_id, delegated_expression_ordinal, enabling_observation_id,
                              enabling_expression_ordinal FROM delegation_record""")
        have_d = {tuple(r) for r in cur.fetchall()}
        cur.execute("""SELECT superseded_observation_id, superseded_expression_ordinal, superseding_observation_id,
                              superseding_expression_ordinal FROM instrument_supersession""")
        have_s = {tuple(r) for r in cur.fetchall()}
        for iid, obs, ordinal, doc, jur, kind, year, short, disp, start, end in rows:
            if kind not in SUBORDINATE:
                continue
            counts["subordinate"] += 1
            cur.execute("""SELECT t.id, coalesce(t.text, '') FROM text_block t
                            WHERE t.document_id = %s AND t.id >= %s AND t.id <= coalesce(%s, t.id)
                            ORDER BY t.id LIMIT %s""", (doc, start, end, WINDOW))
            blocks = cur.fetchall()
            text, spans = "", []
            for bid, btxt in blocks:
                spans.append((len(text), bid)); text += " ".join(btxt.split()) + " "
            block_at = lambda pos: next((b for off, b in reversed(spans) if off <= pos), blocks[0][0] if blocks else None)
            # ---- delegation
            m = POWERS.search(text)
            if not m:
                counts["no_enacting_formula"] += 1
            else:
                hits = resolve(primary, jur, m.group("title"), int(m.group("year")), iid, as_made=as_made,
                               url_of=url_of, ident=ident, size=size)
                if len(hits) != 1:
                    counts["parent_not_held" if not hits else "parent_ambiguous"] += 1
                else:
                    p = meta[hits[0]]
                    secs = sections(m.group("sec"))
                    key = (obs, ordinal, p[1], p[2])
                    if key in have_d:
                        counts["delegation_unchanged"] += 1
                    else:
                        clause = " ".join(m.group(0).split())[:500]
                        cur.execute("""INSERT INTO delegation_record
                                         (delegated_observation_id, delegated_expression_ordinal, enabling_observation_id,
                                          enabling_expression_ordinal, enabling_section_label, clause_text,
                                          source_block_id, assertion, method, evidence, recorded_by)
                                       VALUES (%s,%s,%s,%s,%s,%s,%s,'recorded',%s,%s::jsonb,'claude')""",
                                    (obs, ordinal, p[1], p[2], secs[0] if secs else None, clause, block_at(m.start()),
                                     METHOD, json.dumps(dict(reviewer_type="tool", sections_named=secs,
                                                             texts_of_one_law=len(resolve(primary, jur, m.group("title"),
                                                                                          int(m.group("year")), iid))
                                                             if len(resolve(primary, jur, m.group("title"),
                                                                            int(m.group("year")), iid)) > 1 else None,
                                                             parent_title=p[8] or p[7], parent_year=p[6],
                                                             parent_jurisdiction=p[4], printed_title=m.group("title"),
                                                             printed_year=m.group("year")), ensure_ascii=False)))
                        have_d.add(key)
                        counts["delegation_recorded"] += 1
                        if len(shown) < args.show:
                            shown.append(f"  {doc} {jur} {kind}: s.{secs[0] if secs else '?'} of "
                                         f"{(p[8] or p[7])[:60]} ({p[4]} {p[6]})")
            # ---- supersession
            for sm in SUPER.finditer(text):
                counts["supersession_clauses"] += 1
                if sm.group("partial"):
                    counts["supersession_partial_refused"] += 1; continue
                y = int(sm.group("year"))
                hits = resolve(subord, jur, sm.group("title"), y, iid, allow_fed=False, as_made=as_made, url_of=url_of)
                if len(hits) != 1:
                    counts["superseded_not_held" if not hits else "superseded_ambiguous"] += 1; continue
                old = meta[hits[0]]
                if year is None or old[6] is None or old[6] > year:
                    counts["supersession_year_refused"] += 1; continue
                key = (old[1], old[2], obs, ordinal)
                if key in have_s:
                    counts["supersession_unchanged"] += 1; continue
                cur.execute("""INSERT INTO instrument_supersession
                                 (superseded_observation_id, superseded_expression_ordinal, superseding_observation_id,
                                  superseding_expression_ordinal, superseded_title, superseded_year, superseding_title,
                                  superseding_year, matched_key, basis, assertion, method, evidence, recorded_by)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'supersession_clause','superseded',%s,%s::jsonb,
                                       'claude')""",
                            (old[1], old[2], obs, ordinal, old[8] or old[7], old[6], disp or short, year,
                             norm(sm.group("title")), SUP_METHOD,
                             json.dumps(dict(reviewer_type="tool", owner_decision=OWNER,
                                             clause=" ".join(sm.group(0).split())[:400],
                                             source_block_id=block_at(sm.start())), ensure_ascii=False)))
                have_s.add(key)
                counts["supersession_recorded"] += 1
                if len(shown) < args.show * 2:
                    shown.append(f"  SUPERSEDES: {doc} {(disp or short)[:50]} -> {(old[8] or old[7])[:50]} ({old[6]})")
        if not args.apply:
            conn.rollback()
    print(json.dumps(dict(sorted(counts.items())), indent=1))
    print("\n".join(shown))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
