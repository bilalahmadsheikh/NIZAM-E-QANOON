"""rerank_eval.py SLATES_DIR SCORES_DIR... [--out JSON] : the reranker bake-off on the golden split (D-101), scored by
the rule fixed before any score existed (evals/results/rerank-rule-2026-11-20.json).

SLATES_DIR is evals/rerank_slates.py's output (slates.json, local, with the gold); each SCORES_DIR holds a Kaggle run's
scores-<model>.npy (tools/kaggle/rerank_kernel.py, by pid) and run.json. For every profile/slate and every model:
  * the slate is reordered by the model's score (ties keep the fused order); units the citation fast path resolved
    stay first, in their order (the rule's "citations");
  * per case: NDCG@10 (binary gains; a unit hits a gold unit when it is it or lies inside it; each gold unit is
    credited once; ideal DCG over min(|gold|, 10)), MRR@10, recall@10, recall@50 of the slate;
  * the un-reranked slate is the 'fused' row.
Then the rule: per profile, best (model, slate) by NDCG@10 + MRR@10 among allowed models; a cheaper pair within 1
point on both replaces it; it ships only if its NDCG@10 beats the profile's un-reranked hybrid with a paired 95% CI
clear of zero (evals/paired_bootstrap.py).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.paired_bootstrap import paired  # noqa: E402

RULE = json.loads((ROOT / "evals/results/rerank-rule-2026-11-20.json").read_text(encoding="utf-8"))
PARAMS = {"mminilm": 117641603, "gte-ml": 305959681, "bge-v2-m3": 567755777, "qwen3-0.6b": 595776512,
          "qwen3-4b": 4021784576, "qwen3-8b": 8188548096}
CPU_MAX_PARAMS = 600_000_000


def hits(path: str, gold: list[str]) -> str | None:
    return next((g for g in gold if path == g or path.startswith(g + ".")), None)


def case_metrics(ranked_paths: list[str], gold: list[str]) -> dict:
    credited, dcg, first, r10 = set(), 0.0, None, 0
    for i, p in enumerate(ranked_paths, 1):
        g = hits(p, gold)
        if g is None or g in credited:
            continue
        credited.add(g)
        if i <= 10:
            dcg += 1.0 / math.log2(i + 1)
            r10 += 1
            first = first or i
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(gold), 10) + 1))
    return {"ndcg10": dcg / idcg, "mrr10": 1.0 / first if first else 0.0, "r10": r10 / len(gold),
            "r50": len(credited) / len(gold)}


def reorder(slate: list[dict], scores: np.ndarray | None) -> list[dict]:
    if scores is None:
        return slate
    cited = [u for u in slate if u["citation"]]
    rest = [u for u in slate if not u["citation"]]
    rest = [u for _, _, u in sorted(((-float(scores[u["pid"]]), i, u) for i, u in enumerate(rest)),
                                    key=lambda x: (x[0], x[1]))]
    return cited + rest


def summarise(rows: list[dict]) -> dict:
    return {k: round(float(np.mean([r[k] for r in rows])), 4) for k in ("ndcg10", "mrr10", "r10", "r50")} | \
        {"n": len(rows)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slates", type=Path)
    ap.add_argument("scores", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    S = json.loads((a.slates / "slates.json").read_text(encoding="utf-8"))
    npairs = sum(1 for _ in open(a.slates / "pairs.jsonl", encoding="utf-8"))
    models: dict[str, np.ndarray] = {}
    runs = {}
    for d in a.scores:
        d = d / "out" if (d / "out").exists() else d
        run = (json.loads((d / "run.json").read_text(encoding="utf-8")) if (d / "run.json").exists()
               else {"pairs": npairs, "models": {}})
        if run["pairs"] != npairs:
            sys.exit(f"{d}: scored {run['pairs']} pairs, the slates hold {npairs} (a smoke run, or another dataset)")
        # a model whose scores were saved but whose run.json entry was not (the kernel writes it after the latency
        # step, which ran out of T4 memory at 50 long pairs for the 4B and 8B rerankers, 20 Nov): its scores count
        # if complete and finite; its latency is recorded as not measured
        for f in sorted(d.glob("scores-*.npy")):
            slug = f.stem[len("scores-"):]
            if slug.startswith("int8") or slug in models:
                continue
            sc = np.load(f)
            if len(sc) != npairs or not np.isfinite(sc).all():
                sys.exit(f"{d}/{slug}: {len(sc)} scores, {int((~np.isfinite(sc)).sum())} non-finite")
            models[slug] = sc
            runs[slug] = run["models"].get(slug) or {
                "latency": None, "note": "scored in full; the kernel's latency step ran out of GPU memory (T4, 50 "
                                         "pairs in one batch), so run.json has no entry: latency not measured"}
    cases = S["cases"]
    slates = sorted({k for c in cases.values() for k in c["slates"]})
    per: dict = {}
    for sl in slates:
        for slug in ["fused"] + sorted(models):
            rows = []
            for cid, c in cases.items():
                gold = [g["path"] for g in c["gold"]]
                ranked = reorder(c["slates"][sl], models.get(slug))
                rows.append({"case": cid, "stratum": c["stratum"], "script": c["script"],
                             **case_metrics([u["path"] for u in ranked], gold)})
            per[f"{sl}|{slug}"] = rows
    table = {k: summarise(v) for k, v in per.items()}
    print(f"{'profile/slate':20} {'model':12} {'NDCG@10':>8} {'MRR@10':>7} {'R@10':>6} {'R@50':>6}")
    for k in sorted(table):
        sl, slug = k.split("|")
        t = table[k]
        print(f"{sl:20} {slug:12} {t['ndcg10']:8.3f} {t['mrr10']:7.3f} {t['r10']:6.3f} {t['r50']:6.3f}")
    # the rule
    decision = {}
    for prof in sorted({sl.split("/")[0] for sl in slates}):
        allowed = [m for m in models if prof == "gpu" or PARAMS[m] <= CPU_MAX_PARAMS]
        arms = [(sl, m) for sl in slates if sl.startswith(prof + "/") for m in allowed]
        if not arms:
            continue
        val = {arm: table[f"{arm[0]}|{arm[1]}"]["ndcg10"] + table[f"{arm[0]}|{arm[1]}"]["mrr10"] for arm in arms}
        best = max(arms, key=lambda x: (val[x], -PARAMS[x[1]]))
        bt = table[f"{best[0]}|{best[1]}"]
        chosen = best
        for arm in sorted(arms, key=lambda x: (PARAMS[x[1]], x[0])):
            t = table[f"{arm[0]}|{arm[1]}"]
            if PARAMS[arm[1]] < PARAMS[best[1]] and bt["ndcg10"] - t["ndcg10"] <= 0.01 and bt["mrr10"] - t["mrr10"] <= 0.01:
                chosen = arm
                break
        base = per[f"{prof}/hybrid|fused"]
        ch = per[f"{chosen[0]}|{chosen[1]}"]
        ci = {k: paired(base, ch, k) for k in ("ndcg10", "mrr10", "r10")}
        ships = ci["ndcg10"]["ci95"][0] > 0
        decision[prof] = {"best": list(best), "chosen": list(chosen), "chosen_scores": table[f"{chosen[0]}|{chosen[1]}"],
                          "vs_unreranked_hybrid": ci, "ships": ships}
        print(f"\n{prof}: best {best}, chosen {chosen}; vs un-reranked hybrid: " + "  ".join(
            f"{k} {v['mean']*100:+.1f} [{v['ci95'][0]*100:+.1f},{v['ci95'][1]*100:+.1f}] {v['better']}b/{v['worse']}w"
            for k, v in ci.items()) + f"  -> {'SHIPS' if ships else 'does not ship'}")
        for sc in ("latin", "arabic", "roman_urdu"):
            rows = [r for r in ch if r["script"] == sc]
            if rows:
                print(f"   {sc:10} n={len(rows):3} NDCG@10 {np.mean([r['ndcg10'] for r in rows]):.3f}"
                      f" (fused {np.mean([r['ndcg10'] for r in base if r['script'] == sc]):.3f})")
    if a.out:
        a.out.write_text(json.dumps({"split": S["split"], "rule": "evals/results/rerank-rule-2026-11-20.json",
                                     "runs": runs, "table": table, "decision": decision, "per_case": per},
                                    indent=1), encoding="utf-8")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
