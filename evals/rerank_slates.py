"""rerank_slates.py --split dev|test --out DIR [--precomputed BUNDLE --vectors F --questions F] : the candidate slates
a reranker is measured on (D-101), from the SERVED path, and the passages it reads.

For every answerable golden case of the split (as evals/lexical_benchmark.py scopes it: the case's as_of; its
jurisdiction plus federal law; 'foreign' federal only), and for each profile:
  cpu   the bge-m3 space (the in-process int8 encoder)
  gpu   the 8B space (question vectors made on the GPU, replayed by evals/precomputed_encoder.py; --precomputed)
two slates of k = 50 gated units (evals/results/rerank-rule-2026-11-20.json):
  hybrid       nizam.retrieval.candidates.candidates  (citations, RRF of lexical fusion and dense)
  cited_dense  candidates(windows=False)               (citations, then dense; no BM25 windows)
A degraded slate (lexical_only, dense_cpu) is refused: it would be scored as the better path.

Writes DIR/pairs.jsonl  {"pid", "q", "p"}: one row per (case, unit), the question and Session.unit_passages' text --
                        the ONLY file that leaves this machine (a Kaggle dataset); it holds no gold
       DIR/slates.json  per case: stratum, script, gold units (provision id, path), and per profile/slate the ranked
                        units with their path, fused score and pid -- local, for scoring
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from lexical_benchmark import cases  # noqa: E402

from nizam.retrieval.candidates import candidates  # noqa: E402
from nizam.storage import unit_search  # noqa: E402
from nizam.storage.lexical import Filters  # noqa: E402

K = 50
SLATES = {"hybrid": True, "cited_dense": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--precomputed")
    ap.add_argument("--vectors", default="reference_q.npy")
    ap.add_argument("--questions", default="reference_questions.json")
    ap.add_argument("--profiles", default="cpu,gpu")
    a = ap.parse_args()
    profiles = a.profiles.split(",")
    enc = None
    if "gpu" in profiles:
        if not a.precomputed:
            sys.exit("the gpu profile needs --precomputed (no GPU encoder on this host)")
        from precomputed_encoder import PrecomputedEncoder
        enc = PrecomputedEncoder.from_bundle(Path(a.precomputed), a.vectors, a.questions)
    os.environ["NIZAM_DENSE_PROFILE"] = "cpu"            # the cpu profile's encoder; the gpu one is injected
    a.out.mkdir(parents=True, exist_ok=True)
    pid_of: dict[tuple[str, str], int] = {}
    pairs, out = [], {}
    t0 = time.time()
    for d, units in cases(a.split):
        cid, q = d["caseId"], d["question"]["text"]
        j = d["scope"]["jurisdiction"]
        juris = ("fed",) if j in ("fed", "foreign") else (j, "fed")
        f = Filters(as_of=date.fromisoformat(d["scope"]["asOf"]), jurisdictions=juris)
        rec = {"stratum": d["stratum"], "script": d["question"].get("script", "latin"),
               "gold": [{"provisionId": u["provisionId"], "path": u["path"]} for u in units], "slates": {}}
        for prof in profiles:
            for name, windows in SLATES.items():
                r = candidates(q, f, K, encoder=enc if prof == "gpu" else None, windows=windows)
                if r.degraded:
                    sys.exit(f"{cid} {prof}/{name}: degraded to {r.degraded} -- refusing to score it as {prof}")
                want = 2 if prof == "gpu" else 1
                if r.trace.get("dense_generation") != want:
                    sys.exit(f"{cid} {prof}/{name}: searched generation {r.trace.get('dense_generation')}, not {want}")
                with unit_search.session(r.filters) as s:
                    texts = s.unit_passages([(c.unit_id, c.version_id) for c in r.candidates])
                    s.cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])",
                                  ([c.unit_id for c in r.candidates],))
                    paths = dict(s.cur.fetchall())
                ranked = []
                for c in r.candidates:
                    key = (cid, c.unit_id)
                    if key not in pid_of:
                        pid_of[key] = len(pairs)
                        pairs.append({"pid": len(pairs), "q": q, "p": texts[c.unit_id]})
                    ranked.append({"unit": c.unit_id, "path": paths.get(c.unit_id, ""), "score": c.score,
                                   "citation": c.via_citation, "pid": pid_of[key]})
                rec["slates"][f"{prof}/{name}"] = ranked
        out[cid] = rec
        print(f"  {cid}: {len(pairs)} pairs so far ({time.time() - t0:.0f}s)", flush=True)
    with open(a.out / "pairs.jsonl", "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    (a.out / "slates.json").write_text(json.dumps({"split": a.split, "k": K, "profiles": profiles,
                                                   "built": date.today().isoformat(), "cases": out},
                                                  ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(out)} cases, {len(pairs)} distinct (question, unit) pairs -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
