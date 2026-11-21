"""adr1d_eval.py EXPORT_DIR RUN_DIR [--out F] : ADR-1d after reranking, the CPU generation (bge-m3), on DEV (D-110).

ADR-1d (D-005): binary vectors stay only if they cost at most 2 NDCG@10 points AFTER reranking. Two arms, the same
float question vector (RUN_DIR/bge-m3/q.npy: the Kaggle run at the generation's own commit), the same reranker:

  binary  the SERVED dense generator: nizam.retrieval.lexical.dense_units over the stored sign bits, collapsed to
          legal units
  float   the run's float window (RUN_DIR/bge-m3/topf_ids.npy, topf_sims.npy: the 900 chunks nearest by float cosine
          over the WHOLE corpus in the question's scope), collapsed by dense_hits' rule and the same _collapse

Both arms pass serving's INV-5 gate (unit_search.operative_units), keep 50 units, and are reranked as served on the
CPU profile (the int8 mMiniLM over the first 10 units at 800 characters; the rest keep their order); scored by
rerank_eval.case_metrics against the gold paths (lexical_benchmark.cases); paired bootstrap CI of float - binary.
Same space first: the run's Hamming window (topb_ids.npy, from its float vectors' sign bits) against an exact Hamming
scan of chunk.embedding with the same query bits, on every 10th question.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from lexical_benchmark import cases  # noqa: E402
from paired_bootstrap import paired  # noqa: E402
from rerank_eval import case_metrics  # noqa: E402

from nizam.inference.encoder import Encoder, to_bits  # noqa: E402
from nizam.inference.reranker import reranker as load_reranker  # noqa: E402
from nizam.retrieval.lexical import DENSE_HITS, _collapse, dense_units  # noqa: E402
from nizam.retrieval.rerank import RERANK_INPUT  # noqa: E402
from nizam.storage import unit_search  # noqa: E402
from nizam.storage.lexical import Filters  # noqa: E402
from nizam.storage.unit_search import Hit  # noqa: E402


def float_hits(s, chunk_ids, sims) -> list:
    """dense_hits' collapse over the float window: best chunk per version, best version per provision (active)"""
    keep = [(int(c), float(x)) for c, x in zip(chunk_ids, sims) if c >= 0]
    s.cur.execute("SELECT id, version_id FROM chunk WHERE id = ANY(%s)", ([c for c, _ in keep],))
    ver = dict(s.cur.fetchall())
    best: dict = {}
    for cid, sim in keep:
        v = ver.get(cid)
        if v is not None and (v not in best or sim > best[v]):
            best[v] = sim
    s.cur.execute("""SELECT v.id, p.id::text, p.path::text, p.instrument_id::text FROM provision_version v
                       JOIN provision p ON p.id = v.provision_id AND p.is_active WHERE v.id = ANY(%s::uuid[])""",
                  (list(best),))
    per: dict = {}
    for vid, pid, path, inst in s.cur.fetchall():
        if pid not in per or best[vid] > per[pid][0]:
            per[pid] = (best[vid], path, inst)
    return sorted((Hit(p, path, inst, sim) for p, (sim, path, inst) in per.items()),
                  key=lambda h: (-h.score, h.provision_id))[:DENSE_HITS]


def reranked_paths(s, rr, question: str, units: list, vids: dict) -> list[str]:
    chars, depth = RERANK_INPUT["cpu"]
    head, tail = units[:depth], units[depth:]
    if not head:
        return []
    texts = s.unit_passages([(u.unit_id, vids[u.unit_id]) for u in head], max_chars=chars)
    keep = [u for u in head if u.unit_id in texts]
    scores = rr.score(question, [texts[u.unit_id] for u in keep]) if keep else []
    order = [u for _, _, u in sorted(((-float(sc), i, u) for i, (u, sc) in enumerate(zip(keep, scores))),
                                     key=lambda x: (x[0], x[1]))]
    return [u.path for u in order] + [u.path for u in head if u not in keep] + [u.path for u in tail]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=Path)
    ap.add_argument("run", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / f"evals/results/adr1d-dev-{date.today().isoformat()}.json")
    a = ap.parse_args()
    os.environ["NIZAM_DENSE_PROFILE"] = "cpu"
    run = a.run / "out" / "bge-m3" if (a.run / "out").exists() else a.run / "bge-m3"
    q = np.load(run / "q.npy").astype(np.float32)
    tf_ids, tf_sims, tb_ids = np.load(run / "topf_ids.npy"), np.load(run / "topf_sims.npy"), np.load(run / "topb_ids.npy")
    dev = json.loads((a.export / "dev.json").read_text(encoding="utf-8"))
    manifest = json.loads((a.export / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    if metrics.get("revision") != manifest["revision"]:
        sys.exit(f"the run embedded {metrics.get('revision')}, the generation is {manifest['revision']}: not one space")
    enc = Encoder()                       # its EncoderInfo names the generation; its own vectors are not used here
    rr = load_reranker("cpu")
    gold = {d["caseId"]: (d, units) for d, units in cases("dev")}
    rows_b, rows_f, same = [], [], []
    for qi, c in enumerate(dev):
        if c["case"] not in gold:
            continue
        d, units = gold[c["case"]]
        gpaths = [u["path"] for u in units]
        f = Filters(as_of=date.fromisoformat(d["scope"]["asOf"]), jurisdictions=c["juris"])
        qv = q[qi] / np.linalg.norm(q[qi])
        bunits, _ = dense_units(qv, f, enc.info)
        with unit_search.session(f) as s:
            if qi % 10 == 0:              # the same space: the run's Hamming window = an exact scan of the stored bits
                s.cur.execute("""SELECT id FROM chunk WHERE jurisdiction = ANY(%s) AND embedding IS NOT NULL
                                  ORDER BY bit_count(embedding # %s::bit(1024)), id LIMIT %s""",
                              (c["juris"], to_bits(qv), int((tb_ids[qi] >= 0).sum())))
                stored = {r[0] for r in s.cur.fetchall()}
                kern = {int(x) for x in tb_ids[qi] if x >= 0}
                same.append(len(stored & kern) / max(1, len(stored | kern)))
            funits = [u for u, _ in _collapse(s, float_hits(s, tf_ids[qi], tf_sims[qi]))]
            vids = s.operative_units([u for u, _ in bunits] + funits)   # serving's INV-5 gate after fusion
            bu = [u for u, _ in bunits if u.unit_id in vids][:50]
            fu = [u for u in funits if u.unit_id in vids][:50]
            for us, out in ((bu, rows_b), (fu, rows_f)):
                dense_m = case_metrics([u.path for u in us], gpaths)
                rer = case_metrics(reranked_paths(s, rr, c["q"], us, vids), gpaths)
                out.append({"case": c["case"], "stratum": c["stratum"], "script": c["script"],
                            "dense_ndcg10": dense_m["ndcg10"], "dense_r50": dense_m["r50"], **rer})
    keys = ("ndcg10", "mrr10", "r10", "r50", "dense_ndcg10", "dense_r50")
    summ = {arm: {k: round(float(np.mean([r[k] for r in rs])), 4) for k in keys} | {"n": len(rs)}
            for arm, rs in (("binary", rows_b), ("float", rows_f))}
    ci = {k: paired(rows_b, rows_f, k) for k in keys}
    cost = summ["float"]["ndcg10"] - summ["binary"]["ndcg10"]
    verdict = ("binary stays: it costs at most 2 NDCG@10 points after reranking" if cost <= 0.02 else
               "binary costs more than 2 NDCG@10 points after reranking: ADR-1d's fallback applies")
    res = {"what": "ADR-1d after reranking, CPU generation (bge-m3), dev (D-110)", "rule": "D-005: cost <= 0.02",
           "summary": summ, "float_minus_binary": ci, "ndcg10_cost": round(cost, 4), "verdict": verdict,
           "same_space_window_jaccard": {"n": len(same), "mean": round(float(np.mean(same)), 4) if same else None,
                                         "min": round(float(min(same)), 4) if same else None},
           "rows": {"binary": rows_b, "float": rows_f}}
    a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
