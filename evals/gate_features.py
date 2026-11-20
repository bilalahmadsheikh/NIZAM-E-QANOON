"""gate_features.py --split dev|test [--modes cpu,unreranked,gpu] : the sufficiency gate's inputs, from the SERVED path
(D-102; the rule is evals/results/gate-rule-2026-11-20.json, fixed before this ran).

For every golden case of the split -- answerable AND abstain (the gate's negatives) -- scoped as
evals/lexical_benchmark.py scopes it (the case's as_of; its jurisdiction plus federal; 'foreign' federal only):
  cpu         candidates (hybrid slate, bge-m3 space) -> rerank with the int8 CPU reranker  (= ranked() on the cpu
              profile, the same two calls)
  unreranked  the same candidates in fused order, marked unreranked (docs/04 §9.2's degraded mode)
  gpu         candidates(windows=False) in the 8B space (question vectors replayed) -> Qwen3-Reranker-8B scores
              replayed (evals/precomputed_reranker.py). A pair with no replayed score is written to
              --pending DIR/pairs.jsonl for a Kaggle run and the case is marked pending (never scored otherwise)
Per case and mode: the gate's features (nizam.retrieval.gate.features -- the function serving uses), the label
(sufficient: every proposition's necessary evidence hit in the first BUNDLE units), the hit ranks, the bundle, and
the scope veto finding (computed, never short-circuiting, so the classifier is measured on every case).

PROVISIONAL: golden sets 1-4 are drafts (D-095).
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from precomputed_encoder import PrecomputedEncoder  # noqa: E402
from precomputed_reranker import PrecomputedReranker  # noqa: E402

from nizam.inference.reranker import RerankerInfo  # noqa: E402
from nizam.retrieval import gate as G  # noqa: E402
from nizam.retrieval.candidates import candidates  # noqa: E402
from nizam.retrieval.query import parse  # noqa: E402
from nizam.retrieval.rerank import SLATE_WINDOWS, rerank  # noqa: E402
from nizam.storage import unit_search  # noqa: E402
from nizam.storage.lexical import Filters  # noqa: E402

DATA = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
# the GPU question vectors: dev answerable (the corpus run's bundle), test answerable (D-101), abstain cases (D-102)
GPU_QUESTIONS = [(DATA / "models/encoder-gpu", "reference_q.npy", "reference_questions.json"),
                 (DATA / "embed/out-q8t1/out", "q.npy", "questions.json"),
                 (DATA / "embed/out-q8x1/out", "q.npy", "questions.json"),
                 (DATA / "embed/out-q8n1/out", "q.npy", "questions.json")]   # golden sets 5-10 (D-104)
# Qwen3-Reranker-8B scores: (pairs.jsonl, scores.npy) -- dev (rr2), test (rrt-8b), abstain cases (D-102)
GPU_SCORES = [(DATA / "rerank/ds-dev/pairs.jsonl", DATA / "rerank/out-rr2/out/scores-qwen3-8b.npy"),
              (DATA / "rerank/ds-test-gpu/pairs.jsonl", DATA / "rerank/out-rrt-8b/out/scores-qwen3-8b.npy"),
              (DATA / "rerank/ds-gate-x/pairs.jsonl", DATA / "rerank/out-rrg-8b/out/scores-qwen3-8b.npy")]
GPU_RERANKER = RerankerInfo("Qwen/Qwen3-Reranker-8B", "77d193c791ed757ca307ee72715aa132723da912", "qwen", 1024,
                            "Given a question about Pakistani law, retrieve the statutory provisions that answer it",
                            "gpu")


def all_cases(split: str):
    keep = set(json.loads((ROOT / "evals/golden/split-v1.json").read_text(encoding="utf-8"))[split])
    for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            if d["caseId"] in keep:
                yield d


def propositions(d) -> list[set[str]]:
    """the rule's coverage: one set of necessary unit ids per proposition (necessaryUnits as one, if none listed)"""
    if d["expectedOutcome"] not in ("answer", "conditional"):
        return []
    props = [set(p["necessaryEvidence"]) for p in d.get("propositions") or [] if p.get("necessaryEvidence")]
    if not props:
        nec = {u["provisionId"] for u in d["retrievalGold"].get("necessaryUnits") or []}
        props = [nec] if nec else []
    return props


class MultiEncoder(PrecomputedEncoder):
    def __init__(self, sources):
        qs, vs, info = [], [], None
        for d, vec, qf in sources:
            if not (d / vec).exists():
                continue
            e = PrecomputedEncoder.from_bundle(d, vec, qf)
            info = info or e.info
            if (e.info.model, e.info.revision) != (info.model, info.revision):
                raise SystemExit(f"{d}: another space ({e.info.model}@{e.info.revision})")
            qs += json.loads((d / qf).read_text(encoding="utf-8"))
            vs.append(np.load(d / vec))
        super().__init__(info, qs, np.concatenate(vs))


class MultiReranker(PrecomputedReranker):
    def __init__(self, info, sources):
        self.info, self._by = info, {}
        for pairs, scores in sources:
            if pairs.exists() and scores.exists():
                part = PrecomputedReranker(info, pairs, scores)
                self._by.update(part._by)


def label_and_hits(d, r, paths) -> tuple[int, dict]:
    ranked = [paths.get(c.unit_id, "") for c in r.candidates]
    gold = {u["provisionId"]: u["path"] for u in d["retrievalGold"].get("necessaryUnits") or []}

    def hit_rank(gpath):
        return next((i for i, p in enumerate(ranked, 1) if p == gpath or p.startswith(gpath + ".")), None)
    ranks = {g: hit_rank(p) for g, p in gold.items()}
    props = propositions(d)
    ok = bool(props) and all(any((ranks.get(u) or 99) <= G.BUNDLE for u in prop if u in gold) for prop in props)
    return int(ok), {g: r_ for g, r_ in ranks.items()}


def row(d, r, mode, ms, cur):
    cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])",
                ([c.unit_id for c in r.candidates],))
    paths = dict(cur.fetchall())
    lab, ranks = label_and_hits(d, r, paths)
    return {"features": G.features(r, mode), "sufficient": lab, "hit_ranks": ranks, "results": len(r.candidates),
            # the bundle's raw signals, so a feature can be recomputed by gate.features from these rows
            "bundle": [{"unit": c.unit_id, "version": c.version_id, "instrument": c.instrument_id, "fused": c.score,
                        "rank": c.rank, "rerank": c.rerank_score, "ranks": c.generator_ranks,
                        "cited": c.via_citation} for c in r.candidates[:G.BUNDLE]],
            "degraded": r.degraded, "ms": round(ms),
            "dense_generation": r.trace.get("dense_generation"),
            "reranker": (lambda x: f"{x.get('model')}@{x.get('revision')}" if x else None)(r.trace.get("rerank"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--modes", default="cpu,unreranked,gpu")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pending", type=Path, default=DATA / "rerank/ds-gate-x",
                    help="where GPU pairs with no replayed score are written (a Kaggle dataset: pairs only, no gold)")
    a = ap.parse_args()
    modes = a.modes.split(",")
    out_path = a.out or ROOT / f"evals/results/gate-features-{a.split}-{date.today().isoformat()}.json"
    prior = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"cases": {}}
    os.environ["NIZAM_DENSE_PROFILE"] = "cpu"
    os.environ["NIZAM_RERANK_PROFILE"] = "cpu"
    enc = MultiEncoder(GPU_QUESTIONS) if "gpu" in modes else None
    rr_gpu = MultiReranker(GPU_RERANKER, GPU_SCORES) if "gpu" in modes else None
    pending, out = [], prior["cases"]
    from nizam.storage.db import connect
    t_all = time.time()
    with connect() as conn, conn.cursor() as cur:
        for d in all_cases(a.split):
            cid, q = d["caseId"], d["question"]["text"]
            j = d["scope"]["jurisdiction"]
            juris = ("fed",) if j in ("fed", "foreign") else (j, "fed")
            f = Filters(as_of=date.fromisoformat(d["scope"]["asOf"]), jurisdictions=juris)
            spec = parse(q)
            finding = G.pre_veto(spec, f)
            rec = out.setdefault(cid, {})
            rec.update({"family": d["familyId"], "stratum": d["stratum"], "script": d["question"].get("script", "latin"),
                        "expected": d["expectedOutcome"], "abstention_code": (d.get("abstention") or {}).get("code"),
                        "veto": finding.__dict__ if finding else None})
            rec.setdefault("modes", {})
            if "cpu" in modes or "unreranked" in modes:
                t = time.perf_counter()
                r0 = candidates(spec, f, 50, windows=SLATE_WINDOWS["cpu"])
                t_c = (time.perf_counter() - t) * 1000
                if r0.degraded:
                    sys.exit(f"{cid}: cpu slate degraded to {r0.degraded}")
                if "unreranked" in modes:
                    ru = copy.deepcopy(r0)
                    ru.degraded = "unreranked"
                    rec["modes"]["unreranked"] = row(d, ru, "unreranked", t_c, cur)
                if "cpu" in modes:
                    t = time.perf_counter()
                    rc = rerank(r0)
                    if rc.degraded:
                        sys.exit(f"{cid}: cpu reranker degraded to {rc.degraded}: {rc.trace.get('degraded_stages')}")
                    rec["modes"]["cpu"] = row(d, rc, "cpu", t_c + (time.perf_counter() - t) * 1000, cur)
            if "gpu" in modes:
                t = time.perf_counter()
                rg = candidates(spec, f, 50, encoder=enc, windows=SLATE_WINDOWS["gpu"])
                if rg.degraded or rg.trace.get("dense_generation") != 2:
                    sys.exit(f"{cid}: gpu slate degraded ({rg.degraded}, generation {rg.trace.get('dense_generation')})")
                try:
                    rg = rerank(rg, reranker=rr_gpu)
                except ValueError:
                    rg = None
                if rg is None or rg.degraded:
                    r_again = candidates(spec, f, 50, encoder=enc, windows=SLATE_WINDOWS["gpu"])
                    with unit_search.session(r_again.filters) as s:
                        texts = s.unit_passages([(c.unit_id, c.version_id) for c in r_again.candidates],
                                                max_chars=1600)
                    for c in r_again.candidates:
                        pending.append({"q": q, "p": texts[c.unit_id]})
                    rec["modes"]["gpu"] = {"pending": True}
                else:
                    rec["modes"]["gpu"] = row(d, rg, "gpu", (time.perf_counter() - t) * 1000, cur)
            if a.split == "dev":         # test outcomes are not looked at before the calibration is frozen
                print(f"  {cid} {d['stratum']:<13} " + "  ".join(
                    f"{m}:{rec['modes'][m].get('sufficient', 'P')}/{(rec['modes'][m].get('features') or {}).get('top')}"
                    for m in modes if m in rec["modes"]), flush=True)
            else:
                print(f"  {cid}", flush=True)
    if pending:                      # appended to what an earlier split left, pids continuing, no pair twice
        a.pending.mkdir(parents=True, exist_ok=True)
        pf = a.pending / "pairs.jsonl"
        have = [json.loads(x) for x in open(pf, encoding="utf-8")] if pf.exists() else []
        seen = {(" ".join(p["q"].split()), p["p"]) for p in have}
        rows = []
        for p in pending:
            k = (" ".join(p["q"].split()), p["p"])
            if k not in seen:
                seen.add(k)
                rows.append({"pid": len(have) + len(rows), **p})
        with open(pf, "a", encoding="utf-8") as fh:
            for p in rows:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"{len(rows)} GPU pairs pending -> {pf} (score on Kaggle, then rerun --modes gpu)")
    out_path.write_text(json.dumps({"provisional": "golden sets 1-4 are drafts; kappa not measured (D-095)",
                                    "rule": "evals/results/gate-rule-2026-11-20.json", "split": a.split,
                                    "bundle": G.BUNDLE, "built": date.today().isoformat(), "cases": out},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} cases -> {out_path} ({time.time() - t_all:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
