"""Crawl the Gilgit-Baltistan Chief Court's reported judgments (gbcc.gov.pk), D-139.

    python3 -I data/gbcc_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/gbcc] [--delay 2]

https://gbcc.gov.pk/ReportedJudgments.aspx is an ASP.NET form (25 Nov 2026): a bench list (ddlCourt), a decision-date
list (ddlCaseyear) and a case number box. A search lists rows -- serial, case no, bench, author judge, parties,
citation (a reporter identifier) -- each with a 'View PDF' submit button; pressing it posts the form back and the
response is the file. A search with nothing chosen lists nothing, so every bench and every date is searched and the
rows are merged by serial. The site has no robots.txt (404).

Polite: one request at a time, --delay apart, a generic client name; a download is kept only if it is a PDF. Writes
gbcc_judgments/<serial>.pdf, listing.jsonl, manifest.csv and gbcc_judgments.zip.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"
URL = "https://gbcc.gov.pk/ReportedJudgments.aspx"
P = "ctl00$ContentPlaceHolder1$"


class Site:
    def __init__(self, delay: float):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.delay = delay

    def fetch(self, data: dict | None = None) -> bytes:
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        with self.op.open(urllib.request.Request(URL, data=body, headers={"User-Agent": UA}), timeout=180) as r:
            out = r.read()
        time.sleep(self.delay)
        return out


def hidden(page: str) -> dict:
    return dict(re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page))


def options(page: str, name: str) -> list[str]:
    m = re.search(r'(?s)<select name="%s".*?</select>' % re.escape(P + name), page)
    return [html.unescape(v) for v in re.findall(r'<option[^>]*value="([^"]*)"', m.group(0))][1:] if m else []


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def rows_of(page: str) -> list[dict]:
    out = []
    for tr in re.findall(r"(?is)<tr>(.*?)</tr>", page):
        cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)
        button = re.search(r'name="([^"]+)" value="View PDF"', tr)
        if len(cells) >= 6 and button:
            c = [text(x) for x in cells]
            out.append(dict(serial=c[0], case=c[1], bench=c[2], author=c[3], parties=c[4], citation=c[5] or None,
                            button=button.group(1)))
    return out


def search(site: Site, field: str, value: str) -> tuple[str, list[dict]]:
    first = site.fetch().decode("utf-8", "replace")
    form = dict(hidden(first), **{P + "ddlCourt": "0", P + "ddlCaseyear": "0", P + "txtCaseNo": "",
                                  P + "btnSearch": "Search"})
    form[P + field] = value
    page = site.fetch(form).decode("utf-8", "replace")
    return page, rows_of(page)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/gbcc"))
    ap.add_argument("--delay", type=float, default=2.0)
    a = ap.parse_args()
    folder = a.out / "gbcc_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    site = Site(a.delay)
    start = site.fetch().decode("utf-8", "replace")
    queries = [("ddlCourt", v) for v in options(start, "ddlCourt")] + [("ddlCaseyear", v) for v in
                                                                         options(start, "ddlCaseyear")]
    listing: dict[str, dict] = {}
    for field, value in queries:
        _, rows = search(site, field, value)
        for r in rows:
            listing.setdefault(r["serial"], dict(r, query=f"{field}={value}"))
        print(f"{field} {value[:50]!r}: {len(rows)} rows ({len(listing)} distinct)", flush=True)
    with open(folder / "listing.jsonl", "w", encoding="utf-8") as f:
        for r in listing.values():
            f.write(json.dumps({k: v for k, v in r.items() if k != "button"}, ensure_ascii=False) + "\n")

    out, got, bad = [], 0, 0
    for r in listing.values():
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", f"gbcc_{r['serial']}") + ".pdf"
        path = folder / name
        status = "ok"
        if not (path.exists() and path.stat().st_size > 0):
            try:
                field, value = r["query"].split("=", 1)
                page, rows = search(site, field, value)          # a fresh result page: its button is valid
                btn = next((x["button"] for x in rows if x["serial"] == r["serial"]), None)
                data = site.fetch(dict(hidden(page), **{P + "ddlCourt": "0", P + "ddlCaseyear": "0",
                                                        P + field: value, P + "txtCaseNo": "", btn: "View PDF"}))
                if data.startswith(b"%PDF"):
                    path.write_bytes(data)
                    got += 1
                else:
                    status, bad = "not_a_pdf", bad + 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
        sha = hashlib.sha256(path.read_bytes()).hexdigest() if status == "ok" else ""
        out.append(dict(filename=name, url=f"{URL}#serial={r['serial']}", status=status, sha256=sha, case=r["case"],
                        author=r["author"], parties=r["parties"], citation=r["citation"]))
        print(f"{r['serial']} {status} {r['case']}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    zpath = a.out.parent.parent / "gbcc_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"gbcc_judgments/{p.name}")
    print(f"downloaded {got}, failed {bad}; archive {zpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
