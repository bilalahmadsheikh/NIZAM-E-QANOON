"""Link appeal chains to the judgments below (docs/PRECEDENT-MODEL.md §3.5, D-159).

    uv run python -m nizam.workers.lineage_links [--apply]

Each released judgment's lineage (judgment_lineage, read by the parser from its own words: "against the judgment
dated 17.01.2017 passed by the Lahore High Court in Cr.A. No.652-J of 2016") is resolved to the court below's case
and, where the corpus holds exactly one decision of that case dated as printed, to that judgment.
judgment_lineage_link (0143) is derived: rebuilt here from the release, in one transaction, by one builder.

The court below is the one the parser recorded; an apex court of AJK or Gilgit-Baltistan that prints only "the High
Court" has one court below (AJKHC, GBCC: the AJK Interim Constitution and the GB Order give each one High Court) and
is read so, marked `sole_court_below`. The Supreme Court's "the High Court" names no one court and is not read.

The case line is read by the case grammar every other reader uses (nizam.storage.case_key, D-125), with the court
below's own printed forms: a lineage and a citation of the same case give the same key. A date is never inferred:
an undated copy of the case below, or a case with several decisions and none of the printed date, is `case_held`
with no judgment chosen. Run after nizam.workers.judgment_cases, whose cases this reads.
"""
from __future__ import annotations

import argparse
import collections
import sys
import time

from nizam.corpus.judgment import fold
from nizam.storage.case_key import case_key, read_case_line
from nizam.storage.db import connect

BUILDER = "nizam.lineage_links/1"
SOLE_COURT_BELOW = {"AJKSC": "AJKHC", "GBSAC": "GBCC"}
_HIGH_COURT = {"the high court", "high court", "the learned high court", "learned high court"}


def _forms(cur) -> dict[str, list[tuple[str, str]]]:
    cur.execute("SELECT court_code, code, printed_forms FROM case_type")
    out = collections.defaultdict(list)
    for court, code, forms in cur.fetchall():
        for f in forms:
            out[court].append((fold(f), code))
    for v in out.values():
        v.sort(key=lambda x: -len(x[0]))
    return out


def court_below(upper_court: str, code: str | None, printed: str) -> tuple[str | None, str]:
    if code:
        return code, "printed"
    # 'the High Court', 'passed by the High Court', 'the Shariat Appellate Bench of the High Court' (a bench of it)
    if upper_court in SOLE_COURT_BELOW and (fold(printed) + " ").endswith("high court "):
        return SOLE_COURT_BELOW[upper_court], "sole_court_below"
    return None, "none"


def case_key_of(court: str, printed: str | None, forms: dict) -> str | None:
    """the case key the printed case line names in that court's forms, or None"""
    if not printed:
        return None
    f = fold(printed)
    code = next((cd for form, cd in forms.get(court, []) if f == form or f.startswith(form + " ")), None)
    if code is None:
        return None
    line = read_case_line(printed, [form for form, cd in forms[court] if cd == code])
    if not line or not line.lead or not line.year:
        return None
    return case_key(court, code, line.lead, line.year)


def build(cur) -> tuple[list[tuple], collections.Counter]:
    forms = _forms(cur)
    cur.execute("SELECT code FROM court")
    recorded = {r[0] for r in cur.fetchall()}
    # the held decisions of each case: (judgment id, decided_on, undated)
    cur.execute("""SELECT c.case_key, j.id, j.decided_on, j.decided_on_basis = 'undated'
                     FROM judgment_case c JOIN v_shown_judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on""")
    decisions = collections.defaultdict(list)
    for key, jid, day, undated in cur.fetchall():
        decisions[key].append((jid, day, undated))
    cur.execute("""SELECT l.id, l.upper_judgment_id, l.upper_decided_on, j.court_code, l.lower_court_code,
                          l.lower_court_printed, l.lower_case_printed, l.lower_decided_on
                     FROM judgment_lineage l
                     JOIN v_release_judgment j ON j.id = l.upper_judgment_id AND j.decided_on = l.upper_decided_on""")
    rows, tally = [], collections.Counter()
    for lid, up, up_day, up_court, code, court_printed, case_printed, low_day in cur.fetchall():
        court, basis = court_below(up_court, code, court_printed)
        key, low = None, None
        if court is None:
            # the Supreme Court's bare 'the High Court' names no one court: not read; any other printed name that is
            # not a recorded court is a tribunal or a court below the High Courts
            res = "not_read" if fold(court_printed) in _HIGH_COURT else "court_not_recorded"
        elif court not in recorded:
            court, res = None, "court_not_recorded"
        else:
            key = case_key_of(court, case_printed, forms)
            if key is None:
                res = "not_read"
            elif key not in decisions:
                res = "case_not_held"
            else:
                dated = [d for d in decisions[key] if not d[2] and low_day and d[1] == low_day]
                if len(dated) == 1:
                    low, res = dated[0][0], "resolved"
                else:
                    res = "case_held"
        rows.append((lid, up, up_day, court, key if res in ("resolved", "case_held", "case_not_held") else None,
                     low, low_day, res, basis if court else "none", BUILDER))
        tally[f"resolution:{res}"] += 1
        tally[f"basis:{basis if court else 'none'}"] += 1
    return rows, tally


def main() -> int:
    ap = argparse.ArgumentParser(description="link appeal chains to the judgments below (D-159)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    with connect() as conn, conn.cursor() as cur:
        rows, tally = build(cur)
        cur.execute("DELETE FROM judgment_lineage_link")
        with cur.copy("COPY judgment_lineage_link (lineage_id, upper_judgment_id, upper_decided_on, lower_court_code, "
                      "lower_case_key, lower_judgment_id, lower_decided_on, resolution, basis, builder) "
                      "FROM STDIN") as cp:
            for r in rows:
                cp.write_row(r)
        for k, v in sorted(tally.items()):
            print(f"  {k:28} {v:7,}")
        if a.apply:
            conn.commit()
            print(f"applied {len(rows)} rows in {time.time() - t0:.0f}s ({BUILDER})")
        else:
            conn.rollback()
            print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
