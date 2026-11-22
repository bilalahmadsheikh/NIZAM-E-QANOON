"""second_read.py STAGED FILES OUT_DIR [--workers N] [--limit N] : the local Tesseract reading of every staged scan.

D-114: a scan's release reading comes from Google Document AI (nizam/corpus/ocr_docai.py); the independent check is a
second engine reading the same pages, as lane E2 is checked by a second PDF library. This writes that second reading:
OUT_DIR/<sha256>.json.gz = {"sha256", "extractor", "pages": [text of page 1, ...], "mean_confidence", "lang"}, one
file per PDF, from nizam.corpus.ocr.ocr_pdf unchanged (300 DPI, script-aware). Rows graded 'text' are skipped (they
are not scans). Resumable: a PDF whose file exists is not read again. No database, no network.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SCAN_GRADES = {"scan", "partial", "urdu"}


def read_one(job: tuple[str, str, str]) -> tuple[str, str]:
    sha, path, out_dir = job
    from nizam.corpus.ocr import ocr_pdf
    from nizam.shared.corpus_types import ExtractionRejected
    started = time.time()
    dst = Path(out_dir) / f"{sha}.json.gz"
    try:
        doc = ocr_pdf(Path(path).read_bytes(), sha)
        pages = ["" for _ in range(doc.page_count)]
        for b in sorted(doc.blocks, key=lambda b: b.reading_order):
            pages[b.page_no - 1] += (("\n" if pages[b.page_no - 1] else "") + b.text)
        rec = {"sha256": sha, "extractor": doc.extractor, "pages": pages,
               "mean_confidence": doc.printable_ratio, "lang": doc.pdf_metadata.get("ocr_language"),
               "seconds": round(time.time() - started, 1)}
        status = f"ok {doc.page_count}p conf={doc.printable_ratio:.3f}"
    except ExtractionRejected as e:
        rec = {"sha256": sha, "rejected": str(e)[:300]}
        status = "rejected"
    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(rec, ensure_ascii=False).encode("utf-8")))
    tmp.replace(dst)
    return sha, f"{status} {time.time() - started:.0f}s"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staged", nargs="+", help="staged.csv files, each followed by its files dir: CSV DIR [CSV DIR ...]")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if len(a.staged) % 2:
        ap.error("give staged.csv and files-dir pairs")
    a.out.mkdir(parents=True, exist_ok=True)
    jobs, seen = [], set()
    for csv_path, files in zip(a.staged[::2], a.staged[1::2]):
        for r in csv.DictReader(open(csv_path, encoding="utf-8")):
            sha = r.get("sha256") or ""
            if r.get("grade") not in SCAN_GRADES or not sha or sha in seen:
                continue
            seen.add(sha)
            f = Path(files) / f"{sha}.pdf"
            if f.exists() and not (a.out / f"{sha}.json.gz").exists():
                jobs.append((sha, str(f), str(a.out)))
    jobs.sort(key=lambda j: Path(j[1]).stat().st_size)
    if a.limit:
        jobs = jobs[: a.limit]
    print(f"second read: {len(jobs)} scan(s), {a.workers} workers", flush=True)
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(read_one, j) for j in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                sha, status = fut.result()
                print(f"{n}/{len(jobs)} {sha[:12]} {status}", flush=True)
            except Exception as e:  # noqa: BLE001 -- one bad scan never stops the run
                print(f"{n}/{len(jobs)} ERROR {type(e).__name__}: {e}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
