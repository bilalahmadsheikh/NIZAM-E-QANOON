"""dense_scan_benchmark.py [--window 900] [--split dev] : HNSW against the exact scan, on the dev questions (D-098).

docs/04 §9.1 asks for adaptive execution: an exact scan where few rows are eligible, HNSW (iterative scan) elsewhere.
Where "few" ends is a measurement, not a guess. For every dev question this encodes the question with the installed
int8 encoder (nizam.inference.encoder), takes the question's scope as the golden case states it (its jurisdiction plus
fed), and runs BOTH of nizam.storage.unit_search.dense_hits' SQL paths with the same window:

  exact  every chunk in scope, bit_count(embedding # q), ORDER BY distance -- the true nearest chunks
  hnsw   ix_chunk_hnsw with hnsw.iterative_scan = strict_order and ef_search = window, scope filter in the scan

Reported per scope size: latency of each (warm: each query is run once untimed first), and HNSW's recall of the exact
window, tie-aware (Hamming distances are integers): the share of HNSW rows whose distance is within the exact
window's last distance -- 1.0 means HNSW returned a true nearest window, whichever of equally-distant chunks it chose.
Read-only. Writes evals/results/dense-scan-<date>.json with --out.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.inference.encoder import encoder  # noqa: E402
from nizam.storage.db import connect  # noqa: E402

EXACT = """SELECT c.id, bit_count(c.embedding # %(q)s::bit(1024)) AS d FROM chunk c
            WHERE c.jurisdiction = ANY(%(j)s::text[]) AND c.embedding IS NOT NULL ORDER BY d, c.id LIMIT %(w)s"""
HNSW = """SELECT c.id, (c.embedding <~> %(q)s::bit(1024))::int AS d FROM chunk c
           WHERE c.jurisdiction = ANY(%(j)s::text[]) ORDER BY c.embedding <~> %(q)s::bit(1024) LIMIT %(w)s"""


def cases(split: str):
    s = json.loads((ROOT / "evals/golden/split-v1.json").read_text(encoding="utf-8"))
    keep = set(s[split]) if split != "all" else None
    for f in sorted((ROOT / "evals/golden").glob("golden-pk-v1-set*.draft.jsonl")):
        for line in f.open(encoding="utf-8"):
            d = json.loads(line)
            if keep is not None and d["caseId"] not in keep:
                continue
            j = d["scope"]["jurisdiction"]
            yield d["caseId"], d["question"]["text"], (["fed"] if j in ("fed", "foreign") else [j, "fed"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=900)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--out")
    a = ap.parse_args()
    enc = encoder()
    rows = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT jurisdiction, count(*) FROM chunk WHERE embedding IS NOT NULL GROUP BY 1")
        counts = dict(cur.fetchall())
        cur.execute("SELECT set_config('hnsw.ef_search', %s, false), "        # session-wide: this connection only
                    "set_config('hnsw.iterative_scan', 'strict_order', false)", (str(min(1000, a.window)),))
        for case, q, juris in cases(a.split):
            p = dict(q=enc.bits(q), j=juris, w=a.window)
            out = {}
            for name, sql in (("exact", EXACT), ("hnsw", HNSW)):
                cur.execute(sql, p)                                   # warm
                t = time.perf_counter()
                cur.execute(sql, p)
                res = cur.fetchall()
                out[name] = (res, (time.perf_counter() - t) * 1000)
            exact, hnsw = out["exact"][0], out["hnsw"][0]
            last = exact[-1][1] if exact else 0
            recall = sum(1 for _, d in hnsw if d <= last) / max(1, len(exact))
            rows.append({"case": case, "scope": "+".join(juris), "eligible": sum(counts.get(j, 0) for j in juris),
                         "exact_ms": round(out["exact"][1], 1), "hnsw_ms": round(out["hnsw"][1], 1),
                         "hnsw_rows": len(hnsw), "recall": round(recall, 4)})
    by: dict = {}
    for r in rows:
        by.setdefault((r["eligible"], r["scope"]), []).append(r)
    summary = []
    print(f"{'scope':16} {'eligible':>9} {'n':>3}  {'exact p50':>9} {'p95':>6}  {'hnsw p50':>8} {'p95':>6}  "
          f"{'recall mean':>11} {'min':>6}")
    for (elig, scope), rs in sorted(by.items()):
        ex = sorted(r["exact_ms"] for r in rs)
        hn = sorted(r["hnsw_ms"] for r in rs)
        rec = [r["recall"] for r in rs]
        s = {"scope": scope, "eligible": elig, "n": len(rs), "exact_p50": statistics.median(ex),
             "exact_p95": ex[min(len(ex) - 1, int(0.95 * len(ex)))], "hnsw_p50": statistics.median(hn),
             "hnsw_p95": hn[min(len(hn) - 1, int(0.95 * len(hn)))], "recall_mean": round(statistics.mean(rec), 4),
             "recall_min": min(rec)}
        summary.append(s)
        print(f"{scope:16} {elig:>9} {len(rs):>3}  {s['exact_p50']:>9.0f} {s['exact_p95']:>6.0f}  "
              f"{s['hnsw_p50']:>8.0f} {s['hnsw_p95']:>6.0f}  {s['recall_mean']:>11.4f} {s['recall_min']:>6.3f}")
    allrec = [r["recall"] for r in rows]
    print(f"all: n={len(rows)} hnsw recall mean {statistics.mean(allrec):.4f} min {min(allrec):.3f}; "
          f"exact p50 {statistics.median(r['exact_ms'] for r in rows):.0f} ms, "
          f"hnsw p50 {statistics.median(r['hnsw_ms'] for r in rows):.0f} ms")
    if a.out:
        Path(a.out).write_text(json.dumps({"split": a.split, "window": a.window, "summary": summary, "rows": rows},
                                          indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
