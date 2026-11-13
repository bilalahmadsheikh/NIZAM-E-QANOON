"""stage_candidates.py : download the laws portal_diff.py found missing to a staging folder and grade each file (no DB).

Input: one or more CSVs with at least title and pdf_url (portal_diff.py's <portal>-listing.csv rows whose verdict is
'candidate', or tools/evidence/sindh-portal-gap-2026-11-12.json converted by --sindh-gap). Each file is fetched once
(resumable: an existing staged file with a recorded sha256 is not fetched again) and graded from its own bytes:

    pages, characters per page, share of printable characters, pages with no text, Latin vs Arabic-script share,
    and the first heading line of page 1.

Grade -- a PREDICTION of the work a file needs before release, not a release decision (the corpus's own extraction,
segmentation and release gates decide that):
    text      every page carries a Latin text layer (>= 200 chars/page median, <= 10% empty pages, printable >= 0.97)
    partial   a text layer, but thin or with empty pages: some pages will need OCR
    scan      no usable text layer: OCR before anything else
    not_pdf   the URL did not serve a PDF (recorded with the served type and first bytes)
    urdu      the text layer is mostly Arabic script (not the English lane)

    python tools/acquire/stage_candidates.py --out DIR CSV [CSV ...]
    python tools/acquire/stage_candidates.py --out DIR --sindh-gap tools/evidence/sindh-portal-gap-2026-11-12.json
Writes DIR/staged.csv (one row per candidate) and DIR/files/<sha256>.pdf.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"}
SINDH_EN = "https://sindhlaws.gov.pk/DownloadDocument.aspx?PubID={}&Lang=EN"
FIELDS = ["portal", "kind", "year_or_dept", "title", "detail_url", "pdf_url", "status", "http_status", "content_type",
          "bytes", "sha256", "pages", "median_chars", "empty_pages", "printable", "latin_share", "grade", "first_line",
          "error"]


def grade(pdf: Path) -> dict:
    import fitz
    with fitz.open(pdf) as d:
        texts = [p.get_text("text") for p in d]
    n = len(texts)
    chars = [len(t.strip()) for t in texts]
    allt = "".join(texts)
    printable = sum(c.isprintable() or c in "\n\t" for c in allt) / max(1, len(allt))
    latin = len(re.findall(r"[A-Za-z]", allt)); arabic = len(re.findall(r"[؀-ۿ]", allt))
    empty = sum(c < 30 for c in chars)
    med = statistics.median(chars) if chars else 0
    first = next((ln.strip() for ln in (texts[0] if texts else "").splitlines() if len(ln.strip()) > 8), "")
    if arabic > latin:
        g = "urdu"
    elif med >= 200 and empty <= max(0, n // 10) and printable >= 0.97:
        g = "text"
    elif med >= 50:
        g = "partial"
    else:
        g = "scan"
    return {"pages": n, "median_chars": int(med), "empty_pages": empty, "printable": round(printable, 4),
            "latin_share": round(latin / max(1, latin + arabic), 3), "grade": g, "first_line": first[:120]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="*", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--sindh-gap", type=Path)
    a = ap.parse_args()
    rows = []
    for c in a.csv:
        with c.open(encoding="utf-8", newline="") as fh:
            rows += [r for r in csv.DictReader(fh) if r.get("verdict", "candidate").startswith("candidate")]
    if a.sindh_gap:
        for g in json.loads(a.sindh_gap.read_text(encoding="utf-8-sig")):
            rows.append({"portal": "sindh", "kind": g["doc_type"].lower(), "year_or_dept": g["year"],
                         "title": " ".join(g["title"].split()), "detail_url": g.get("listing_url", ""),
                         "pdf_url": SINDH_EN.format(g["pub_id"]) if g.get("en") == "True" else ""})
    files = a.out / "files"; files.mkdir(parents=True, exist_ok=True)
    dst = a.out / "staged.csv"
    done = {}
    if dst.exists():
        with dst.open(encoding="utf-8", newline="") as fh:
            done = {r["pdf_url"]: r for r in csv.DictReader(fh) if r.get("sha256")}
    s = requests.Session(); s.headers.update(UA)
    out = []
    for r in rows:
        row = {k: r.get(k, "") for k in FIELDS}
        if r.get("pdf_url") in done:
            out.append(done[r["pdf_url"]]); continue
        if not r.get("pdf_url"):
            row.update(status="no_file", grade="no_file"); out.append(row); continue
        try:
            resp = s.get(r["pdf_url"], timeout=120, verify=not r["pdf_url"].startswith("https://sindhlaws"))
            body = resp.content
            row.update(http_status=resp.status_code, content_type=resp.headers.get("content-type", ""),
                       bytes=len(body))
            if resp.status_code != 200 or not body.startswith(b"%PDF"):
                row.update(status="not_pdf", grade="not_pdf", error=body[:120].decode("latin-1", "replace"))
            else:
                h = hashlib.sha256(body).hexdigest(); p = files / f"{h}.pdf"; p.write_bytes(body)
                row.update(status="staged", sha256=h, **grade(p))
        except Exception as e:  # recorded, never fatal: one bad file must not stop the rest
            row.update(status="error", grade="error", error=f"{type(e).__name__}: {e}"[:200])
        out.append(row)
        print(f"{row['grade']:8} {row['portal']:12} {row['title'][:80]}", flush=True)
        time.sleep(1.5)
    with dst.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore"); w.writeheader(); w.writerows(out)
    by = {}
    for r in out:
        by[r["grade"]] = by.get(r["grade"], 0) + 1
    print(by, "->", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
