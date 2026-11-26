"""law_precedent_join_study.py: does "the law first, then the judgments that cite it" reach the right judgments?
A descriptive study for docs/ANSWER-COMPOSITION.md (D-172). Dev splits only; no test case is read.

A. Statute dev (evals/golden split-v1 dev): for each answerable case's gold units, how many have any released
   judgment paragraph that cites them (or a unit inside them), by role (interpreted / quoted / challenged / charge /
   cited), and how many have one from a court binding the case's forum (SC; the forum's own High Court).
B. Precedent dev (split-precedent-v1 dev, sets 1+2, answerable, not case lookups): for each case, the statute search
   (candidates(), the CPU profile's hybrid, k=50, at the case's as_of and forum territory) is run on the question.
   Then: does a gold judgment cite any provision at all; does a GOLD PARAGRAPH cite one; is a provision the gold
   paragraph (or judgment) cites among the statute search's first 10 / 50 units; and how many released judgments
   cite those same units (the fan-out a ranker would have to sort).

    python evals/law_precedent_join_study.py [--out evals/results/join-study-2026-11-27.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

BINDING = {"punjab": "LHC", "sindh": "SHC", "kp": "PHC", "balochistan": "BHC", "ict": "IHC"}


def units_cited(cur, unit_ids: list[str]) -> dict[str, collections.Counter]:
    """unit id -> Counter of (role, court) over released resolved references to it or a provision inside it"""
    out = {}
    for u in unit_ids:
        cur.execute("""
            SELECT r.role, j.court_code, count(DISTINCT r.judgment_id)
              FROM provision up
              JOIN provision p ON p.instrument_id = up.instrument_id AND p.path <@ up.path
              JOIN judgment_statute_reference r ON r.dst_provision_id = p.id AND r.resolution = 'resolved'
              JOIN v_release_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
             WHERE up.id = %s GROUP BY 1, 2""", (u,))
        c = collections.Counter()
        for role, court, n in cur.fetchall():
            c[(role, court)] += n
        out[u] = c
    return out


def study_a(cur) -> dict:
    from lexical_benchmark import cases
    rows, n_units = [], 0
    for d, units in cases("dev"):
        forum = d["scope"].get("territory") or d["scope"]["jurisdiction"]
        ids = [u["provisionId"] for u in units]
        cited = units_cited(cur, ids)
        for u in ids:
            n_units += 1
            c = cited[u]
            any_ = sum(c.values())
            interp = sum(v for (role, _), v in c.items() if role in ("interpreted", "quoted", "challenged"))
            binding = sum(v for (role, court), v in c.items() if court == "SC" or court == BINDING.get(forum))
            rows.append({"case": d["caseId"], "unit": u, "forum": forum, "judgments": any_,
                         "interpreting": interp, "binding": binding})
    share = lambda f: round(sum(1 for r in rows if f(r)) / max(len(rows), 1), 3)  # noqa: E731
    return {"gold_units": n_units, "cases": len({r["case"] for r in rows}),
            "share_cited_by_any_judgment": share(lambda r: r["judgments"] > 0),
            "share_interpreted_quoted_or_challenged": share(lambda r: r["interpreting"] > 0),
            "share_cited_by_a_binding_court": share(lambda r: r["binding"] > 0),
            "median_judgments_per_cited_unit": sorted(r["judgments"] for r in rows if r["judgments"])[
                len([r for r in rows if r["judgments"]]) // 2] if any(r["judgments"] for r in rows) else 0,
            "rows": rows}


def study_b(conn, cur) -> dict:
    import precedent_eval as PE
    from nizam.retrieval.candidates import candidates
    from nizam.storage import unit_search
    from nizam.storage.lexical import Filters
    split = json.loads(PE.SPLIT.read_text(encoding="utf-8"))
    chosen = [c for c in PE.cases() if c["familyId"] in split["dev"] and c["expectedOutcome"] != "abstain"
              and c["stratum"] != "case_lookup"]
    docs = {u["judgmentDocumentId"] for c in chosen for u in c["precedentGold"]["necessaryJudgments"]}
    from nizam.storage.judgment_read import JudgmentRead
    repo = JudgmentRead()
    repo.open()
    with repo.transaction() as jc:                               # dict rows, as precedent_eval reads them
        to_j = PE._doc_to_judgment(jc, docs)
    repo.close()
    rows, t0 = [], time.time()
    for c in chosen:
        s = c["scope"]
        terr = s.get("territory")
        juris = ("fed",) if terr in (None, "ict", "fed") else (terr, "fed")
        f = Filters(as_of=date.fromisoformat(s["asOf"]), territory=terr if terr != "fed" else None,
                    jurisdictions=juris)
        r = candidates(c["question"]["text"], f, 50)
        law = [x.unit_id for x in r.candidates]
        gold = c["precedentGold"]["necessaryJudgments"]
        jids = [to_j[u["judgmentDocumentId"]] for u in gold if u["judgmentDocumentId"] in to_j]
        cur.execute("""SELECT r.judgment_id::text, r.dst_provision_id::text, p.printed_no
                         FROM judgment_statute_reference r
                         JOIN judgment_paragraph p ON p.id = r.paragraph_id AND p.decided_on = r.decided_on
                        WHERE r.judgment_id = ANY(%s::uuid[]) AND r.resolution = 'resolved'""", (jids,))
        refs = cur.fetchall()
        gold_paras = {(to_j.get(u["judgmentDocumentId"]), u["printedNo"]) for u in gold if u.get("printedNo")}
        para_provs = {p for j, p, no in refs if (j, no) in gold_paras}
        judg_provs = {p for _, p, _ in refs}
        with unit_search.session(f) as ss:
            umap = ss.units_of(sorted(judg_provs))
            ss.cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])", (law,))
            lpath = dict(ss.cur.fetchall())
        inst = {x.unit_id: x.instrument_id for x in r.candidates}

        def hit(provs, depth):
            for p in provs:
                u = umap.get(p)
                if not u:
                    continue
                for lu in law[:depth]:
                    lp = lpath.get(lu, "")
                    if inst[lu] == u.instrument_id and (lp == u.path or lp.startswith(u.path + ".")
                                                        or u.path.startswith(lp + ".")):
                        return True
            return False
        fan = 0
        if law[:10]:
            cur.execute("""SELECT count(DISTINCT r.judgment_id) FROM provision up
                             JOIN provision p ON p.instrument_id = up.instrument_id AND p.path <@ up.path
                             JOIN judgment_statute_reference r ON r.dst_provision_id = p.id AND r.resolution='resolved'
                            WHERE up.id = ANY(%s::uuid[])""", (law[:10],))
            fan = cur.fetchone()[0]
        rows.append({"case": c["caseId"], "stratum": c["stratum"], "judgment_cites_law": bool(judg_provs),
                     "gold_paragraph_cites_law": bool(para_provs),
                     "paragraph_law_in_top10": hit(para_provs, 10), "paragraph_law_in_top50": hit(para_provs, 50),
                     "judgment_law_in_top10": hit(judg_provs, 10), "judgment_law_in_top50": hit(judg_provs, 50),
                     "judgments_citing_top10_units": fan})
        print(f"  {c['caseId']}: {rows[-1]} ({time.time() - t0:.0f}s)", flush=True)
    share = lambda k: round(sum(r[k] for r in rows) / max(len(rows), 1), 3)  # noqa: E731
    fans = sorted(r["judgments_citing_top10_units"] for r in rows)
    return {"cases": len(rows), **{k: share(k) for k in ("judgment_cites_law", "gold_paragraph_cites_law",
                                                          "paragraph_law_in_top10", "paragraph_law_in_top50",
                                                          "judgment_law_in_top10", "judgment_law_in_top50")},
            "median_judgments_citing_top10_units": fans[len(fans) // 2] if fans else 0, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / f"evals/results/join-study-{date.today().isoformat()}.json"))
    a = ap.parse_args()
    os.environ.setdefault("NIZAM_DENSE_PROFILE", "cpu")
    from nizam.storage.db import connect
    with connect() as conn:
        conn.execute("SET statement_timeout = 0")
        with conn.cursor() as cur:
            A = study_a(cur)
            print({k: v for k, v in A.items() if k != "rows"}, flush=True)
            B = study_b(conn, cur)
    out = {"built": date.today().isoformat(), "A_statute_dev": A, "B_precedent_dev": B}
    Path(a.out).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"A": {k: v for k, v in A.items() if k != "rows"},
                      "B": {k: v for k, v in B.items() if k != "rows"}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
