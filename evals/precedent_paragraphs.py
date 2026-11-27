"""precedent_paragraphs.py: which paragraph of each found judgment to show (D-176). The judgment ORDER is precedent
search's, unchanged; only the paragraph presented for each judgment is chosen.

    python evals/precedent_paragraphs.py pool --profile cpu|gpu [--gpu-vectors B] --out DIR [--split test]
    python evals/precedent_paragraphs.py score-cpu --dir DIR       # the CPU reranker (int8 mMiniLM) on every pair
    python evals/precedent_paragraphs.py report --dir DIR [--gpu-scores scores-qwen3-8b.npy]

pool: per answerable dev case (case lookups too), precedent search (k=10) on the profile; for each of the first 10
judgments, the candidate paragraphs: the one search returned, the others any generator found, and the 6 nearest the
question by embedding within the judgment (body paragraphs, the profile's own sign bits). Writes DIR/pairs.jsonl
{pid, q, p} (question and paragraph text: what leaves for Kaggle; no gold) and DIR/pool.json (per case: judgments,
their candidates, search's choice, the nearest, the gold paragraphs of gold judgments; local only).
report: paragraph@10 over the gold judgments in the top 10 that have paragraph-level gold, for each chooser
(search, nearest, cpu reranker, 8B), the pool's ceiling, and paired bootstrap against search's choice.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

NEAREST = 6
K = 10


def pool_cmd(profile: str, gpu_vectors: Path | None, out: Path, split_name: str = "dev") -> int:
    import precedent_eval as PE
    from nizam.retrieval.precedent import search
    from nizam.storage.authority import Subordinate
    from nizam.storage.judgment_read import JudgmentRead
    split = json.loads(PE.SPLIT.read_text(encoding="utf-8"))
    chosen = [c for c in PE.cases() if c["familyId"] in split[split_name] and c["expectedOutcome"] != "abstain"]
    if profile == "gpu":
        from precomputed_encoder import PrecomputedEncoder
        enc = PrecomputedEncoder.from_bundle(gpu_vectors, vectors="q.npy", questions="questions.json")
    else:
        from nizam.inference.encoder import encoder
        enc = encoder()
    out.mkdir(parents=True, exist_ok=True)
    repo = JudgmentRead()
    repo.open()
    pairs, pid_of, cases = [], {}, {}
    try:
        docs = {u["judgmentDocumentId"] for c in chosen for u in c["precedentGold"]["necessaryJudgments"]}
        with repo.transaction() as conn:
            jid_of = PE._doc_to_judgment(conn, docs)
        for c in chosen:
            q = c["question"]["text"]
            as_of = date.fromisoformat(c["scope"]["asOf"])
            forum = Subordinate(c["scope"]["territory"]) if c["scope"].get("forum") else None
            r = search(q, as_of=as_of, forum=forum, k=K, repo=repo, encoder=enc)
            gold = {}
            for u in c["precedentGold"]["necessaryJudgments"]:
                j = jid_of.get(u["judgmentDocumentId"])
                if j and u.get("paragraphId"):
                    gold.setdefault(j, set()).add(u["paragraphId"])
            bits = enc.bits(q, 4096) if profile == "gpu" else enc.bits(q)
            js = []
            with repo.transaction() as conn:
                for h in r.hits[:K]:
                    if profile == "gpu":
                        near = conn.execute("""
                            SELECT c.paragraph_id::text AS id, min(e.bits <~> %s::bit(4096)) AS d
                              FROM judgment_chunk c JOIN judgment_chunk_embedding_gpu e ON e.chunk_id = c.id
                              JOIN judgment_paragraph p ON p.id = c.paragraph_id AND p.decided_on = c.decided_on
                             WHERE c.judgment_id = %s AND p.kind = 'body' GROUP BY 1 ORDER BY 2 LIMIT %s""",
                                            (bits, h.judgment_id, NEAREST)).fetchall()
                    else:
                        near = conn.execute("""
                            SELECT c.paragraph_id::text AS id, min(c.embedding <~> %s::bit(1024)) AS d
                              FROM judgment_chunk c
                              JOIN judgment_paragraph p ON p.id = c.paragraph_id AND p.decided_on = c.decided_on
                             WHERE c.judgment_id = %s AND p.kind = 'body' AND c.embedding IS NOT NULL
                             GROUP BY 1 ORDER BY 2 LIMIT %s""", (bits, h.judgment_id, NEAREST)).fetchall()
                    cand = list(dict.fromkeys([h.paragraph_id] + [n["id"] for n in near]))
                    texts = {t["id"]: t["text"] for t in conn.execute(
                        "SELECT id::text AS id, text FROM judgment_paragraph WHERE id = ANY(%s::uuid[])",
                        (cand,)).fetchall()}
                    cand = [p for p in cand if p in texts]
                    rows = []
                    for p in cand:
                        key = (q, texts[p][:2000])
                        if key not in pid_of:
                            pid_of[key] = len(pairs)
                            pairs.append({"pid": len(pairs), "q": q, "p": texts[p][:2000]})
                        rows.append({"paragraph": p, "pid": pid_of[key]})
                    js.append({"judgment": h.judgment_id, "search": h.paragraph_id,
                               "nearest": near[0]["id"] if near else h.paragraph_id, "candidates": rows,
                               "gold": sorted(gold.get(h.judgment_id, []))})
            cases[c["caseId"]] = {"stratum": c["stratum"], "judgments": js}
            print(f"  {c['caseId']}: {sum(len(j['candidates']) for j in js)} candidates, {len(pairs)} pairs", flush=True)
    finally:
        repo.close()
    with open(out / "pairs.jsonl", "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    (out / "pool.json").write_text(json.dumps({"profile": profile, "built": date.today().isoformat(), "cases": cases},
                                              indent=0), encoding="utf-8")
    print(f"{len(cases)} cases, {len(pairs)} pairs -> {out}")
    return 0


def score_cpu_cmd(d: Path) -> int:
    from nizam.inference.reranker import reranker
    rr = reranker("cpu")
    pairs = [json.loads(line) for line in open(d / "pairs.jsonl", encoding="utf-8")]
    by_q = {}
    for p in pairs:
        by_q.setdefault(p["q"], []).append(p)
    s = np.zeros(len(pairs), dtype=np.float32)
    for q, ps in by_q.items():
        for p, v in zip(ps, rr.score(q, [x["p"][:800] for x in ps])):     # the CPU profile's 800 characters
            s[p["pid"]] = v
    np.save(d / "scores-cpu.npy", s)
    print(f"{len(pairs)} pairs scored by {rr.info.model} -> {d / 'scores-cpu.npy'}")
    return 0


def report_cmd(d: Path, gpu_scores: Path | None) -> int:
    pool = json.loads((d / "pool.json").read_text(encoding="utf-8"))["cases"]
    scores = {"cpu reranker": np.load(d / "scores-cpu.npy")} if (d / "scores-cpu.npy").exists() else {}
    if gpu_scores and gpu_scores.exists():
        scores["8B reranker"] = np.load(gpu_scores)
    choosers = ["search", "nearest"] + list(scores)
    rows = {k: [] for k in choosers + ["pool ceiling"]}
    for cid, c in pool.items():
        for j in c["judgments"]:
            if not j["gold"]:
                continue
            gold = set(j["gold"])
            rows["search"].append(float(j["search"] in gold))
            rows["nearest"].append(float(j["nearest"] in gold))
            rows["pool ceiling"].append(float(any(x["paragraph"] in gold for x in j["candidates"])))
            for name, s in scores.items():
                best = max(j["candidates"], key=lambda x: s[x["pid"]])
                rows[name].append(float(best["paragraph"] in gold))
    n = len(rows["search"])
    random.seed(0)

    def ci(x):
        m = sum(x) / len(x)
        b = sorted(sum(x[random.randrange(len(x))] for _ in x) / len(x) for _ in range(5000))
        return f"{m*100:+.1f} [{b[125]*100:+.1f}, {b[4875]*100:+.1f}]"
    print(f"gold judgments in the top 10 with paragraph gold: {n}")
    for k, v in rows.items():
        line = f"  {k:14} paragraph right {np.mean(v):.3f}"
        if k not in ("search", "pool ceiling"):
            line += f"   vs search {ci([a - b for a, b in zip(v, rows['search'])])}"
        print(line)
    json.dump({k: float(np.mean(v)) for k, v in rows.items()} | {"n": n}, open(d / "report.json", "w"), indent=1)
    return 0


def budget_cmd(d: Path, gpu_scores: Path) -> int:
    """the 8B chooser at a scoring budget: only the first J judgments get a choice, from their first P candidates
    (search's paragraph, then the nearest by embedding); later judgments keep search's paragraph. Reports
    paragraph@10 and the mean pairs scored per question (the GPU cost), per (J, P)."""
    pool = json.loads((d / "pool.json").read_text(encoding="utf-8"))["cases"]
    s = np.load(gpu_scores)
    out = []
    for J in (2, 3, 5, 10):
        for P in (2, 3, 4, 7):
            right, base, pairs = [], [], []
            for c in pool.values():
                pairs.append(sum(min(P, len(j["candidates"])) for j in c["judgments"][:J]))
                for rank, j in enumerate(c["judgments"]):
                    if not j["gold"]:
                        continue
                    gold = set(j["gold"])
                    pick = j["search"]
                    if rank < J:
                        pick = max(j["candidates"][:P], key=lambda x: s[x["pid"]])["paragraph"]
                    right.append(float(pick in gold)); base.append(float(j["search"] in gold))
            random.seed(0)
            dif = [a - b for a, b in zip(right, base)]
            b = sorted(sum(dif[random.randrange(len(dif))] for _ in dif) / len(dif) for _ in range(5000))
            out.append(dict(J=J, P=P, paragraph_right=round(float(np.mean(right)), 3),
                            vs_search=round(float(np.mean(dif)) * 100, 1), ci=[round(b[125] * 100, 1), round(b[4875] * 100, 1)],
                            pairs_per_question=round(float(np.mean(pairs)), 1)))
            print(f"  J={J:2} P={P}  right {np.mean(right):.3f}  vs search {np.mean(dif)*100:+.1f} "
                  f"[{b[125]*100:+.1f}, {b[4875]*100:+.1f}]  pairs/question {np.mean(pairs):.1f}")
    json.dump(out, open(d / "budget.json", "w"), indent=1)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pool")
    p.add_argument("--profile", choices=["cpu", "gpu"], required=True)
    p.add_argument("--gpu-vectors", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--split", choices=["dev", "test"], default="dev", help="test: read ONCE, after the dev choice")
    s = sub.add_parser("score-cpu")
    s.add_argument("--dir", type=Path, required=True)
    r = sub.add_parser("report")
    r.add_argument("--dir", type=Path, required=True)
    r.add_argument("--gpu-scores", type=Path)
    bu = sub.add_parser("budget")
    bu.add_argument("--dir", type=Path, required=True)
    bu.add_argument("--gpu-scores", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "pool":
        return pool_cmd(a.profile, a.gpu_vectors, a.out, a.split)
    if a.cmd == "budget":
        return budget_cmd(a.dir, a.gpu_scores)
    if a.cmd == "score-cpu":
        return score_cpu_cmd(a.dir)
    return report_cmd(a.dir, a.gpu_scores)


if __name__ == "__main__":
    raise SystemExit(main())
