"""Lexical experiments on golden sets 1-4 (PROVISIONAL, D-095): what the cheap changes to the BM25 stage are worth.

    python evals/lexical_experiments.py [--out evals/results/lexical-experiments-<date>.json]

Measured, never tuned on: every setting below was fixed before the run (docs/04 §5 constants, a generic English
question-frame list). The golden sets are drafts without kappa, and there is no dev/test split yet, so nothing here is
fitted to them -- no synonym list built from their questions is tried (that would be tuning on the test set).

Configurations (k = 50 legal UNITS; a unit = the provision's innermost section/article/rule-level ancestor, else its
outermost schedule/form/appendix/annexure/preamble):
  B0  nodes      -- today's port: the top 50 provisions as they come (the D-095 benchmark, recomputed here)
  E1  units      -- 400 node hits collapsed to units, unitScore = max + 0.15 * second best (docs/04 §5)
  E2  units-frame-- E1 on the question with its frame stripped (pronouns, question words, auxiliaries)
  E3  fused      -- E2 plus RRF (k=60, docs/04 §5) of three ranked lists: body units, heading/marginal-note units,
                    and units of instruments whose TITLE matches
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.storage.db import connect  # noqa: E402
from nizam.storage.lexical import Bm25LexicalSearch, Filters  # noqa: E402

K = 50
RRF_K = 60
FRAME = set("""i me my mine we us our you your he him his she her they them their it its this that these those
what which who whom whose when where why how can could may might must shall should will would do does did done is
am are was were be been being have has had having a an the of to in on at for from by with about as into than then
so if or and but not no yes there here want wants wanted get gets got let tell know please any some someone anyone
also just still even only very really allowed legal law laws rule rules""".split())

UNIT_KINDS = ("section", "article", "order")
OUTER_KINDS = ("schedule", "form", "appendix", "annexure", "preamble")


def cases():
    for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            units = d["retrievalGold"].get("necessaryUnits") or []
            if d["expectedOutcome"] in ("answer", "conditional") and units:
                yield d, units


def strip_frame(q: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", q)
    kept = [w for w in words if w.lower().strip("'") not in FRAME]
    return " ".join(kept) or q


def unit_of(cur, pids: list[str]) -> dict[str, tuple[str, str]]:
    """{provision id: (unit id, unit path)} -- innermost section-level ancestor-or-self, else outermost container"""
    cur.execute("""
        SELECT c.id::text,
               coalesce(
                 (SELECT a.id::text || '|' || a.path::text FROM provision a
                   WHERE a.instrument_id = c.instrument_id AND a.path @> c.path AND a.kind::text = ANY(%s)
                   ORDER BY nlevel(a.path) DESC LIMIT 1),
                 (SELECT a.id::text || '|' || a.path::text FROM provision a
                   WHERE a.instrument_id = c.instrument_id AND a.path @> c.path AND a.kind::text = ANY(%s)
                   ORDER BY nlevel(a.path) LIMIT 1),
                 c.id::text || '|' || c.path::text)
          FROM provision c WHERE c.id = ANY(%s::uuid[])""", (list(UNIT_KINDS), list(OUTER_KINDS), pids))
    return {pid: tuple(v.split("|", 1)) for pid, v in cur.fetchall()}


def collapse(cur, cands) -> list[tuple[str, str, float]]:
    """[(unit id, unit path, unitScore)] best first; unitScore = max + 0.15 * second best (docs/04 §5)"""
    if not cands:
        return []
    u = unit_of(cur, [c.provision_id for c in cands])
    scores = collections.defaultdict(list)
    path = {}
    for c in cands:
        uid, up = u[c.provision_id]
        scores[uid].append(c.score)
        path[uid] = up
    ranked = []
    for uid, ss in scores.items():
        ss.sort(reverse=True)
        ranked.append((uid, path[uid], ss[0] + 0.15 * (ss[1] if len(ss) > 1 else 0.0)))
    ranked.sort(key=lambda x: (-x[2], x[0]))
    return ranked


def title_units(cur, q: str, filters: Filters, n: int = 20) -> list[tuple[str, int]]:
    """[(instrument id, rank)] of released instruments whose title matches"""
    cur.execute("""SELECT i.id::text FROM instrument i
                    WHERE (i.short_title ||| %(q)s OR i.display_title ||| %(q)s OR i.long_title ||| %(q)s)
                      AND EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = i.id)
                      AND (%(j)s::text[] IS NULL OR i.jurisdiction::text = ANY(%(j)s::text[]))
                    ORDER BY pdb.score(i.id) DESC, i.id LIMIT %(n)s""",
                dict(q=q, n=n, j=list(filters.jurisdictions) if filters.jurisdictions else None))
    return [(r[0], k) for k, r in enumerate(cur.fetchall(), 1)]


def score(ranked_paths: list[str], gold: dict[str, str]) -> dict:
    def hit(gp):
        return next((r for r, p in enumerate(ranked_paths, 1) if p == gp or p.startswith(gp + ".")), None)
    ranks = {g: hit(p) for g, p in gold.items()}
    first = min((r for r in ranks.values() if r), default=None)
    return {"recall10": sum(1 for r in ranks.values() if r and r <= 10) / len(gold),
            "recall50": sum(1 for r in ranks.values() if r and r <= K) / len(gold),
            "mrr10": (1 / first) if first and first <= 10 else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / f"evals/results/lexical-experiments-{date.today().isoformat()}.json"))
    a = ap.parse_args()
    s = Bm25LexicalSearch()
    per = collections.defaultdict(list)
    with connect() as conn, conn.cursor() as cur:
        for d, units in cases():
            j = d["scope"]["jurisdiction"]
            f = Filters(as_of=date.fromisoformat(d["scope"]["asOf"]),
                        jurisdictions=("fed",) if j in ("fed", "foreign") else (j, "fed"))
            gold = {u["provisionId"]: u["path"] for u in units}
            q0 = d["question"]["text"]
            qf = strip_frame(q0)
            meta = {"case": d["caseId"], "stratum": d["stratum"]}
            t = time.time()
            nodes = s.search(q0, f, 400)
            cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])",
                        ([c.provision_id for c in nodes[:K]],))
            pth = dict(cur.fetchall())
            per["B0 nodes"].append(dict(meta, **score([pth[c.provision_id] for c in nodes[:K]], gold),
                                        ms=round((time.time() - t) * 1000)))
            u1 = collapse(cur, nodes)
            per["E1 units"].append(dict(meta, **score([p for _u, p, _s in u1[:K]], gold)))
            t = time.time()
            nodes_f = s.search(qf, f, 400)
            u2 = collapse(cur, nodes_f)
            per["E2 units-frame"].append(dict(meta, **score([p for _u, p, _s in u2[:K]], gold),
                                              ms=round((time.time() - t) * 1000)))
            # E3: RRF of body units, heading units, title-matched instruments' units
            heads = collapse(cur, s.headings(qf, f, 100))
            titles = dict((iid, r) for iid, r in title_units(cur, qf, f))
            fused = collections.defaultdict(float)
            paths = {}
            for lst in (u2, heads):
                for r, (uid, up, _s) in enumerate(lst, 1):
                    fused[uid] += 1 / (RRF_K + r)
                    paths[uid] = up
            if titles and paths:
                cur.execute("SELECT id::text, instrument_id::text FROM provision WHERE id = ANY(%s::uuid[])",
                            (list(paths),))
                for uid, iid in cur.fetchall():
                    if iid in titles:
                        fused[uid] += 1 / (RRF_K + titles[iid])
            order = sorted(fused, key=lambda u: (-fused[u], u))
            per["E3 fused"].append(dict(meta, **score([paths[u] for u in order[:K]], gold)))
    summary = {}
    for name, rows in per.items():
        by = collections.defaultdict(list)
        for r in rows:
            by[r["stratum"]].append(r["recall50"])
        summary[name] = {"recall@10": round(statistics.mean(r["recall10"] for r in rows), 4),
                         "recall@50": round(statistics.mean(r["recall50"] for r in rows), 4),
                         "mrr@10": round(statistics.mean(r["mrr10"] for r in rows), 4),
                         "recall@50 by stratum": {k: round(statistics.mean(v), 3) for k, v in sorted(by.items())}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"provisional": "golden drafts, kappa not measured; nothing tuned on them",
                                       "summary": summary, "cases": per}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
