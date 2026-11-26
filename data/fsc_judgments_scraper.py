"""The Federal Shariat Court's published judgments, from the court's own site (D-157; docs/SOURCES-NOT-HELD-2026-11-26.md).

    python3 -I data/fsc_judgments_scraper.py [--delay 3] [--out /mnt/e/nizam-data/acquire/fsc]

federalshariatcourt.gov.pk publishes four lists (robots.txt disallows only /wp-admin/, and allows admin-ajax):
  * shariatjudgment2.2.php: the Shariat petitions and references (Art. 203D), one table row each, with the court's
    own record of the case number, parties, citation, decision date, author, **law challenged** and remarks, and a
    `?download=N` link to the judgment;
  * judgments_api.php, category 'criminal' (the page criminaljudgments.html posts its empty search form there): the
    criminal appeals, with case number, parties, bench, date, the section decided under and citation;
  * the same, category 'suomoto' (suomoto.html): the Shariat suo motu decisions;
  * landmarkjudgemnts.html: a list of landmark judgments in the page's own script (mostly the petitions again).
Each record is kept once per file URL in listing.jsonl, with the list it came from; files are fetched once.

Kept: the court's own record of each decision (above). The law challenged is the court's own words: the evidence a
later `invalidated_by` reading starts from (docs/03b), never itself a ruling. Citations are identifiers only (D-120).

Writes <out>/fsc_judgments/ (PDFs, listing.jsonl, manifest.csv) and <out>/fsc_judgments.zip (members under
fsc_judgments/), landed as the other court crawls (nizam.workers.judgments --court FSC --member-prefix fsc_judgments/).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

BASE = "https://www.federalshariatcourt.gov.pk/"
UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"


def fetch(url: str, data: bytes | None = None, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def quote_path(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path)), p.query, ""))


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def shariat_rows(page: str) -> list[dict]:
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S | re.I):
        cells = dict(re.findall(r'<td[^>]*data-label="([^"]+)"[^>]*>(.*?)</td>', tr, re.S | re.I))
        link = re.search(r'href="([^"]*\?download=\d+)"', tr)
        if not cells or not link:
            continue
        out.append(dict(list="shariat", case_no=text(cells.get("Ref. No")), parties=text(cells.get("Party Names")),
                        citation=text(cells.get("FSC Citation")), listed_date=text(cells.get("Decision Date")),
                        author=text(cells.get("Author Judge")), law_challenged=text(cells.get("Law Challenged")),
                        remarks=text(cells.get("Remarks")),
                        url=urllib.parse.urljoin(BASE + "shariatjudgment2.2.php", html.unescape(link.group(1)))))
    return out


def api_rows(category: str) -> list[dict]:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"category\"\r\n\r\n{category}\r\n"
            f"--{boundary}--\r\n").encode()
    d = json.loads(fetch(BASE + "judgments_api.php", body,
                         {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    out = []
    for r in d.get("rows", []):
        if not (r.get("judgement") or "").strip():
            continue
        out.append(dict(list=category, case_no=" ".join((r.get("casejno") or "").split()),
                        parties=" ".join((r.get("pn") or "").split()), bench=" ".join((r.get("decidedby") or "").split()),
                        listed_date=r.get("doj") or "", under=" ".join((r.get("sent") or "").split()),
                        citation=r.get("citation") or "", year=r.get("yearj"),
                        url=quote_path(urllib.parse.urljoin(BASE, r["judgement"].strip()))))
    return out


def landmark_rows(page: str) -> list[dict]:
    b = re.search(r'const B="([^"]+)"', page)
    d = re.search(r"const D=(\[.*?\]);", page, re.S)
    if not (b and d):
        return []
    out = []
    for title, citation, day, name in json.loads(d.group(1)):
        out.append(dict(list="landmark", title=title, citation=citation, listed_date=day,
                        url=quote_path(b.group(1) + name)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/fsc"))
    a = ap.parse_args()
    folder = a.out / "fsc_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    rows: list[dict] = []
    rows += shariat_rows(fetch(BASE + "shariatjudgment2.2.php").decode("utf-8", "replace"))
    time.sleep(a.delay)
    for cat in ("criminal", "suomoto"):
        rows += api_rows(cat)
        time.sleep(a.delay)
    rows += landmark_rows(fetch(BASE + "landmarkjudgemnts.html").decode("utf-8", "replace"))
    by_url: dict[str, dict] = {}
    for r in rows:
        r["seen_on"] = today
        by_url.setdefault(r["url"], r)
    print({k: sum(1 for r in rows if r["list"] == k) for k in ("shariat", "criminal", "suomoto", "landmark")},
          f"{len(by_url)} distinct files", flush=True)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    out, got, kept, bad = [], 0, 0, 0
    for i, (url, r) in enumerate(by_url.items()):
        name = f"{hashlib.sha1(url.encode()).hexdigest()[:10]}_{re.sub(r'[^A-Za-z0-9.-]+', '_', r.get('case_no') or r.get('title') or 'judgment')[:80]}.pdf"
        path = folder / name
        status, sha = "ok", ""
        if path.exists():
            kept += 1
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            try:
                data = fetch(url)
                if not data.startswith(b"%PDF"):
                    status, bad = "not_a_pdf", bad + 1
                else:
                    path.write_bytes(data)
                    sha, got = hashlib.sha256(data).hexdigest(), got + 1
            except Exception as exc:                              # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        out.append(dict(filename=name if status == "ok" else "", status=status, sha256=sha, list=r["list"],
                        case_no=r.get("case_no") or r.get("title", ""), listed_date=r.get("listed_date", ""), url=url))
        if (i + 1) % 50 == 0:
            print(f"files {i + 1}/{len(by_url)}: downloaded {got}, held {kept}, failed {bad}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["filename", "status", "sha256", "list", "case_no", "listed_date", "url"])
        w.writeheader()
        w.writerows(out)
    zpath = a.out / "fsc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"fsc_judgments/{p.name}")
    print(f"distinct files {len(by_url)}; downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
