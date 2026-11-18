"""Lexical port benchmark (docs/03 §5): implementation A (pg_search BM25) against B (ts_rank_cd), on the golden sets.

    python evals/lexical_benchmark.py [--k 50] [--out evals/results/lexical-<date>.json]

PROVISIONAL (D-095). The golden sets 1-4 are drafts: text-checked, but their review sheets are not annotated and
inter-annotator agreement (kappa) is not measured (docs/10). These numbers say how the two implementations compare
on the same queries and gold; they are not the thesis figure docs/03 §5 asks for, which waits for the frozen,
kappa-checked split.

Per answerable case (expectedOutcome answer or conditional, with necessary units):
  * query = the case's question text, as a user typed it (no query understanding: this measures the index, not L3);
  * filters = the case's as-of date; its jurisdiction plus federal law (docs/04: applicable federal law plus the
    selected territorial law); 'foreign' cases are scoped to federal only;
  * a candidate HITS a necessary unit when it is that unit or lies inside it (a section's words are in its
    sub-sections, so the body index matches the sub-section);
  * recall@10 / recall@k: share of necessary units hit in the top 10 / k; MRR@10 over the first hit; latency.
Abstain cases are skipped here: abstention is the gate's measure (docs/04), not lexical recall's.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.storage.db import connect  # noqa: E402
from nizam.storage.lexical import (Bm25LexicalSearch, Filters, TsRankAnyLexicalSearch,  # noqa: E402
                                   TsRankLexicalSearch)


class FusedSearch:
    """L3's fused lexical candidates (nizam.retrieval.lexical, D-097), shaped like the port's candidates"""
    name = "fused"

    def search(self, q, filters, k):
        from types import SimpleNamespace
        from nizam.retrieval.lexical import lexical_candidates
        r = lexical_candidates(q, filters, k)
        return [SimpleNamespace(provision_id=c.unit_id, score=c.score, rank=c.rank) for c in r.candidates]


def cases():
    for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            units = d["retrievalGold"].get("necessaryUnits") or []
            if d["expectedOutcome"] in ("answer", "conditional") and units:
                yield d, units


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--out", default=str(ROOT / f"evals/results/lexical-{date.today().isoformat()}.json"))
    ap.add_argument("--impls", default="bm25,ts_rank_cd,ts_rank_cd_any,fused")
    ap.add_argument("--unscoped", action="store_true",
                    help="no jurisdiction from the case: only what the question itself says (place recognition)")
    a = ap.parse_args()
    every = [Bm25LexicalSearch(), TsRankLexicalSearch(), TsRankAnyLexicalSearch(), FusedSearch()]
    impls = [i for i in every if i.name in a.impls.split(",")]
    per = {i.name: [] for i in impls}
    with connect() as conn, conn.cursor() as cur:
        for d, units in cases():
            j = d["scope"]["jurisdiction"]
            juris = ("fed",) if j in ("fed", "foreign") else (j, "fed")
            f = Filters(as_of=date.fromisoformat(d["scope"]["asOf"]), jurisdictions=None if a.unscoped else juris)
            gold = {u["provisionId"]: u["path"] for u in units}
            for impl in impls:
                t = time.time()
                got = impl.search(d["question"]["text"], f, a.k)
                ms = (time.time() - t) * 1000
                cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])",
                            ([c.provision_id for c in got],))
                paths = dict(cur.fetchall())
                ranked = [paths.get(c.provision_id, "") for c in got]

                def hit_rank(gpath):
                    return next((r for r, p in enumerate(ranked, 1)
                                 if p == gpath or p.startswith(gpath + ".")), None)
                ranks = {g: hit_rank(p) for g, p in gold.items()}
                first = min((r for r in ranks.values() if r), default=None)
                per[impl.name].append({
                    "case": d["caseId"], "stratum": d["stratum"], "results": len(got), "ms": round(ms),
                    "recall10": sum(1 for r in ranks.values() if r and r <= 10) / len(gold),
                    f"recall{a.k}": sum(1 for r in ranks.values() if r) / len(gold),
                    "mrr10": (1 / first) if first and first <= 10 else 0.0})
    summary = {}
    for name, rows in per.items():
        summary[name] = {
            "cases": len(rows),
            "recall@10": round(statistics.mean(r["recall10"] for r in rows), 4),
            f"recall@{a.k}": round(statistics.mean(r[f"recall{a.k}"] for r in rows), 4),
            "mrr@10": round(statistics.mean(r["mrr10"] for r in rows), 4),
            "no_result_cases": sum(1 for r in rows if r["results"] == 0),
            "latency_ms_p50": round(statistics.median(r["ms"] for r in rows)),
            "latency_ms_p95": round(sorted(r["ms"] for r in rows)[int(0.95 * (len(rows) - 1))]),
            f"recall@{a.k} by stratum": {st: round(statistics.mean(r[f"recall{a.k}"] for r in rows
                                                                   if r["stratum"] == st), 3)
                                         for st in sorted({r["stratum"] for r in rows})},
        }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"provisional": "golden sets 1-4 are drafts; kappa not measured (D-095)",
                                       "k": a.k, "unscoped": a.unscoped, "summary": summary, "cases": per},
                                      indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
