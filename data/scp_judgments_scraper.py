"""Crawl the Supreme Court of Pakistan's open judgment listing (scp.gov.pk), D-139, D-144.

    python3 -I data/scp_judgments_scraper.py [--out /mnt/e/nizam-data/acquire/scp] [--delay 3]
                                             [--retry-manifest /mnt/e/nizam-data/scp_judgments.zip]

What the site serves without a block (surveyed 25 Nov 2026):

  * www.supremecourt.gov.pk answers 403 (an Akamai denial) to every path, robots.txt included; www.scp.gov.pk is the
    court's site. Its robots.txt allows every path to a generic client and signals search=yes, ai-train=no,
    use=reference (D-144: this court's text never enters a training set).
  * /LatestJudgments: the last 25 judgments uploaded, one table row each (subject, case number, title, author judge,
    judgment date, upload date, citation, SC citation, file). It is the only open listing. The judgment search
    (/JudgmentsSearch) is protected by reCAPTCHA and is NOT used: a block is never circumvented (D-139).
  * /Judgments/<file>.pdf: each file. The September archive's files (scp_judgments.zip, fetched from the older
    www.supremecourt.gov.pk/downloads_judgements/) are served here under the same file names, so the files that
    archive's manifest records as failed are fetched again from here (--retry-manifest).

Run it again later and it adds what the listing has gained: files already under --out are kept (listing.jsonl
accumulates every row ever seen). Polite by construction: one request at a time, --delay seconds apart, a generic
client name and nothing that identifies the project or its people. Writes, under --out:

  scp_site_judgments/<file>.pdf        the PDFs as served
  scp_site_judgments/listing.jsonl     every listing row seen, with the date it was seen
  scp_site_judgments/manifest.csv      filename, url, status, sha256 (read by nizam.workers.judgments)
  scp_site_judgments.zip               the folder, for `nizam.workers.judgments --member-prefix scp_site_judgments/`
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www.scp.gov.pk"
UA = "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"
FIELDS = ("subject", "case_number", "title", "author_judge", "judgment_date", "upload_date", "citation",
          "sc_citation")


def get(url: str, timeout: int = 90) -> bytes:
    # a listed file name may hold a space ('ICA3 &4-2011DT2011.pdf', D-148): the last segment is percent-encoded
    head, _, name = url.rpartition("/")
    url = f"{head}/{urllib.parse.quote(urllib.parse.unquote(name), safe='&')}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _cell(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def listing_rows(page: str) -> list[dict]:
    """The rows of the latest-judgments table: ten cells each, the last holding the file link. A row classed
    'has-tagline' is followed by a 'tagline-row' holding the court's one-line tagline, kept in the listing record (the
    court's own words, not a reporter's headnote; read for nothing, D-120)."""
    rows = []
    for tr, tag in re.findall(r'<tr class="\s*data-row[^"]*">(.*?)</tr>(\s*<tr class="tagline-row">.*?</tr>)?',
                              page, re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S)
        link = re.search(r'href="([^"]+\.pdf)"', tr, re.I)
        if len(cells) != 10 or not link:
            raise ValueError(f"unexpected listing row ({len(cells)} cells): {_cell(tr)[:120]!r}")
        row = dict(zip(FIELDS, (_cell(c) for c in cells[1:9])))
        url = urllib.parse.urljoin(BASE + "/", html.unescape(link.group(1)))
        row.update(url=url, filename=urllib.parse.unquote(url.rsplit("/", 1)[-1]), tagline=_cell(tag))
        rows.append(row)
    n_links = len(set(re.findall(r'href="([^"]+\.pdf)"', page, re.I)))
    if len({r["url"] for r in rows}) != n_links:
        raise ValueError(f"{len(rows)} listing rows read, but the page links {n_links} files")
    return rows


def retry_rows(archive: Path) -> list[dict]:
    """Files the September archive's manifest records as failed and which that archive does not hold."""
    with zipfile.ZipFile(archive) as z:
        held = {n.rsplit("/", 1)[-1].lower() for n in z.namelist() if n.lower().endswith(".pdf")}
        name = next(n for n in z.namelist() if n.endswith("manifest.csv"))
        old = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))
    out, seen = [], set()
    for r in old:
        f = r["filename"]
        if r["status"] == "error" and f.lower() not in held and f.lower() not in seen:
            seen.add(f.lower())
            out.append(dict(filename=f, url=f"{BASE}/Judgments/{urllib.parse.quote(f)}", retried_from=r["url"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/mnt/e/nizam-data/acquire/scp"))
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--retry-manifest", type=Path, default=None)
    a = ap.parse_args()
    folder = a.out / "scp_site_judgments"
    folder.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    rows = listing_rows(get(f"{BASE}/LatestJudgments").decode("utf-8", "replace"))
    print(f"listing: {len(rows)} rows", flush=True)
    seen_path = folder / "listing.jsonl"
    seen = [json.loads(ln) for ln in seen_path.read_text(encoding="utf-8").splitlines()] if seen_path.exists() else []
    known = {(r["url"], r["upload_date"]) for r in seen}
    with open(seen_path, "a", encoding="utf-8") as f:
        for r in rows:
            if (r["url"], r["upload_date"]) not in known:
                f.write(json.dumps(dict(r, seen_on=today), ensure_ascii=False) + "\n")
    wanted = {r["filename"].lower(): r for r in seen + rows}
    if a.retry_manifest:
        retry = retry_rows(a.retry_manifest)
        print(f"retry from {a.retry_manifest.name}: {len(retry)} files", flush=True)
        for r in retry:
            wanted.setdefault(r["filename"].lower(), r)

    out, got, kept, bad = [], 0, 0, 0
    for r in wanted.values():
        path = folder / r["filename"]
        status, sha = "ok", None
        if path.exists():
            kept += 1
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            try:
                data = get(r["url"])
                if not data.startswith(b"%PDF"):
                    status, bad = "not_a_pdf", bad + 1
                else:
                    path.write_bytes(data)
                    sha = hashlib.sha256(data).hexdigest()
                    got += 1
            except Exception as exc:                            # noqa: BLE001
                status, bad = f"error: {type(exc).__name__}: {exc}"[:200], bad + 1
            time.sleep(a.delay)
        out.append(dict(filename=r["filename"], url=r["url"], status=status, sha256=sha or "",
                        case_number=r.get("case_number", ""), judgment_date=r.get("judgment_date", ""),
                        upload_date=r.get("upload_date", ""), author_judge=r.get("author_judge", ""),
                        retried_from=r.get("retried_from", "")))
        print(f"{len(out)}/{len(wanted)} {status} {r['filename']}", flush=True)
    with open(folder / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    zpath = a.out / "scp_site_judgments.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
        for p in sorted(folder.iterdir()):
            z.write(p, f"scp_site_judgments/{p.name}")
    print(f"downloaded {got}, already held {kept}, failed {bad}; archive {zpath}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
