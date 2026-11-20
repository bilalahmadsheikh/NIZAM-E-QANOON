"""rerank_budget.py SLATES_DIR MODEL_DIR [--out JSON] : the CPU reranker under a latency ceiling (D-101), scored by the
addendum fixed before these scores existed (evals/results/rerank-rule-addendum-cpu-2026-11-20.json).

For every passage length and rerank depth of the addendum's grid, every dev case's cpu/hybrid slate is reranked on THIS
host through nizam.inference.reranker.OnnxReranker exactly as served: the first `depth` units' passages are cut to
`chars` (the same word-boundary cut as unit_search.Session.unit_passages, applied to the stored 1,600-character body,
which is equivalent), scored in batches of 16 within the query, and timed. Cited units stay first; the scored rest are
reordered; units beyond `depth` keep the fused order. Then the addendum's rule: best NDCG@10 + MRR@10 among
configurations with p50 <= 1,000 ms, shipping only if its NDCG@10 beats the un-reranked slate with a paired 95% CI
clear of zero.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.paired_bootstrap import paired  # noqa: E402
from evals.rerank_eval import case_metrics  # noqa: E402

ADD = json.loads((ROOT / "evals/results/rerank-rule-addendum-cpu-2026-11-20.json").read_text(encoding="utf-8"))
SLATE = "cpu/hybrid"
CEILING_MS = 1000


def cut(passage: str, chars: int) -> str:
    """passage = prefix + '\\n' + body; the body cut as unit_passages cuts it at max_chars"""
    prefix, _, body = passage.partition("\n")
    if len(body) > chars:
        c = body.rfind(" ", 0, chars)
        body = body[: c if c > chars // 2 else chars]
    return prefix + "\n" + body


def rerank_depth(slate: list[dict], scores: dict[int, float], depth: int) -> list[dict]:
    head, tail = slate[:depth], slate[depth:]
    cited = [u for u in head if u["citation"]]
    rest = [u for u in head if not u["citation"]]
    rest = [u for _, _, u in sorted(((-scores[u["pid"]], i, u) for i, u in enumerate(rest)), key=lambda x: (x[0], x[1]))]
    return cited + rest + tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slates", type=Path)
    ap.add_argument("model_dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--limit", type=int, default=0, help="first N cases only (a smoke run; never a result)")
    a = ap.parse_args()
    from nizam.inference.reranker import OnnxReranker
    rr = OnnxReranker(a.model_dir)
    rr.score("warm up", ["warm up passage"] * 4)
    pairs = {}
    for line in open(a.slates / "pairs.jsonl", encoding="utf-8"):
        r = json.loads(line)
        pairs[r["pid"]] = r
    S = json.loads((a.slates / "slates.json").read_text(encoding="utf-8"))
    cases = list(S["cases"].items())[: a.limit or None]
    grid = [(c, d) for c in ADD["search"]["passage_chars"] for d in ADD["search"]["depth"]]
    per: dict[str, list[dict]] = {"fused": []}
    lat: dict[str, list[float]] = {}
    for n, (cid, c) in enumerate(cases, 1):
        slate = c["slates"][SLATE]
        gold = [g["path"] for g in c["gold"]]
        base = {"case": cid, "stratum": c["stratum"], "script": c["script"]}
        per["fused"].append(base | case_metrics([u["path"] for u in slate], gold))
        for chars, depth in grid:
            key = f"chars{chars}_depth{depth}"
            head = slate[:depth]
            q = pairs[head[0]["pid"]]["q"] if head else ""
            ps = [cut(pairs[u["pid"]]["p"], chars) for u in head]
            t = time.perf_counter()
            sc = rr.score(q, ps) if ps else []
            lat.setdefault(key, []).append((time.perf_counter() - t) * 1000)
            ranked = rerank_depth(slate, {u["pid"]: s for u, s in zip(head, sc)}, depth)
            per.setdefault(key, []).append(base | case_metrics([u["path"] for u in ranked], gold))
        if n % 10 == 0:
            print(f"  {n}/{len(cases)} cases", flush=True)
    table = {}
    for key, rows in per.items():
        t = {k: round(float(np.mean([r[k] for r in rows])), 4) for k in ("ndcg10", "mrr10", "r10")}
        if key in lat:
            t |= {"p50_ms": round(float(np.percentile(lat[key], 50))), "p95_ms": round(float(np.percentile(lat[key], 95)))}
        table[key] = t
    print(f"{'configuration':22} {'NDCG@10':>8} {'MRR@10':>7} {'R@10':>6} {'p50 ms':>7} {'p95 ms':>7}")
    for key, t in table.items():
        print(f"{key:22} {t['ndcg10']:8.3f} {t['mrr10']:7.3f} {t['r10']:6.3f} {t.get('p50_ms', ''):>7} {t.get('p95_ms', ''):>7}")
    ok = [k for k in table if k != "fused" and table[k]["p50_ms"] <= CEILING_MS]
    decision: dict = {"under_ceiling": ok}
    if ok:
        best = max(ok, key=lambda k: (table[k]["ndcg10"] + table[k]["mrr10"], -table[k]["p50_ms"]))
        ci = {k: paired(per["fused"], per[best], k) for k in ("ndcg10", "mrr10", "r10")}
        decision |= {"chosen": best, "scores": table[best], "vs_unreranked_hybrid": ci, "ships": ci["ndcg10"]["ci95"][0] > 0}
        print(f"\nchosen {best}: " + "  ".join(
            f"{k} {v['mean']*100:+.1f} [{v['ci95'][0]*100:+.1f},{v['ci95'][1]*100:+.1f}] {v['better']}b/{v['worse']}w"
            for k, v in ci.items()) + f"  -> {'SHIPS' if decision['ships'] else 'does not ship'}")
    else:
        decision |= {"chosen": None, "ships": False}
        print("\nno configuration is under the 1,000 ms ceiling: the CPU profile serves 'unreranked' (addendum rule C)")
    if a.out:
        a.out.write_text(json.dumps({"split": S["split"], "slate": SLATE, "rule": "evals/results/rerank-rule-addendum-cpu-2026-11-20.json",
                                     "model": rr.info.model, "revision": rr.info.revision,
                                     "threads": rr.sess.get_session_options().intra_op_num_threads,
                                     "cases": len(cases), "limit": a.limit or None, "table": table, "decision": decision,
                                     "per_case": per, "latency_ms": {k: [round(x, 1) for x in v] for k, v in lat.items()}},
                                    indent=1), encoding="utf-8")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
