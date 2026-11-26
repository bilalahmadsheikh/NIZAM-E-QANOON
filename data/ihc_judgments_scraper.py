"""The Islamabad High Court's published judgments, from the court's own site (D-156; docs/SOURCES-NOT-HELD-2026-11-26.md).

    python3 -I data/ihc_judgments_scraper.py [--years 1990-2026] [--delay 3] [--out /mnt/e/nizam-data/acquire/ihc]

mis.ihc.gov.pk's judgments page lists, through its own public JSON service (ihc.asmx/srchDecisionClms; no captcha,
no login, robots.txt absent), the decisions the court marks "important" (PLANDMARK 0) and "approved for reporting"
(PLANDMARK 1), searchable by case year. For each case year both lists are read, every decision is recorded once (by
the court's record id O_ID) in listing.jsonl, and its PDF is fetched from /attachments/judgements/... .

What is kept: the court's own record of the decision (case number, parties as listed, bench, author, decision date,
subject, the section it was decided under, citation identifiers, and what the Supreme Court later did on appeal:
status, result, its citation and date). What is never kept: the headnotes (O_IHC_HEADNOTE, O_SC_HEADNOTE) -- a
reporter's or the court's summary prose, never stored or used (D-120). Citations are identifiers only.

Writes <out>/ihc_judgments/ (PDFs, listing.jsonl, manifest.csv) and <out>/ihc_judgments.zip (members under
ihc_judgments/), landed as the other court crawls (nizam.workers.judgments --court IHC --member-prefix ihc_judgments/).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://mis.ihc.gov.pk"
UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"
NEVER = {"O_IHC_HEADNOTE", "O_SC_HEADNOTE"}               # headnotes: never stored (D-120)


def call(year: int, landmark: str) -> list[dict]:
    body = json.dumps(dict(PCASENO="0", PJUG="0", PADV="0", PYEAR=str(year), pPrty="", PDDATE="01/01/1900",
                           PLANDMARK=landmark, PAFR=landmark)).encode()
    req = urllib.request.Request(f"{BASE}/ihc.asmx/srchDecisionClms", data=body,
                                 headers={"User-Agent": UA, "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())["d"]
    return json.loads(d) if d.startswith("[") else []


def get(url: str) -> bytes:
    head, _, name = url.rpartition("/")
    url = f"{head}/{urllib.parse.quote(urllib.parse.unquote(name))}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="1990-2026")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/ihc"))
    a = ap.parse_args()
    lo, _, hi = a.years.partition("-")
    folder = a.out / "ihc_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    listing = folder / "listing.jsonl"
    seen = {json.loads(x)["O_ID"]: json.loads(x) for x in listing.read_text(encoding="utf-8").splitlines()} \
        if listing.exists() else {}
    with open(listing, "a", encoding="utf-8") as fh:
        for year in range(int(lo), int(hi or lo) + 1):
            for landmark, kind in (("1", "reported"), ("0", "important")):
                try:
                    rows = call(year, landmark)
                except Exception as exc:                          # noqa: BLE001
                    print(f"{year} {kind}: error {type(exc).__name__}: {exc}", flush=True)
                    time.sleep(a.delay * 3)
                    continue
                new = 0
                for r in rows:
                    rec = {k: v for k, v in r.items() if k not in NEVER}
                    if rec["O_ID"] not in seen:
                        rec.update(listed_as=kind, case_year=year, seen_on=today)
                        seen[rec["O_ID"]] = rec
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        new += 1
                fh.flush()
                print(f"{year} {kind}: {len(rows)} listed, {new} new", flush=True)
                time.sleep(a.delay)
    out, got, kept, bad = [], 0, 0, 0
    for oid, r in seen.items():
        att = (r.get("ATTACHMENTS") or "").strip()
        if not att.lower().endswith(".pdf"):
            out.append(dict(o_id=oid, filename="", status="no_pdf_listed", sha256="", caseno=r.get("CASENO", "")))
            continue
        name = f"{oid}_{Path(att).name}"
        path = folder / name
        status, sha = "ok", ""
        if path.exists():
            kept += 1
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            try:
                data = get(BASE + att)
                if not data.startswith(b"%PDF"):
                    status, bad = "not_a_pdf", bad + 1
                else:
                    path.write_bytes(data)
                    sha, got = hashlib.sha256(data).hexdigest(), got + 1
            except Exception as exc:                              # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        out.append(dict(o_id=oid, filename=name, status=status, sha256=sha, caseno=r.get("CASENO", ""),
                        ddate=r.get("DDATE", ""), url=BASE + att))
        if len(out) % 100 == 0:
            print(f"files {len(out)}/{len(seen)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["o_id", "filename", "status", "sha256", "caseno", "ddate", "url"])
        w.writeheader()
        w.writerows(out)
    zpath = a.out / "ihc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"ihc_judgments/{p.name}")
    print(f"listed {len(seen)}; downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
