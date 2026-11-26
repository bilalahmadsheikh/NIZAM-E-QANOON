"""Precedent search against the precedent stratum of the golden set (D-133; docs/10 §4, §6; PRECEDENT-MODEL §6).

    python evals/precedent_eval.py split                 # writes evals/golden/split-precedent-v1.json (idempotent)
    python evals/precedent_eval.py run --split dev       # dev: for choosing and tuning
    python evals/precedent_eval.py run --split test      # test: read once, to report a decision made on dev

The split assigns whole families (docs/10 §4: variants, dates and translations of one question stay together):
families are ordered by sha256(familyId) within two groups (answerable, unanswerable) and the first 60% are dev.

What is measured, per answerable case, over `nizam.retrieval.precedent.search(question, as_of, forum)`:
  * hit@10 and MRR@10: a necessary judgment among the first ten judgments, and the reciprocal rank of the first;
  * recall@10 and recall@50 over the necessary judgments (a judgment counts once, however many gold paragraphs);
  * paragraph@10: of the necessary judgments found in the top ten, the share whose returned paragraph is a gold
    paragraph (paragraph-level gold only);
  * leaks: a must-not-serve judgment returned, or any hit decided after as_of (INV-5; both must be 0);
  * authority: for each gold judgment found, the returned binding status against the author's reading (Arts. 189,
    201); `not_recorded` is counted apart, since it is a refusal, not a wrong answer.
Unanswerable cases: search is discovery and passes no gate (INV-2 governs answers, not discovery), so it is not
expected to abstain. What it returns is recorded: before_coverage must return nothing; court_not_held returns other
courts' judgments, which a precedent gate (not built, docs/04 §6) must decline to present as that court's view.

The gold is incomplete by nature (many judgments state a settled principle), so no precision figure is reported.
The set is a draft until its legal review (A1/A2): figures from it are provisional and say so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GOLDEN = ROOT / "evals/golden"
SPLIT = GOLDEN / "split-precedent-v1.json"
DEV_SHARE = 0.6


def cases() -> list[dict]:
    out = []
    for p in sorted(GOLDEN.glob("golden-pk-v1-precedent*.draft.jsonl")):
        out += [json.loads(line) for line in p.open(encoding="utf-8") if line.strip()]
    return out


def make_split() -> int:
    fams = defaultdict(set)
    for c in cases():
        fams["unanswerable" if c["expectedOutcome"] == "abstain" else "answerable"].add(c["familyId"])
    prior = json.loads(SPLIT.read_text(encoding="utf-8")) if SPLIT.exists() else {"dev": [], "test": []}
    fixed = {f: "dev" for f in prior["dev"]} | {f: "test" for f in prior["test"]}
    split = {"dev": [], "test": []}
    for group, ids in sorted(fams.items()):
        # a family already placed keeps its side; new ones are placed by the same rule AMONG THEMSELVES (D-168), so
        # adding a set never moves an old family and the new families split 60/40 however they interleave
        new = sorted((f for f in ids if f not in fixed), key=lambda f: hashlib.sha256(f.encode()).hexdigest())
        n_dev = round(len(new) * DEV_SHARE)
        for f in ids:
            split[fixed[f] if f in fixed else ("dev" if new.index(f) < n_dev else "test")].append(f)
    split = {k: sorted(v) for k, v in split.items()}
    rule = prior.get("rule") or "families by sha256(familyId) within answerable/unanswerable, first 60% dev (D-133)"
    if "D-168" not in rule:
        rule += ("; families added later keep set 1's places and are split by the same rule among themselves, first "
                 "60% dev (D-168)")
    SPLIT.write_text(json.dumps({"rule": rule, **split}, indent=1), encoding="utf-8")
    n = defaultdict(int)
    for c in cases():
        n["dev" if c["familyId"] in split["dev"] else "test"] += 1
    print(f"families dev {len(split['dev'])} test {len(split['test'])}; cases dev {n['dev']} test {n['test']}")
    return 0


def _doc_to_judgment(conn, docs: set[int]) -> dict[int, str]:
    # the gold names the file read at build; a re-read gives the same bytes a new document (precedent_common)
    rows = conn.execute("""SELECT g.id AS document_id, j.id::text AS id
                             FROM judgment_document g
                             JOIN judgment_document d ON d.sha256 = g.sha256
                             JOIN v_release_judgment j ON j.document_id = d.id
                            WHERE g.id = ANY(%s)""", (list(docs),)).fetchall()
    return {r["document_id"]: r["id"] for r in rows}


def run(split_name: str, out: Path | None, gpu_vectors: Path | None = None) -> int:
    from nizam.inference.encoder import encoder
    from nizam.retrieval.precedent import search
    from nizam.storage.authority import Subordinate
    from nizam.storage.judgment_read import JudgmentRead
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    chosen = [c for c in cases() if split_name == "all" or c["familyId"] in split[split_name]]
    repo = JudgmentRead()
    repo.open()
    try:
        if gpu_vectors:
            # the GPU generation (D-158), measured here by replaying the questions' 8B vectors made on Kaggle
            # (q8push): the kernel's q.npy and questions.json, with the GPU encoder bundle's encoder.json
            from precomputed_encoder import PrecomputedEncoder
            enc = PrecomputedEncoder.from_bundle(gpu_vectors, vectors="q.npy", questions="questions.json")
        else:
            enc = encoder()
    except Exception as exc:                                    # noqa: BLE001  no encoder bundle: lexical only
        print(f"encoder unavailable ({type(exc).__name__}); dense generator off"); enc = None
    docs = {u["judgmentDocumentId"] for c in chosen for k in ("necessaryJudgments", "relevantJudgments",
                                                              "hardNegatives") for u in c["precedentGold"][k]}
    with repo.transaction() as conn:
        jid_of = _doc_to_judgment(conn, docs)
    doc_of = {j: d for d, j in jid_of.items()}
    rows, ms = [], []
    try:
        for c in chosen:
            as_of = date.fromisoformat(c["scope"]["asOf"])
            terr = c["scope"]["territory"]
            forum = Subordinate(terr) if c["scope"].get("forum") else None
            t = time.time()
            r = search(c["question"]["text"], as_of=as_of, forum=forum, k=50, repo=repo, encoder=enc)
            ms.append((time.time() - t) * 1000)
            ranked = [h.judgment_id for h in r.hits]
            row = dict(caseId=c["caseId"], stratum=c["stratum"], familyId=c["familyId"],
                       outcome=c["expectedOutcome"], mode=r.mode, hits=len(r.hits),
                       leaks_after_as_of=sum(1 for h in r.hits if h.decided_on and h.decided_on > as_of),
                       trace=r.trace)
            neg = {jid_of.get(u["judgmentDocumentId"]) for u in c["precedentGold"]["hardNegatives"]}
            row["leaks_must_not_serve"] = sum(1 for j in ranked if j in neg)
            row["coverage_gap"] = r.coverage_gap
            row["cases_named"] = r.cases_named
            if c["expectedOutcome"] == "abstain":
                row["abstention_code"] = c["abstention"]["code"]
                row["courts_returned"] = sorted({h.court for h in r.hits})
                # declined: nothing shown as a court's view it does not hold, or nothing before coverage (D-137)
                row["declined"] = not r.hits
                rows.append(row)
                continue
            gold = defaultdict(set)              # judgment id -> gold paragraph ids (empty: whole judgment)
            courts = {}
            expected = {}
            for u in c["precedentGold"]["necessaryJudgments"]:
                j = jid_of.get(u["judgmentDocumentId"])
                gold[j]
                if u["paragraphId"]:
                    gold[j].add(u["paragraphId"])
                courts[j] = u["court"]
                expected[j] = u.get("expectedAuthority")
            relevant = {jid_of.get(u["judgmentDocumentId"]) for u in c["precedentGold"]["relevantJudgments"]}
            top10 = ranked[:10]
            found10 = [j for j in top10 if j in gold]
            first = next((i for i, j in enumerate(top10, 1) if j in gold), None)
            para = [(h.paragraph_id in gold[h.judgment_id]) for h in r.hits[:10]
                    if h.judgment_id in gold and gold[h.judgment_id]]
            auth = []
            for h in r.hits:
                if h.judgment_id in gold and expected.get(h.judgment_id):
                    got = (h.authority or {}).get("status")
                    auth.append("not_recorded" if got == "not_recorded" else
                                ("agree" if got == expected[h.judgment_id] else "disagree"))
            row.update(hit10=bool(found10), rr10=1.0 / first if first else 0.0,
                       recall10=len(found10) / len(gold), recall50=len([j for j in ranked if j in gold]) / len(gold),
                       paragraph10=(sum(para) / len(para)) if para else None,
                       any_gold_or_relevant10=any(j in gold or j in relevant for j in top10),
                       authority=auth, gold_courts=sorted(set(courts.values())),
                       first_rank=first,
                       gold_ranks={f"{courts[j]} doc {doc_of.get(j)}": (ranked.index(j) + 1 if j in ranked else None)
                                   for j in gold})
            rows.append(row)
    finally:
        repo.close()
    report = summarise(rows, ms, split_name)
    out = out or ROOT / f"evals/results/precedent-eval-{split_name}.json"
    out.write_text(json.dumps({"summary": report, "cases": rows}, indent=1, default=str), encoding="utf-8")
    print(json.dumps(report, indent=1))
    print(f"-> {out}")
    return 0


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def summarise(rows: list[dict], ms: list[float], split_name: str) -> dict:
    ans = [r for r in rows if r["outcome"] != "abstain"]
    by = defaultdict(list)
    for r in ans:
        by[r["stratum"]].append(r)
    auth = [a for r in ans for a in r["authority"]]
    un = [r for r in rows if r["outcome"] == "abstain"]
    return {
        "split": split_name, "status": "provisional: draft gold, not yet legally reviewed (A1/A2)",
        "cases": len(rows), "answerable": len(ans), "modes": sorted({r["mode"] for r in rows}),
        "hit@10": _mean([float(r["hit10"]) for r in ans]), "MRR@10": _mean([r["rr10"] for r in ans]),
        "recall@10": _mean([r["recall10"] for r in ans]), "recall@50": _mean([r["recall50"] for r in ans]),
        "paragraph@10": _mean([r["paragraph10"] for r in ans]),
        "gold_or_relevant@10": _mean([float(r["any_gold_or_relevant10"]) for r in ans]),
        "by_stratum": {s: {"n": len(v), "hit@10": _mean([float(r["hit10"]) for r in v]),
                           "MRR@10": _mean([r["rr10"] for r in v]), "recall@50": _mean([r["recall50"] for r in v])}
                       for s, v in sorted(by.items())},
        "leaks": {"after_as_of": sum(r["leaks_after_as_of"] for r in rows),
                  "must_not_serve": sum(r["leaks_must_not_serve"] for r in rows)},
        "authority": {k: auth.count(k) for k in ("agree", "disagree", "not_recorded")},
        "unanswerable": [{"caseId": r["caseId"], "code": r["abstention_code"], "hits": r["hits"],
                          "courts_returned": r["courts_returned"], "declined": r.get("declined"),
                          "coverage_gap": (r.get("coverage_gap") or {}).get("court")} for r in un],
        "declined": f"{sum(1 for r in un if r.get('declined'))} of {len(un)}",
        "latency_ms": {"p50": round(statistics.median(ms)) if ms else None,
                       "p95": round(sorted(ms)[max(0, int(len(ms) * 0.95) - 1)]) if ms else None},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("split")
    r = sub.add_parser("run")
    r.add_argument("--split", choices=["dev", "test", "all"], required=True)
    r.add_argument("--out", type=Path)
    r.add_argument("--gpu-vectors", type=Path, help="a directory of the questions' 8B vectors (q.npy, questions.json, "
                                                    "encoder.json): search the GPU generation's space (D-158)")
    a = ap.parse_args()
    return make_split() if a.cmd == "split" else run(a.split, a.out, a.gpu_vectors)


if __name__ == "__main__":
    sys.exit(main())
