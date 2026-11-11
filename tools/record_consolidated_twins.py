"""Link a law's original Gazette text (as made) to its consolidated text (migration 0075, consolidated_twin).

Owner decision, 12 Nov 2026 (chat): "Link; serve consolidated (Recommended)" -- both texts stay released and
citable; operative_provision serves the consolidated one only.

PAIRS CONSIDERED. Released instruments whose source is the Ministry of Law DRS (drs.molaw.gov.pk: Gazette issues as
made) against released instruments from the Pakistan Code (pakistancode.gov.pk: consolidated, "Updated till ..."), of
the SAME jurisdiction, kind and year. Identity, strongest first:
  * same_title_number_year         -- title keys equal and numbers equal;
  * same_title_year                -- title keys equal, and the two numbers do not disagree (one may be missing);
  * same_number_year_title_overlap -- numbers equal and the title words overlap: at least 75% of the shorter title's
                                      words are in the longer one ('Transfer of Railways Order' / 'Railways Order').
Numbers that DISAGREE always refuse. An as-made text matching more than one consolidated text, or a consolidated text
matched by more than one as-made text, is refused (listed, never guessed). Every pair is printed for review; nothing
is written without --apply. A pair withdrawn by a person is never re-recorded.

    python tools/record_consolidated_twins.py            # list
    python tools/record_consolidated_twins.py --apply    # record
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METHOD = "nizam.consolidated_twin/1"
DECISION = ("owner chat 12 Nov 2026: 'Link; serve consolidated (Recommended)' -- keep both released and citable, "
            "link each reviewed pair, operative_provision serves only the consolidated text")
STOP = {"the", "of", "and", "act", "ordinance", "order", "regulation", "regulations", "rules", "in", "for", "to",
        "on", "a", "an", "an", "s", "s"}


# Pairs a person reviewed whose titles fail the word test (migration 0076): (as-made doc, consolidated doc) -> the
# evidence that the two titles name one law. Only same number/kind/year/jurisdiction pairs can be listed here.
REVIEWED_TITLES = {
    (5171, 4253): "ICT abbreviates Islamabad Capital Territory; both XLII of 2001",
    (9024, 2305): ("the consolidated text cites its own amending 'Land Control (Capital of the Federation) (Amdt.) Act "
                   "No. XXXIV of 1952' and records its title substituted by A.O., 1964; both XI of 1952"),
}


def title_words(t: str) -> set[str]:
    t = re.sub(r",?\s*\(?\d{4}\)?.*$", "", t or "")            # drop the year and anything after it
    return {w for w in re.findall(r"[a-z]+", t.lower()) if w not in STOP and len(w) > 1}


def overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cur.execute("""
            SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id, i.jurisdiction::text,
                   i.kind::text, i.year, i.number, coalesce(i.display_title, i.short_title),
                   coalesce(nullif(instrument_title_key(i.display_title), ''), instrument_title_key(i.short_title)),
                   i.source_url ~ 'drs\\.molaw' AS as_made,
                   (SELECT count(*) FROM provision p WHERE p.instrument_id = i.id AND p.is_active)
              FROM v_release_instrument i
             WHERE i.year IS NOT NULL AND (i.source_url ~ 'drs\\.molaw' OR i.source_url ~ 'pakistancode')""")
        rows = cur.fetchall()
        cur.execute("""SELECT DISTINCT ON (as_made_observation_id, as_made_expression_ordinal)
                              as_made_observation_id, as_made_expression_ordinal, assertion,
                              consolidated_observation_id, consolidated_expression_ordinal
                         FROM consolidated_twin
                        ORDER BY as_made_observation_id, as_made_expression_ordinal, recorded_at DESC, id DESC""")
        latest = {(r[0], r[1]): r for r in cur.fetchall()}
        made = [r for r in rows if r[10]]
        cons = [r for r in rows if not r[10]]
        by_key: dict[tuple, list] = {}
        for r in cons:
            by_key.setdefault((r[4], r[5], r[6]), []).append(r)
        pairs, refused, near = [], [], []
        for a in made:
            found = []
            for c in by_key.get((a[4], a[5], a[6]), []):
                if a[7] and c[7] and a[7] != c[7]:
                    continue                                  # numbers disagree: different laws
                same_title = bool(a[9]) and a[9] == c[9]
                same_number = bool(a[7]) and a[7] == c[7]
                ov = overlap(title_words(a[8]), title_words(c[8]))
                if same_title and same_number:
                    found.append((c, "same_title_number_year", ov))
                elif same_title:
                    found.append((c, "same_title_year", ov))
                elif same_number and ov >= 0.75:
                    found.append((c, "same_number_year_title_overlap", ov))
                elif same_number and (a[3], c[3]) in REVIEWED_TITLES:
                    found.append((c, "same_number_year_title_reviewed", ov))
                elif same_number:
                    near.append((a, c, ov))
            if len(found) == 1:
                pairs.append((a, *found[0]))
            elif len(found) > 1:
                refused.append((a, [f[0][3] for f in found]))
        twins = {}
        for a, c, *_ in pairs:
            twins.setdefault(c[0], []).append(a[3])
        counts = dict(pairs=0, recorded=0, unchanged=0, withdrawn_kept=0, refused_many=len(refused),
                      refused_shared_twin=0)
        for a, c, basis, ov in sorted(pairs, key=lambda p: p[0][3]):
            if len(twins[c[0]]) > 1:
                counts["refused_shared_twin"] += 1
                print(f"REFUSED {a[3]}: consolidated {c[3]} is matched by {twins[c[0]]}")
                continue
            counts["pairs"] += 1
            print(f"{a[3]:>5}:{a[2]} -> {c[3]:>5}:{c[2]}  {basis:31} ov={ov:.2f} no={a[7]}/{c[7]} "
                  f"prov={a[11]}/{c[11]} | {a[8][:55]} || {c[8][:55]}")
            prior = latest.get((a[1], a[2]))
            if prior and prior[2] == "withdrawn":
                counts["withdrawn_kept"] += 1; continue
            if prior and prior[2] == "recorded" and (prior[3], prior[4]) == (c[1], c[2]):
                counts["unchanged"] += 1; continue
            evidence = dict(reviewer_type="tool+claude review of the printed list", owner_decision=DECISION,
                            as_made_document=a[3], consolidated_document=c[3], title_word_overlap=round(ov, 3),
                            numbers=[a[7], c[7]], provisions=[a[11], c[11]],
                            as_made_source="drs.molaw.gov.pk (Gazette as made)",
                            consolidated_source="pakistancode.gov.pk (consolidated)",
                            **({"title_review": REVIEWED_TITLES[(a[3], c[3])]}
                               if basis == "same_number_year_title_reviewed" else {}))
            cur.execute("""INSERT INTO consolidated_twin
                             (as_made_observation_id, as_made_expression_ordinal, consolidated_observation_id,
                              consolidated_expression_ordinal, as_made_title, consolidated_title, basis, assertion,
                              method, evidence, recorded_by)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,'recorded',%s,%s::jsonb,'claude')""",
                        (a[1], a[2], c[1], c[2], a[8], c[8], basis, METHOD, json.dumps(evidence)))
            counts["recorded"] += 1
        for a, docs in refused:
            print(f"REFUSED {a[3]}: matches several consolidated texts {docs}")
        for a, c, ov in near:          # same number and year, titles too far apart: listed for a person, never linked
            print(f"NEAR (not linked) {a[3]}:{a[2]} -> {c[3]}:{c[2]} ov={ov:.2f} no={a[7]} | {a[8][:60]} || {c[8][:60]}")
        if not args.apply:
            conn.rollback()
    print(json.dumps(counts, indent=1))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
