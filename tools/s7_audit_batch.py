"""Finish the weighted 200-decision S7 audit one rendered batch at a time.

`s7_audit_sample.py` draws the sample and labels it with a length heuristic.
Two passes then read 28 and 5 pages and reached opposite conclusions about
what the heuristic's 26.5% "WRONG" means -- the first found schedule rows and
false positives, the second found footnote runs standing where sections should
be. A partial reading cannot settle that. This tool exists to read all 200 the
same way and write every verdict to one machine-readable file.

FROZEN SAMPLE. The draw is the same SQL `s7_audit_sample.py` uses (stratified
by sibling-group band 1:2:3:4, at most 8 rows per document, ordered by a hash
of the adjudication id), run once and written to `sample-<date>.json`. Later
batches read that file, not the database, so a replay that retires a revision
mid-audit cannot quietly change which 200 are being audited.

WHAT A VERDICT RECORDS. Per row: `correct` (the demoted block is not a
provision distinct from the kept one -- apparatus, table row, contents entry,
quoted amendment text, duplicate), `wrong` (law was demoted), `not_s7` (both
blocks are apparatus, so the decision cannot have demoted law), with the render
paths, their SHA-256, and a written observation. Separately it records whether
the instrument the decision attaches to is still ACTIVE: 3,603 of the 4,498
decisions sit on revisions later replays retired, so the decider's error rate
and the risk to the corpus as served are different numbers and are reported
separately.

    ./nz s7-audit-batch --freeze                 write the frozen 200
    ./nz s7-audit-batch --next 12                render unread rows covering 12 pages
    ./nz s7-audit-batch --summary                counts, intervals, band weights

It writes no decision and changes no provision. Verdicts go to
`verdicts.json`, which a person or assistant fills in after reading the page.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from nizam.storage.db import connect

CORPUS = Path("/mnt/e/nizam-data")
OUT = CORPUS / "s7-audit"
VERDICTS = OUT / "verdicts.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s7_audit_sample import SAMPLE, verdict as heuristic  # noqa: E402

CONTEXT = """
SELECT a.id::text, c.id::text, c.instrument_id::text, i.is_active,
       c.document_id, c.printed_label, c.source_page, c.canonical_source_page,
       b.object_key, d.page_count
  FROM segmentation_structural_adjudication a
  JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
  JOIN instrument i ON i.id = c.instrument_id
  JOIN document d ON d.id = c.document_id
  JOIN blob b ON b.sha256 = d.sha256
 WHERE a.id = %s
"""

POPULATION_BY_BAND = """
SELECT CASE WHEN coalesce((c.evidence->>'group_size')::int,1) >= 50 THEN 4
            WHEN coalesce((c.evidence->>'group_size')::int,1) >= 10 THEN 3
            WHEN coalesce((c.evidence->>'group_size')::int,1) >= 4  THEN 2
            ELSE 1 END AS band,
       count(*)
  FROM segmentation_structural_adjudication a
  JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
  LEFT JOIN text_block k ON k.id = c.canonical_source_block_id
  LEFT JOIN text_block d ON d.id = c.source_block_id
 WHERE a.resolution = 'accept_non_citable'
   AND a.decided_by = 'nizam.structural_adjudicator/1'
   AND k.text IS NOT NULL AND d.text IS NOT NULL
 GROUP BY 1
"""


def _latest_sample() -> Path | None:
    found = sorted(OUT.glob("sample-*.json"))
    return found[-1] if found else None


def freeze() -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SAMPLE, (200, 200, 200))
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        enriched = []
        for r in rows:
            cur.execute(CONTEXT, (str(r["adjudication_id"]),))
            (adj, cand, inst, active, doc, label, page, cpage,
             key, pages) = cur.fetchone()
            h, why = heuristic(r["kept_text"], r["demoted_text"], r["grp"])
            enriched.append({
                "adjudication_id": adj, "candidate_id": cand,
                "instrument_id": inst, "instrument_active_at_freeze": active,
                "document_id": doc, "printed_label": label,
                "source_page": page, "canonical_source_page": cpage,
                "group_size": r["grp"], "band": r["band"],
                "heuristic": h, "heuristic_why": why,
                "object_key": key, "page_count": pages,
                "kept_text": " ".join((r["kept_text"] or "").split())[:600],
                "demoted_text": " ".join((r["demoted_text"] or "").split())[:600],
            })
        cur.execute(POPULATION_BY_BAND)
        population = {str(b): n for b, n in cur.fetchall()}
    stamp = dt.date.today().isoformat()
    path = OUT / f"sample-{stamp}.json"
    path.write_text(json.dumps({"frozen": stamp, "population_by_band": population,
                                "rows": enriched}, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print(f"froze {len(enriched)} rows to {path}")
    print("population by band:", population)
    return 0


def render(key: str, page: int, stem: str) -> Path | None:
    src = CORPUS / key
    if not src.exists():
        return None
    existing = sorted(OUT.glob(f"{stem}-*.png"))
    if existing:
        return existing[0]
    subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "130",
                    "-png", str(src), str(OUT / stem)],
                   check=False, capture_output=True)
    written = sorted(OUT.glob(f"{stem}-*.png"))
    return written[0] if written else None


def next_batch(n: int) -> int:
    sample_path = _latest_sample()
    if sample_path is None:
        print("no frozen sample -- run --freeze first")
        return 1
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    done = json.loads(VERDICTS.read_text(encoding="utf-8")) if VERDICTS.exists() else {}
    # Batch by PAGE, not by row: a compendium page can answer eight rows at
    # once, and the reading is the expensive part. Take unread rows grouped by
    # document and page until N distinct pages are covered.
    unread = sorted((r for r in sample["rows"] if r["adjudication_id"] not in done),
                    key=lambda r: (r["document_id"], r["source_page"] or 0,
                                   r["canonical_source_page"] or 0))
    todo, pages_seen = [], set()
    for r in unread:
        need = {(r["document_id"], p) for p in (r["source_page"],
                                                 r["canonical_source_page"]) if p}
        if len(pages_seen | need) > n and todo:
            break
        pages_seen |= need
        todo.append(r)
    batch = []
    for r in todo:
        adj8 = r["adjudication_id"][:8]
        pages = sorted({p for p in (r["source_page"], r["canonical_source_page"]) if p})
        renders = []
        for p in pages:
            # One render per document page, shared by every row that cites it.
            path = render(r["object_key"], p, f"audit-doc{r['document_id']}-p{p}")
            if path is not None:
                renders.append({"page": p, "render": str(path),
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        batch.append({**{k: r[k] for k in ("adjudication_id", "document_id",
                                            "printed_label", "source_page",
                                            "canonical_source_page", "group_size",
                                            "band", "heuristic",
                                            "instrument_active_at_freeze")},
                      "renders": renders,
                      "kept_text": r["kept_text"][:300],
                      "demoted_text": r["demoted_text"][:300]})
    out = OUT / "batch-next.json"
    out.write_text(json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"sample {sample_path.name}: {len(done)} read, "
          f"{len(sample['rows']) - len(done)} unread; this batch {len(batch)} -> {out}")
    return 0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def summary() -> int:
    sample_path = _latest_sample()
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    done = json.loads(VERDICTS.read_text(encoding="utf-8")) if VERDICTS.exists() else {}
    rows = {r["adjudication_id"]: r for r in sample["rows"]}
    read = [(rows[a], v) for a, v in done.items() if a in rows]
    n = len(read)
    print(f"sample {sample_path.name}: {n} of {len(rows)} read")
    by = {}
    for r, v in read:
        by.setdefault(v["verdict"], []).append(r)
    for key in ("correct", "wrong", "not_s7"):
        k = len(by.get(key, []))
        lo, hi = wilson(k, n)
        print(f"  {key:8} {k:4}  {100*k/n if n else 0:5.1f}%   95% CI {100*lo:4.1f}-{100*hi:4.1f}%")
    # Inverse-probability weighting: each band was sampled at its own rate.
    pop = {int(b): c for b, c in sample["population_by_band"].items()}
    sampled_in_band = {}
    for r in rows.values():
        sampled_in_band[r["band"]] = sampled_in_band.get(r["band"], 0) + 1
    read_in_band = {}
    wrong_in_band = {}
    for r, v in read:
        read_in_band[r["band"]] = read_in_band.get(r["band"], 0) + 1
        if v["verdict"] == "wrong":
            wrong_in_band[r["band"]] = wrong_in_band.get(r["band"], 0) + 1
    est = 0.0
    covered = 0
    for b, total in pop.items():
        if read_in_band.get(b):
            est += total * wrong_in_band.get(b, 0) / read_in_band[b]
            covered += total
    if covered:
        print(f"  band-weighted wrong estimate over the {covered:,} decisions in "
              f"read bands: {est:,.0f} ({100*est/covered:.1f}%)")
    live = [(r, v) for r, v in read if v.get("instrument_active_now")]
    lw = sum(1 for _, v in live if v["verdict"] == "wrong")
    print(f"  on instruments still active: {len(live)} read, {lw} wrong")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--freeze", action="store_true")
    g.add_argument("--next", type=int, metavar="N")
    g.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.freeze:
        return freeze()
    if a.next:
        return next_batch(a.next)
    return summary()


if __name__ == "__main__":
    raise SystemExit(main())
