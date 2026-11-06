"""Link Ordinances to the later Act of the same name that superseded them (migration 0067; owner decision q6).

Owner decision decision-review-2026-10-21 q6 'mark-replaced': "Where the corpus holds a later Act with the same title,
the Ordinance is linked to it and shown as replaced; all others stay 'unknown'." This records exactly that link and
nothing more -- no lifecycle status, no date (see the migration).

A pair is recorded only when ALL hold:
  * the predecessor's title is an Ordinance; the successor is an instrument of kind 'act' whose title is an Act,
    not an Ordinance; both are active canonical instruments of the SAME jurisdiction;
  * their titles fold to the same key (case, punctuation, a leading 'The', footnote markers and the spelling 'Sind'
    folded; everything from the word 'Ordinance'/'Act' onward dropped);
  * the Act's year is the Ordinance's year or later, and EXACTLY ONE such Act exists (two or more: skipped);
  * an '(Amendment)' Ordinance pairs only with an Act of the same or the next year (amendment Ordinances of one
    session are enacted together; a later amendment Act of the same title is a different amendment).
basis = act_text_names_ordinance when the Act's own text prints '<title> Ordinance, <year>', else
same_title_successor_act.

    python tools/record_instrument_supersession.py            # report
    python tools/record_instrument_supersession.py --apply    # record rows not already standing
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METHOD = "nizam.ordinance_successor_title/1"
OWNER_DECISION = ".artifacts/decision-review/exports/decision-review-2026-10-21-recrawl.json q6 mark-replaced"
ORD = re.compile(r"\bordinance\b", re.I)
ACT = re.compile(r"\bact\b", re.I)


def fold(text: str | None) -> str:
    t = (text or "").lower()
    t = re.sub(r"\bsind\b", "sindh", t)
    return re.sub(r"[^a-z0-9]", "", t)


def title_key(title: str | None) -> str:
    """The title before the word Ordinance/Act, folded: 'The Cotton Ordinance, 1956' and 'Cotton Act, 1957' -> 'cotton'."""
    t = (title or "").lower()
    t = re.sub(r"^\W*(?:\d+\s*)?the\s+", "", t)
    t = re.sub(r"\b(?:ordinance|act)\b.*$", "", t, flags=re.S)
    return fold(t)


def is_amendment(title: str | None) -> bool:
    return bool(re.search(r"amendment", title or "", re.I))


def plan(instruments: list[dict]) -> tuple[list[tuple[dict, dict]], int]:
    """instruments: dicts {id, kind, jurisdiction, year, title}. Returns ([(ordinance, act)], ambiguous count)."""
    acts = collections.defaultdict(list)
    for i in instruments:
        if i["kind"] == "act" and ACT.search(i["title"] or "") and not ORD.search(i["title"] or "") and i["year"]:
            acts[(i["jurisdiction"], title_key(i["title"]))].append(i)
    pairs, ambiguous = [], 0
    for o in instruments:
        if not ORD.search(o["title"] or "") or not o["year"]:
            continue
        key = title_key(o["title"])
        if len(key) < 6:
            continue
        cands = [a for a in acts.get((o["jurisdiction"], key), []) if a["year"] >= o["year"] and a["id"] != o["id"]
                 and (not is_amendment(o["title"]) or a["year"] <= o["year"] + 1)]
        if len(cands) == 1:
            pairs.append((o, cands[0]))
        elif len(cands) > 1:
            ambiguous += 1
    return pairs, ambiguous


def names_ordinance(act_text_folded: str, ordinance: dict) -> bool:
    return (title_key(ordinance["title"]) + "ordinance" + str(ordinance["year"])) in act_text_folded


def main() -> int:
    from nizam.storage.db import connect
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT i.id::text, i.kind::text, i.jurisdiction::text, i.year, i.short_title,
                              i.source_observation_id, i.expression_ordinal, i.document_id
                         FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL""")
        cols = ("id", "kind", "jurisdiction", "year", "title", "obs", "ordinal", "doc")
        instruments = [dict(zip(cols, r)) for r in cur.fetchall()]
        pairs, ambiguous = plan(instruments)
        cur.execute("""SELECT superseded_observation_id, superseded_expression_ordinal,
                              superseding_observation_id, superseding_expression_ordinal
                         FROM v_instrument_supersession_current""")
        standing = {tuple(r) for r in cur.fetchall()}
        rows, by_basis = [], collections.Counter()
        for o, act in pairs:
            if (o["obs"], o["ordinal"], act["obs"], act["ordinal"]) in standing:
                continue
            cur.execute("""SELECT string_agg(coalesce(v.text_en,''), ' ') FROM provision p
                             LEFT JOIN provision_version v ON v.provision_id = p.id
                            WHERE p.instrument_id = %s AND p.is_active""", (act["id"],))
            basis = ("act_text_names_ordinance" if names_ordinance(fold(cur.fetchone()[0]), o)
                     else "same_title_successor_act")
            by_basis[basis] += 1
            rows.append((o, act, basis))
        print(f"ordinance -> act pairs: {len(pairs)} ({ambiguous} ambiguous skipped); new {len(rows)} {dict(by_basis)}")
        for o, act, basis in rows[:12]:
            print(f"   doc {o['doc']} {o['year']} {o['title'][:55]!r} -> doc {act['doc']} {act['year']} "
                  f"{act['title'][:50]!r} [{basis}]")
        if not a.apply:
            print("dry run -- pass --apply to record")
            return 0
        for o, act, basis in rows:
            cur.execute("""INSERT INTO instrument_supersession
                             (superseded_observation_id, superseded_expression_ordinal, superseding_observation_id,
                              superseding_expression_ordinal, superseded_title, superseded_year, superseding_title,
                              superseding_year, matched_key, basis, assertion, method, evidence, recorded_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'superseded',%s,%s,%s)""",
                        (o["obs"], o["ordinal"], act["obs"], act["ordinal"], o["title"], o["year"], act["title"],
                         act["year"], title_key(o["title"]), basis, METHOD,
                         json.dumps({"reviewer_type": "assistant", "owner_decision": OWNER_DECISION,
                                     "superseded_document_id": o["doc"], "superseding_document_id": act["doc"],
                                     "year_gap": act["year"] - o["year"]}), "claude.q6-supersession/1"))
        conn.commit()
        print(f"recorded {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
