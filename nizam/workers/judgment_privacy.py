"""Decide, for every released judgment, which names are withheld and what parties line is shown (D-131; D-122).

    uv run python -m nizam.workers.judgment_privacy [--apply]

`judgment_sensitivity` and `judgment_display` are derived: each run rebuilds them whole from v_release_judgment under
one builder (BUILDER), in one transaction. Run it after any judgment release and after the linker, whose resolved
citations it reads. A29 asserts the tables are exactly the release.

1. **Categories** (sensitive_category_rule): a judgment is in a category when it cites a law of that category (a
   resolved citation whose law title matches, and where the rule lists units, one of them: PPC ss. 354A, 376, 376A,
   377, 377B), or when its header prints the category's words ('Judge Family Court', 'through his father'), or, for a
   sexual offence only, when its body names the offence ('zina-bil-jabr', 'rape', 'prosecutrix'; 0129). Over-marking
   only withholds names, so the rules lean towards marking.
2. **The parties line** shown is the first 'A v. B' the header prints. In a judgment of any category, each side that is
   a person is withheld; the State, a government, an office or a company is not.
3. **Names withheld** (internal): the persons on the parties line, and for a sexual offence the persons the body
   names as victim, prosecutrix or abductee and every 'Mst.'/'Miss' name, and for a minor the persons named as minor
   or juvenile. Readers replace them in the text they return and refuse a search that names one.
"""
from __future__ import annotations

import argparse
import collections
import sys
import time

from nizam.storage import privacy as P
from nizam.storage.db import connect

BUILDER = "nizam.judgment_privacy/2"     # /2: the shown line is redacted of every withheld name (D-138)


def build(cur):
    counts: collections.Counter = collections.Counter()
    cur.execute("""
        SELECT DISTINCT ON (r.judgment_id, sr.category) r.judgment_id, r.decided_on, sr.category, sr.id, r.raw
          FROM judgment_statute_reference r
          JOIN v_release_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
          JOIN instrument i ON i.id = r.dst_instrument_id
          JOIN sensitive_category_rule sr ON sr.kind = 'law_cited'
                                         AND coalesce(nullif(i.display_title, ''), i.short_title) ~* sr.pattern
                                         AND (sr.labels IS NULL OR r.label = ANY (sr.labels))
         WHERE r.resolution = 'resolved'
         ORDER BY r.judgment_id, sr.category, r.char_start""")
    marks = {(jid, cat): (day, rid, raw[:300]) for jid, day, cat, rid, raw in cur.fetchall()}
    cur.execute("""
        SELECT DISTINCT ON (p.judgment_id, sr.category) p.judgment_id, p.decided_on, sr.category, sr.id,
               (regexp_match(p.text, sr.pattern, 'i'))[1]
          FROM v_release_judgment_paragraph p
          JOIN sensitive_category_rule sr ON sr.kind = 'header_words' AND p.text ~* sr.pattern
         WHERE p.kind = 'header'
         ORDER BY p.judgment_id, sr.category""")
    for jid, day, cat, rid, words in cur.fetchall():
        marks.setdefault((jid, cat), (day, rid, f"header: {words or cat}"))
    cur.execute("""
        SELECT DISTINCT ON (p.judgment_id, sr.category) p.judgment_id, p.decided_on, sr.category, sr.id,
               (regexp_match(p.text, sr.pattern, 'i'))[1]
          FROM v_release_judgment_paragraph p
          JOIN sensitive_category_rule sr ON sr.kind = 'body_words' AND p.text ~* sr.pattern
         WHERE p.kind = 'body'
         ORDER BY p.judgment_id, sr.category, p.ordinal""")
    for jid, day, cat, rid, words in cur.fetchall():
        marks.setdefault((jid, cat), (day, rid, f"body: {words or cat}"))
    sensitivity = [(jid, day, cat, rid, ev, BUILDER) for (jid, cat), (day, rid, ev) in marks.items()]
    cats_of: dict = collections.defaultdict(set)
    for jid, cat in marks:
        cats_of[jid].add(cat)
        counts[f"category:{cat}"] += 1

    cur.execute("""SELECT j.id, j.decided_on, j.parties_raw,
                          (SELECT string_agg(p.text, ' ' ORDER BY p.ordinal) FROM judgment_paragraph p
                            WHERE p.judgment_id = j.id AND p.decided_on = j.decided_on AND p.kind = 'header')
                     FROM v_release_judgment j""")
    rows = cur.fetchall()
    display = []
    for jid, day, raw, header in rows:
        pair = P.parties(header or "") or P.parties(raw or "")
        cats = cats_of.get(jid, set())
        names: list[str] = []
        if pair:
            left, right = pair
            if cats:
                shown = []
                for side in (left, right):
                    persons = P.names_of(side)
                    # a side is shown only when it names no person: one that mixes an office and a person ('X,
                    # Inspector, Police Station Y'), or carries header words beside a name, is withheld whole
                    if persons or not P.is_institution(side):
                        shown.append(P.WITHHELD)
                        names += persons
                    else:
                        shown.append(side)
                line = f"{shown[0]} v. {shown[1]}"
            else:
                line = f"{left} v. {right}"
        else:
            line = None
            counts["parties:not_read"] += 1
        if cats & {"sexual_offence", "minor"}:
            cur.execute("""SELECT text FROM judgment_paragraph WHERE judgment_id = %s AND decided_on = %s
                             AND kind IN ('body', 'footnote')""", (jid, day))
            body = [r[0] for r in cur.fetchall()]
            if "sexual_offence" in cats:
                names += P.victim_names(body)
            names += P.minor_names(body)          # a minor, and a child victim of a sexual offence
        names = list(dict.fromkeys(names))
        if cats and line:
            # no withheld name is ever in the line shown (audit A29), whatever the side-cutting above kept: a header
            # joining two cases can carry the second case's parties on a side read as 'The State' (D-138, SHC Crl.
            # B.A. 1698/2025). A one-word name is redacted here too: in a party line it is the person, not a word.
            line = P.redact(line, names)
        display.append((jid, day, line, bool(cats), names, BUILDER))
        counts["redacted" if cats else "shown"] += 1
        counts["names_withheld"] += len(names)
    return sensitivity, display, counts


def write(cur, sensitivity, display) -> None:
    cur.execute("DELETE FROM judgment_sensitivity")
    cur.execute("DELETE FROM judgment_display")
    with cur.copy("COPY judgment_sensitivity (judgment_id, decided_on, category, rule_id, evidence, builder) "
                  "FROM STDIN") as cp:
        for r in sensitivity:
            cp.write_row(r)
    with cur.copy("COPY judgment_display (judgment_id, decided_on, parties_display, redacted, names_withheld, builder) "
                  "FROM STDIN") as cp:
        for r in display:
            cp.write_row(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="withhold names in sensitive judgments (D-131)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        sensitivity, display, counts = build(cur)
        if a.apply:
            write(cur, sensitivity, display)
            conn.commit()
        else:
            conn.rollback()
    for k in sorted(counts):
        print(f"  {k:28} {counts[k]:>8,}")
    print(f"done in {time.time() - t0:.0f}s ({BUILDER})" + ("" if a.apply else " (dry run: nothing written; add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
