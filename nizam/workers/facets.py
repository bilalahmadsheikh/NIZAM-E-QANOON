"""Facets (D-163; 0147): subject_matter for laws by title rule, and a judgment's subjects from the laws it cites.

    uv run python -m nizam.workers.facets [--apply]

1. The vocabulary version (nizam.storage.facets.VERSION) is recorded in taxonomy_version if it is not.
2. instrument_facet: every released law's short title (and display title) is read by facets.subjects_of; each subject
   it decides is a row, with the words that decided it. A law whose title decides none is left unassigned.
3. judgment_subject: for each released judgment, the subjects of the laws its resolved statute citations name,
   weighted by role (interpreted, challenged or quoted 3; cited 2; charge 1); a subject carrying at least a third of
   the weight is kept, with its share. A judgment citing no law with a subject has none.
Both tables are derived and rebuilt in one transaction. Audit A37.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time

from nizam.storage import facets as F
from nizam.storage.db import connect

BUILDER = "nizam.facets/1"
WEIGHT = {"interpreted": 3, "challenged": 3, "quoted": 3, "charge": 1}


def main() -> int:
    ap = argparse.ArgumentParser(description="facets: subject_matter (D-163)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO taxonomy_version (facet, version, vocabulary, released_on, rationale)
                       VALUES ('subject_matter', %s, %s::jsonb, current_date, %s)
                       ON CONFLICT (facet, version) DO NOTHING""",
                    (F.VERSION, json.dumps(F.VOCABULARY), F.RATIONALE))
        cur.execute("SELECT vocabulary FROM taxonomy_version WHERE facet = 'subject_matter' AND version = %s",
                    (F.VERSION,))
        if sorted(cur.fetchone()[0]) != F.VOCABULARY:
            sys.exit(f"vocabulary v{F.VERSION} differs from the one recorded: bump facets.VERSION")
        cur.execute("SELECT id, short_title, display_title FROM v_release_instrument")
        rows, per_inst, tally = [], {}, collections.Counter()
        for iid, short, display in cur.fetchall():
            subs = F.subjects_of(short) or F.subjects_of(display)
            per_inst[iid] = [v for v, _ in subs]
            tally["laws with a subject" if subs else "laws unassigned"] += 1
            for v, ev in subs:
                rows.append((iid, "subject_matter", v, F.VERSION, "title_rule", ev, BUILDER))
                tally[f"subject:{v}"] += 1
        cur.execute("DELETE FROM instrument_facet WHERE facet = 'subject_matter'")
        with cur.copy("COPY instrument_facet (instrument_id, facet, value, taxonomy_ver, method, evidence, builder) "
                      "FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)
        # a judgment's subjects, from the laws it cites
        cur.execute("""SELECT r.judgment_id, r.decided_on, r.dst_instrument_id, r.role
                         FROM judgment_statute_reference r
                         JOIN v_release_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                        WHERE r.resolution = 'resolved'""")
        weight = collections.defaultdict(collections.Counter)
        day_of = {}
        for jid, day, inst, role in cur.fetchall():
            subs = per_inst.get(inst)
            if not subs:
                continue
            day_of[jid] = day
            w = WEIGHT.get(role, 2) / len(subs)
            for v in subs:
                weight[jid][v] += w
        jrows = []
        for jid, c in weight.items():
            total = sum(c.values())
            for v, w in c.items():
                if w / total >= 1 / 3:
                    jrows.append((jid, day_of[jid], v, round(w / total, 3), F.VERSION, BUILDER))
                    tally[f"judgment subject:{v}"] += 1
        tally["judgments with a subject"] = len({r[0] for r in jrows})
        cur.execute("DELETE FROM judgment_subject")
        with cur.copy("COPY judgment_subject (judgment_id, decided_on, value, share, taxonomy_ver, builder) "
                      "FROM STDIN") as cp:
            for r in jrows:
                cp.write_row(r)
        for k, v in sorted(tally.items()):
            print(f"  {k:36} {v:7,}")
        if a.apply:
            conn.commit()
            print(f"applied in {time.time() - t0:.0f}s ({BUILDER})")
        else:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
