"""Build the case records from the released judgments (D-125; docs/PRECEDENT-MODEL.md §3.3 as built).

    uv run python -m nizam.workers.judgment_cases [--apply]

`judicial_case`, `judgment_case`, `judgment_case_state` and `judgment_relation` are derived: every run rebuilds
them whole from v_release_judgment, under one named builder (BUILDER), in one transaction. Without --apply the run
reports and writes nothing. Run it after any judgment release, then the linker (nizam.workers.judgment_links), whose
case citations resolve to these cases. A28 asserts the tables are exactly the release.

1. **The case.** The case line as printed (judgment.case_no_printed) is read by nizam.corpus.judgment_case: the lead
   number, the numbers of the same type and year printed beside it, and the year that closes them. The case line is
   the record; where the header parser's number or year differs, the difference is kept in the state row.
2. **Reasons for a short order.** The opening three and closing four body paragraphs are read for the court's
   statement that the judgment gives the reasons for its short order, and that order's printed date. The short
   order is linked when the case holds exactly one other judgment decided that day that is marked as a short order
   by its own record (an opinion headed SHORT ORDER, or words saying its reasons will follow). A statement inside a
   quotation is the court quoting an earlier order, and is not read.
3. **Copies.** Two judgments of one case whose bodies overlap at COPY_MIN (word 5-grams), decided the same day when
   both are dated, are one decision. The copy kept is the longer body, then a dated one, then the first read.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import sys
import time

from nizam.corpus import judgment_case as JC
from nizam.storage.db import connect

BUILDER = "nizam.judgment_cases/2"     # /2: the other cases the header lists as decided together (D-128)
OPENING, CLOSING = 3, 4


def build(cur) -> tuple[dict, list, list, list, collections.Counter]:
    """(cases, memberships, states, relations, counts), read from the release. Writes nothing."""
    counts: collections.Counter = collections.Counter()
    cur.execute("SELECT code, printed_forms FROM case_type")
    forms = dict(cur.fetchall())
    cur.execute("""SELECT j.id, j.decided_on, j.decided_on_basis = 'undated', j.court_code, j.case_type_code,
                          j.case_number, j.case_year, j.case_no_printed, j.document_id
                     FROM v_release_judgment j ORDER BY j.decided_on, j.id""")
    judgments = cur.fetchall()
    cases: dict[str, tuple] = {}
    members: list[tuple] = []
    states: list[tuple] = []
    lead_of: dict = {}                                  # judgment id -> (lead key, day, undated, document id)
    cur.execute("""SELECT p.judgment_id, string_agg(p.text, ' ' ORDER BY p.ordinal) FROM v_release_judgment_paragraph p
                    WHERE p.kind = 'header' GROUP BY p.judgment_id""")
    headers = dict(cur.fetchall())
    court_forms: dict[str, dict[str, list[str]]] = collections.defaultdict(dict)
    for code, fs in forms.items():
        court_forms[code.split(":", 1)[0]][code] = fs
    for jid, day, undated, court, code, num, year, printed, doc in judgments:
        line = JC.read_case_line(printed, forms.get(code, []))
        if line is None or line.lead is None:
            states.append((jid, day, BUILDER, "no_number_read", (line.printed if line else printed)[:300], False))
            counts["state:no_number_read"] += 1
            continue
        if line.year is None:
            states.append((jid, day, BUILDER, "no_year_read", line.printed[:300], False))
            counts["state:no_year_read"] += 1
            continue
        differs = line.lead != JC.norm_number(num or "") or line.year != year
        states.append((jid, day, BUILDER, "grouped", line.printed[:300], differs))
        counts["state:grouped"] += 1
        counts["header_differs"] += differs
        lead = JC.case_key(court, code, line.lead, line.year)
        lead_of[jid] = (lead, day, undated, doc)
        seen: set[str] = set()
        listed = [(code, number, line.year, "lead") for number in [line.lead]]
        listed += [(code, n, line.year, "joined") for n in line.joined]
        # the other cases the header lists as decided together (D-128), each with its own type and year
        for hcode, hline in JC.header_cases(headers.get(jid, ""), court_forms.get(court, {})):
            listed += [(hcode, n, hline.year, "joined") for n in [hline.lead] + hline.joined]
        for c_code, number, c_year, role in listed:
            key = JC.case_key(court, c_code, number, c_year)
            if key in seen:
                continue
            seen.add(key)
            cases.setdefault(key, (key, court, c_code, JC.norm_number(number), c_year, BUILDER))
            members.append((jid, day, key, role, BUILDER))
            counts[f"membership:{role}"] += 1
    counts["cases"] = len(cases)

    by_case: dict[str, list] = collections.defaultdict(list)
    for jid, (key, day, undated, doc) in lead_of.items():
        by_case[key].append((jid, day, undated, doc))

    # bodies: the paragraphs read for a reasons statement, and the whole body where the case has another judgment
    cur.execute("""SELECT p.judgment_id, array_agg(p.text ORDER BY p.ordinal) FROM v_release_judgment_paragraph p
                    WHERE p.kind = 'body' GROUP BY p.judgment_id""")
    bodies = {jid: texts for jid, texts in cur.fetchall()}

    relations: list[tuple] = []
    # 3. copies first: a copy is never a short order's match
    copy_of: dict = {}
    for key, js in by_case.items():
        if len(js) < 2:
            continue
        sh = {j[0]: (JC.shingles(" ".join(bodies.get(j[0], []))), sum(map(len, bodies.get(j[0], [])))) for j in js}
        parent = {j[0]: j[0] for j in js}

        def root(x):
            while parent[x] != x:
                x = parent[x]
            return x
        scores = {}
        for a, b in itertools.combinations(js, 2):
            if not a[2] and not b[2] and a[1] != b[1]:
                continue                                    # two dated decisions on different days
            (sa, la), (sb, lb) = sh[a[0]], sh[b[0]]
            if min(la, lb) < JC.COPY_LEN_MIN * max(la, lb, 1):
                continue
            s = JC.copy_score(sa, sb)
            if s >= JC.COPY_MIN:
                parent[root(a[0])] = root(b[0])
                scores[(a[0], b[0])] = scores[(b[0], a[0])] = s
        clusters = collections.defaultdict(list)
        for j in js:
            clusters[root(j[0])].append(j)
        for group in clusters.values():
            if len(group) < 2:
                continue
            kept = max(group, key=lambda j: (sh[j[0]][1], not j[2], -j[3]))
            for j in group:
                if j is kept:
                    continue
                s = scores.get((j[0], kept[0]), max(scores.get((j[0], o[0]), 0) for o in group if o is not j))
                copy_of[j[0]] = kept[0]
                relations.append((j[0], j[1], "copy_of", key, kept[0], kept[1], None, None,
                                  f"body overlap {s:.3f} with the copy kept", round(s, 4), BUILDER))
                counts["relation:copy_of"] += 1

    # 2. reasons for a short order. The short order linked must be marked as one by its own record: an opinion
    #    headed SHORT ORDER, or words saying its reasons will follow ('For reasons to be recorded later').
    cur.execute("SELECT DISTINCT judgment_id FROM judgment_opinion WHERE kind = 'short_order'")
    short_heads = {r[0] for r in cur.fetchall()}
    for jid, (key, day, undated, _doc) in lead_of.items():
        texts = bodies.get(jid, [])
        part = texts if len(texts) <= OPENING + CLOSING else texts[:OPENING] + texts[-CLOSING:]
        st = JC.reasons_statement(part, None if undated else day)
        if st is None:
            continue
        if st.short_order_on and not undated and st.short_order_on > day:
            counts["reasons:short_order_after_own_date_skipped"] += 1
            continue
        other = None
        if st.short_order_on:
            hits = [j for j in by_case[key] if j[0] != jid and not j[2] and j[1] == st.short_order_on
                    and j[0] not in copy_of
                    and (j[0] in short_heads or JC.announces_reasons_later(bodies.get(j[0], [])))]
            if len(hits) == 1:
                other = hits[0]
            counts["reasons:short_order_held" if other else
                   ("reasons:short_order_ambiguous" if hits else "reasons:short_order_not_held")] += 1
        counts[f"reasons:{st.date_basis}"] += 1
        relations.append((jid, day, "reasons_for", key, other[0] if other else None, other[1] if other else None,
                          st.short_order_on, st.date_basis, st.printed, None, BUILDER))
        counts["relation:reasons_for"] += 1
    return cases, members, states, relations, counts


def write(cur, cases, members, states, relations) -> None:
    cur.execute("DELETE FROM judgment_relation")
    cur.execute("DELETE FROM judgment_case")
    cur.execute("DELETE FROM judgment_case_state")
    cur.execute("DELETE FROM judicial_case")
    with cur.copy("COPY judicial_case (case_key, court_code, case_type_code, case_number, case_year, builder) "
                  "FROM STDIN") as cp:
        for r in cases.values():
            cp.write_row(r)
    with cur.copy("COPY judgment_case (judgment_id, decided_on, case_key, role, builder) FROM STDIN") as cp:
        for r in members:
            cp.write_row(r)
    with cur.copy("COPY judgment_case_state (judgment_id, decided_on, builder, outcome, case_line_read, "
                  "header_differs) FROM STDIN") as cp:
        for r in states:
            cp.write_row(r)
    with cur.copy("COPY judgment_relation (judgment_id, decided_on, relation, case_key, other_judgment_id, "
                  "other_decided_on, short_order_on, date_basis, printed, score, builder) FROM STDIN") as cp:
        for r in relations:
            cp.write_row(r)


def main() -> int:
    ap = argparse.ArgumentParser(description="build case records from the released judgments (D-125)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        cases, members, states, relations, counts = build(cur)
        if a.apply:
            write(cur, cases, members, states, relations)
            conn.commit()
        else:
            conn.rollback()
    for k in sorted(counts):
        print(f"  {k:44} {counts[k]:>7,}")
    print(f"done in {time.time() - t0:.0f}s ({BUILDER})" + ("" if a.apply else " (dry run: nothing written; add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
