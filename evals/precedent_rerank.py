"""Precedent reranking (D-167): the candidate judgments precedent search returns, reordered by a cross-encoder.

    python evals/precedent_rerank.py slates --split dev --out DIR [--gpu-vectors BUNDLE ...] [--cpu]
    python evals/precedent_rerank.py score  --split dev --slates DIR --scores SCORES.npy --model NAME [--out JSON]

slates: for every case of the split, nizam.retrieval.precedent.search(question, as_of, forum, k=50) -- the served
search, with the question vectors of each named profile (an 8B bundle replayed, or the CPU encoder) -- and, for each
judgment returned, the paragraph it was found by. Writes DIR/pairs.jsonl {"pid", "q", "p"} (questions and judgment
paragraphs only, no gold: the one file that leaves this machine, for `kg.sh rrpush`) and DIR/slates.json (local).

score: each profile's slate reordered by the reranker's scores (by pid), two ways -- the reranker's order alone, and
its rank fused with the search's own rank (RRF, k = 60) -- and measured with precedent_eval's definitions (hit@10,
MRR@10, recall@10/50, paragraph@10, leaks), beside the search's own order. Writes a JSON summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import precedent_eval as PE  # noqa: E402

K = 50
PASSAGE_CHARS = 1800


def _chosen(split_name):
    split = json.loads(PE.SPLIT.read_text(encoding="utf-8"))
    return [c for c in PE.cases() if c["familyId"] in split[split_name] and c["expectedOutcome"] != "abstain"]


def slates(split_name: str, out: Path, bundles: list[Path], cpu: bool) -> int:
    from nizam.retrieval.precedent import search
    from nizam.storage.authority import Subordinate
    from nizam.storage.judgment_read import JudgmentRead
    from precomputed_encoder import PrecomputedEncoder
    profiles = {b.name: PrecomputedEncoder.from_bundle(b, vectors="q.npy", questions="questions.json") for b in bundles}
    if cpu:
        from nizam.inference.encoder import encoder
        profiles["cpu"] = encoder()
    out.mkdir(parents=True, exist_ok=True)
    repo = JudgmentRead()
    repo.open()
    pairs, pid_of, result = [], {}, {}
    try:
        for c in _chosen(split_name):
            q = c["question"]["text"]
            as_of = date.fromisoformat(c["scope"]["asOf"])
            forum = Subordinate(c["scope"]["territory"]) if c["scope"].get("forum") else None
            per = {}
            for name, enc in profiles.items():
                r = search(q, as_of=as_of, forum=forum, k=K, repo=repo, encoder=enc)
                rows = []
                for h in r.hits:
                    key = (q, h.paragraph_id)
                    if key not in pid_of:
                        pid_of[key] = len(pairs)
                        pairs.append({"pid": len(pairs), "q": q,
                                      "p": f"{h.court}. {' '.join((h.text or '').split())[:PASSAGE_CHARS]}"})
                    rows.append({"pid": pid_of[key], "judgment_id": h.judgment_id, "paragraph_id": h.paragraph_id,
                                 "decided_on": str(h.decided_on) if h.decided_on else None})
                per[name] = {"mode": r.mode, "trace_dense": r.trace.get("dense_space"), "hits": rows}
            result[c["caseId"]] = per
    finally:
        repo.close()
    with open(out / "pairs.jsonl", "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    (out / "slates.json").write_text(json.dumps({"split": split_name, "k": K, "profiles": list(profiles),
                                                 "cases": result}, indent=0), encoding="utf-8")
    print(f"{len(result)} cases, {len(pairs)} distinct pairs, profiles {list(profiles)} -> {out}")
    return 0


def _metrics(c, order, jid_of):
    gold = defaultdict(set)
    for u in c["precedentGold"]["necessaryJudgments"]:
        j = jid_of.get(u["judgmentDocumentId"])
        gold[j]
        if u["paragraphId"]:
            gold[j].add(u["paragraphId"])
    neg = {jid_of.get(u["judgmentDocumentId"]) for u in c["precedentGold"]["hardNegatives"]}
    ranked = [h["judgment_id"] for h in order]
    top10 = ranked[:10]
    first = next((i for i, j in enumerate(top10, 1) if j in gold), None)
    para = [(h["paragraph_id"] in gold[h["judgment_id"]]) for h in order[:10]
            if h["judgment_id"] in gold and gold[h["judgment_id"]]]
    as_of = c["scope"]["asOf"]
    return dict(hit10=float(bool(first)), rr10=1.0 / first if first else 0.0,
                recall10=len([j for j in top10 if j in gold]) / len(gold),
                recall50=len([j for j in ranked if j in gold]) / len(gold),
                paragraph10=(sum(para) / len(para)) if para else None,
                leaks=sum(1 for j in ranked if j in neg) + sum(1 for h in order if h["decided_on"]
                                                                and h["decided_on"] > as_of))


def score(split_name, slates_dir: Path, scores_path: Path, model: str, out: Path | None) -> int:
    import numpy as np
    from nizam.storage.judgment_read import JudgmentRead
    s = json.loads((slates_dir / "slates.json").read_text(encoding="utf-8"))
    sc = np.load(scores_path)
    chosen = {c["caseId"]: c for c in _chosen(split_name)}
    docs = {u["judgmentDocumentId"] for c in chosen.values() for k in ("necessaryJudgments", "hardNegatives")
            for u in c["precedentGold"][k]}
    repo = JudgmentRead()
    repo.open()
    try:
        with repo.transaction() as conn:
            jid_of = PE._doc_to_judgment(conn, docs)
    finally:
        repo.close()
    jid_of = {k: str(v) for k, v in jid_of.items()}
    report = {"model": model, "split": split_name, "status": "provisional: draft gold (A1/A2)"}
    for prof in s["profiles"]:
        rows = defaultdict(list)
        for cid, per in s["cases"].items():
            if cid not in chosen:
                continue
            hits = per[prof]["hits"]
            base = hits
            rer = sorted(hits, key=lambda h: -float(sc[h["pid"]]))
            rank_b = {h["pid"]: i for i, h in enumerate(base, 1)}
            rank_r = {h["pid"]: i for i, h in enumerate(rer, 1)}
            fused = sorted(hits, key=lambda h: -(1 / (60 + rank_b[h["pid"]]) + 1 / (60 + rank_r[h["pid"]])))
            for name, order in (("search", base), ("reranked", rer), ("rrf_search_rerank", fused)):
                rows[name].append(_metrics(chosen[cid], order, jid_of))
        report[prof] = {name: {m: round(sum(r[m] for r in v if r[m] is not None) /
                                         max(1, sum(1 for r in v if r[m] is not None)), 3)
                               for m in ("hit10", "rr10", "recall10", "recall50", "paragraph10")} |
                        {"leaks": sum(r["leaks"] for r in v), "cases": len(v), "per_case": v}
                        for name, v in rows.items()}
    out = out or ROOT / f"evals/results/precedent-rerank-{split_name}-{model}.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    for prof in s["profiles"]:
        for name, v in report[prof].items():
            print(prof, name, {k: v[k] for k in v if k != "per_case"})
    print("->", out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("slates")
    a.add_argument("--split", choices=["dev", "test"], required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--gpu-vectors", type=Path, action="append", default=[])
    a.add_argument("--cpu", action="store_true")
    b = sub.add_parser("score")
    b.add_argument("--split", choices=["dev", "test"], required=True)
    b.add_argument("--slates", type=Path, required=True)
    b.add_argument("--scores", type=Path, required=True)
    b.add_argument("--model", required=True)
    b.add_argument("--out", type=Path)
    x = ap.parse_args()
    if x.cmd == "slates":
        return slates(x.split, x.out, x.gpu_vectors, x.cpu)
    return score(x.split, x.slates, x.scores, x.model, x.out)


if __name__ == "__main__":
    sys.exit(main())
