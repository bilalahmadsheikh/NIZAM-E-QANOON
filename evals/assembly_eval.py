"""Evaluate L3 evidence assembly (docs/04 §7; D-107) under evals/results/assembly-rule-2026-11-20.json.

    .venv/bin/python evals/assembly_eval.py --split dev --sizes      # unconstrained packet sizes only (the budget)
    .venv/bin/python evals/assembly_eval.py --split dev               # M1-M3, M5-M7, and the M4 sample
    .venv/bin/python evals/assembly_eval.py --split test              # once, after the code and budget are frozen

For each case that expects an answer and each mode (gpu, cpu) it takes the gate's bundle as served (the features
file) and the gate harness's Filters, then measures three arms: `passages` (what the reranker read), `units` (each
bundle unit whole) and `assembled` (the full assembly under the budget). Gold is read here only, never by the code
under test.

PROVISIONAL: golden sets 1-10 are drafts (D-095, D-104); M4 is author-checked.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import re
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.retrieval import gate as G  # noqa: E402
from nizam.retrieval.assembly import BUDGET_CHARS, assemble  # noqa: E402
from nizam.retrieval.query import parse  # noqa: E402
from nizam.storage import evidence_read as ER  # noqa: E402
from nizam.storage import unit_search  # noqa: E402
from nizam.storage.lexical import Filters  # noqa: E402

sys.path.insert(0, str(ROOT / "evals"))
from gate_eval import decide, rate  # noqa: E402

FEATURES = "evals/results/gate-features-{split}-*.json"     # the newest: bundles follow the corpus (D-110)
MODES = ("gpu", "cpu")


def cases(split: str):
    keep = set(json.loads((ROOT / "evals/golden/split-v1.json").read_text(encoding="utf-8"))[split])
    for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            if d["caseId"] in keep:
                yield d


def fold(s: str) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", (s or "").lower()).split())


def filters_of(d) -> Filters:
    j = d["scope"]["jurisdiction"]
    juris = ("fed",) if j in ("fed", "foreign") else (j, "fed")
    return Filters(as_of=date.fromisoformat(d["scope"]["asOf"]), jurisdictions=juris)


def bundle_of(feat_mode) -> tuple:
    return tuple(G.BundleItem(x["unit"], x["version"], x["instrument"], x["rank"], x.get("rerank"), x["fused"],
                              bool(x.get("cited"))) for x in (feat_mode.get("bundle") or [])[:G.BUNDLE])


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--sizes", action="store_true", help="unconstrained packet sizes only (the budget procedure)")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--features", type=Path, help="a gate-features file (default: the split's newest)")
    a = ap.parse_args()
    fpath = a.features or Path(sorted(glob.glob(str(ROOT / FEATURES.format(split=a.split))))[-1])
    print(f"bundles from {fpath.name}")
    feats = json.loads(fpath.read_text(encoding="utf-8"))["cases"]
    cal = G.calibration()
    modes = a.modes.split(",")
    rows = []
    additions = []
    n = 0
    for d in cases(a.split):
        if d["expectedOutcome"] not in ("answer", "conditional"):
            continue
        cid = d["caseId"]
        fc = feats.get(cid)
        if fc is None:
            continue
        n += 1
        if a.limit and n > a.limit:
            break
        f = filters_of(d)
        spec = parse(d["question"]["text"])
        veto = G.pre_veto(spec, f)
        fc = {**fc, "veto": veto.__dict__ if veto else None}
        for mode in modes:
            fm = fc["modes"].get(mode) or {}
            items = bundle_of(fm)
            if not items:
                continue
            passed = decide(fc, mode, cal)["decision"] == "pass"
            ctx = G.GroundingContext(spec, f, items, 1.0, 0.5, {"decision": "pass"}, {})
            if a.sizes:
                out = assemble(ctx, budget=10 ** 9, max_units=10 ** 6)
                rows.append({"case": cid, "mode": mode, "chars": out.coverage["used_chars"] if out else 0})
                continue
            out = assemble(ctx)
            gold_nec = [u["provisionId"] for u in d["retrievalGold"].get("necessaryUnits") or []]
            gold_rel = [u["provisionId"] for u in d["retrievalGold"].get("relevantUnits") or []]
            checks = [fold(c) for c in d.get("textChecks") or [] if fold(c)]
            # the passages and units arms
            with unit_search.session(f) as s:
                passages = s.unit_passages([(b.unit_id, b.version_id) for b in items])
            with ER.session(f) as s:
                whole = s.units([b.unit_id for b in items])
            unit_nodes = {uid: {n.provision_id for n in u.nodes} | {uid} for uid, u in whole.items()}
            p_ids = {b.unit_id for b in items}
            arm_ids = {
                "passages": set().union(*(unit_nodes.get(u, {u}) for u in p_ids)),
                "units": set().union(*(unit_nodes.get(u, {u}) for u in p_ids)),
                "assembled": set(),
            }
            arm_text = {
                "passages": fold(" ".join(passages.values())),
                "units": fold(" ".join(n.text for u in whole.values() for n in u.nodes)),
                "assembled": "",
            }
            ev = out.evidence if out else ()
            for it in ev:
                arm_ids["assembled"] |= {it.unit_id, it.provision_id} | {nd[0] for nd in it.nodes}
            # M3 reads the operative words; the rendered text adds labels between nodes
            with ER.session(f) as s:
                vids = [nd[1] for it in ev for nd in it.nodes]
                live = s._operative(vids)
            arm_text["assembled"] = fold(" ".join(live[v]["body"] for v in vids if v in live))
            row = {"case": cid, "mode": mode, "passed": passed, "stratum": d["stratum"],
                   "script": d["question"].get("script", "latin")}
            for arm in ("passages", "units", "assembled"):
                row[arm] = {"nec": sum(1 for g in gold_nec if g in arm_ids[arm]), "nec_n": len(gold_nec),
                            "rel": sum(1 for g in gold_rel if g in arm_ids[arm]), "rel_n": len(gold_rel),
                            "checks": bool(checks) and all(c in arm_text[arm] for c in checks),
                            "has_checks": bool(checks)}
            row["lost_necessary"] = [g for g in gold_nec if g in arm_ids["units"] and g not in arm_ids["assembled"]]
            row["added_necessary"] = [g for g in gold_nec if g in arm_ids["assembled"] and g not in arm_ids["units"]]
            row["added_relevant"] = [g for g in gold_rel if g in arm_ids["assembled"] and g not in arm_ids["units"]]
            row["inv5_missing"] = sorted(set(vids) - set(live))
            cov = out.coverage if out else {}
            row.update(chars=cov.get("used_chars"), items=len(ev), n_units=cov.get("units"),
                       n_definitions=cov.get("definitions"), over_budget=cov.get("over_budget"),
                       ms=cov.get("assembly_ms"), timings=cov.get("timings_ms"),
                       roles={r: sum(1 for it in ev if it.role == r) for r in
                              ("governing", "qualification", "definition", "reference", "schedule")},
                       omitted=len(cov.get("omitted") or []), budget_omitted=sum(
                           1 for o in cov.get("omitted") or [] if o["reason"] == "budget"),
                       refs=cov.get("references"),
                       conflicts=[dict(c) for c in (out.conflicts if out else ())],   # D-110: prevails/over/kind/said_by
                       sub_questions=cov.get("sub_questions"))                                       # D-110
            rows.append(row)
            if mode == "gpu":
                gov = {it.unit_id: it for it in ev if it.role == "governing"}
                for it in ev:
                    if it.role != "governing":
                        additions.append({"case": cid, "question": d["question"]["text"], "role": it.role,
                                          "citation": it.citation, "reason": it.inclusion_reason,
                                          "text": it.text[:1500], "provision": it.provision_id,
                                          "governing": [g.citation for g in gov.values()][:3]})
        if n % 25 == 0:
            print(f"  {n} cases", flush=True)

    out_path = a.out or ROOT / f"evals/results/assembly-{a.split}{'-sizes' if a.sizes else ''}-2026-11-20.json"
    if a.sizes:
        summary = {}
        for mode in modes:
            xs = [r["chars"] for r in rows if r["mode"] == mode]
            summary[mode] = {"cases": len(xs), "p50": pct(xs, .5), "p90": pct(xs, .9), "max": max(xs) if xs else None}
            print(mode, summary[mode])
        out_path.write_text(json.dumps({"split": a.split, "what": "unconstrained packet sizes (characters)",
                                        "summary": summary, "rows": rows}, indent=1), encoding="utf-8")
        return 0

    summary = {}
    for mode in modes:
        for subset in ("all", "passed"):
            rs = [r for r in rows if r["mode"] == mode and (subset == "all" or r["passed"])]
            if not rs:
                continue
            s = {"cases": len(rs)}
            for arm in ("passages", "units", "assembled"):
                nec = sum(r[arm]["nec"] for r in rs)
                nec_n = sum(r[arm]["nec_n"] for r in rs)
                rel = sum(r[arm]["rel"] for r in rs)
                rel_n = sum(r[arm]["rel_n"] for r in rs)
                ck = [r for r in rs if r[arm]["has_checks"]]
                s[arm] = {"M1_necessary": rate(nec, nec_n), "M2_relevant": rate(rel, rel_n),
                          "M3_text_checks": rate(sum(1 for r in ck if r[arm]["checks"]), len(ck))}
            s["lost_necessary"] = [(r["case"], r["lost_necessary"]) for r in rs if r["lost_necessary"]]
            s["added_necessary"] = sum(len(r["added_necessary"]) for r in rs)
            s["added_relevant"] = sum(len(r["added_relevant"]) for r in rs)
            s["M5_inv5_violations"] = sum(len(r["inv5_missing"]) for r in rs)
            chars = [r["chars"] for r in rs if r["chars"] is not None]
            ms = [r["ms"] for r in rs if r["ms"] is not None][1:]          # warm: the first call pays the connect
            s["M6_size"] = {"chars_p50": pct(chars, .5), "chars_p90": pct(chars, .9), "chars_max": max(chars),
                            "items_mean": round(statistics.mean(r["items"] for r in rs), 2),
                            "units_mean": round(statistics.mean(r["n_units"] or 0 for r in rs), 2),
                            "definitions_mean": round(statistics.mean(r["n_definitions"] or 0 for r in rs), 2),
                            "roles": {k: sum(r["roles"][k] for r in rs) for k in rs[0]["roles"]},
                            "over_budget": sum(1 for r in rs if r["over_budget"]),
                            "budget_omitted": sum(r["budget_omitted"] for r in rs),
                            "conflicts": sum(len(r.get("conflicts") or []) for r in rs),
                            "cases_with_conflicts": sum(1 for r in rs if r.get("conflicts")),
                            "cases_split": sum(1 for r in rs if r.get("sub_questions")),
                            "sub_questions_without_lexical_support": sum(
                                1 for r in rs for s in (r.get("sub_questions") or []) if s["lexical_support"] == [])}
            s["M7_latency_ms"] = {"p50": pct(ms, .5), "p95": pct(ms, .95)}
            summary[f"{mode}:{subset}"] = s
            a1 = s["assembled"]
            print(f"{mode:3s} {subset:6s} n={len(rs):3d}  nec {s['passages']['M1_necessary']['rate']}/"
                  f"{s['units']['M1_necessary']['rate']}/{a1['M1_necessary']['rate']}  rel "
                  f"{s['passages']['M2_relevant']['rate']}/{s['units']['M2_relevant']['rate']}/"
                  f"{a1['M2_relevant']['rate']}  checks {s['passages']['M3_text_checks']['rate']}/"
                  f"{s['units']['M3_text_checks']['rate']}/{a1['M3_text_checks']['rate']}  lost "
                  f"{len(s['lost_necessary'])}  inv5 {s['M5_inv5_violations']}  chars p50 "
                  f"{s['M6_size']['chars_p50']} p90 {s['M6_size']['chars_p90']}  ms p50 {s['M7_latency_ms']['p50']}"
                  f" p95 {s['M7_latency_ms']['p95']}")
    res = {"provisional": "golden sets 1-10 are drafts; kappa not measured (D-095, D-104)", "split": a.split,
           "rule": "evals/results/assembly-rule-2026-11-20.json", "budget_chars": BUDGET_CHARS,
           "arms": "passages / units / assembled", "summary": summary,
           "rows": [{k: v for k, v in r.items() if k != "timings"} for r in rows]}
    out_path.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    # M4: 40 GPU additions by a fixed seed, read against the law (on test: once, after the code is frozen)
    random.seed(20261120)
    sample = random.sample(additions, min(40, len(additions)))
    review = ROOT / f"evals/golden/review/assembly-additions-{a.split}-{date.today().isoformat()}.json"
    if not (a.split == "test" and review.exists()):
        review.write_text(json.dumps({"what": f"M4 sample: 40 {a.split} GPU additions, seed 20261120; judge each",
                                      "items": sample}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"M4 sample ({len(sample)} of {len(additions)}) -> {review}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
