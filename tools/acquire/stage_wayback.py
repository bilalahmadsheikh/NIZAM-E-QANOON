"""stage_wayback.py --out DIR --host HOST --prefix PATH [--prefix PATH ...] [--name REGEX] : stage an official host's
law PDFs from the Internet Archive's captures of that host, verified against the archive's own digest (no DB).

WHY (lead, 16 Nov 2026). Gilgit-Baltistan's laws are published on official hosts that this corpus cannot fetch today:
gba.gov.pk (the GB Assembly's site, where its Acts are filed under /gba/gba/tables/alldocuments/actdocx/) presents a
TLS certificate that has EXPIRED -- and TLS is never bypassed here (stage_candidates.py, 14 Nov 2026) -- while
gbassembly.gbit.gov.pk and gilgitbaltistan.gov.pk refuse connections (probed 16 Nov 2026 from two network stacks;
pakistancode.gov.pk and law.gok.pk answered from the same host). gbassembly.gbit.gov.pk's own listing linked 26 PDFs
that answered 404 on 14 Nov (acquisition_exception rows). The Internet Archive captured these files from the official
hosts when they served them. docs/02 §3.1 does not name an archive route; this tool is that route, recorded in
docs/SCHEMA.md (Territories):

  * the CDX index of web.archive.org is asked for the host's PDF captures under the given path prefixes that answered
    200 (statuscode:200, mimetype:application/pdf);
  * one capture per distinct payload: the archive's digest (SHA-1, base32) identifies the bytes; the latest capture of
    a digest is taken, and a file captured under several URLs is staged once;
  * the RAW capture is fetched (https://web.archive.org/web/<timestamp>id_/<original>: the bytes as the official host
    served them, no archive banner), TLS verified, a generic client name sent;
  * the bytes are accepted ONLY when their SHA-1 equals the digest the archive recorded at capture time and they are
    a PDF; anything else is a row with the error, never a file;
  * each row keeps the official URL (pdf_url, detail_url: the URL the official host served the file at) and the
    archive's evidence (archive_url, archive_timestamp, archive_digest), which tools/recrawl/land_missing.py writes into
    source_metadata.archived_capture. The landed observation's canonical_url is the OFFICIAL url; its provenance says
    the bytes came from the archive's capture of it, never that the official host was fetched today.

The output is stage_candidates.py's (DIR/staged.csv, DIR/files/<sha256>.pdf, the same grade), so
preflight_segment.py and select_landing.py read it unchanged.

    python tools/acquire/stage_wayback.py --out DIR --host gba.gov.pk --prefix /gba/gba/tables/alldocuments/actdocx/
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 (compatible; legal-research-crawler/1.0)"}
# stage_candidates.py's columns and grade, without importing it (it needs requests, which this venv does not carry)
FIELDS = ["portal", "kind", "year_or_dept", "title", "detail_url", "pdf_url", "status", "http_status", "content_type",
          "bytes", "sha256", "pages", "median_chars", "empty_pages", "printable", "latin_share", "grade", "first_line",
          "error"]


def grade(pdf: Path) -> dict:
    """The same grade as tools/acquire/stage_candidates.py (kept identical; see that module)."""
    import statistics
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


def get(url: str, timeout: int = 300) -> tuple[int, str, bytes]:
    """(status, content type, body); TLS verified (urllib's default context)."""
    try:
        with urlopen(Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except HTTPError as e:
        return e.code, e.headers.get("content-type", "") if e.headers else "", e.read() or b""
CDX = "https://web.archive.org/cdx/search/cdx"
RAW = "https://web.archive.org/web/{ts}id_/{orig}"
ARCHIVE_FIELDS = ["archive_url", "archive_timestamp", "archive_digest"]
YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def sha1_base32(data: bytes) -> str:
    return base64.b32encode(hashlib.sha1(data).digest()).decode()


def title_from(orig: str) -> str:
    """A readable title from the official file name: '2019-02-26 14:34:12gb-envirment-protection-act-2016.pdf' ->
    'gb envirment protection act 2016'; a Laravel name '<random>-meta<base64 of the original name>-.pdf' is decoded."""
    name = unquote(orig.rsplit("/", 1)[-1])
    name = re.sub(r"^files\?file=", "", name)
    m = re.search(r"-meta([A-Za-z0-9+/=]+)-\.pdf$", name)
    if m:
        try:
            name = base64.b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4)).decode("utf-8", "replace")
        except ValueError:
            pass
    name = re.sub(r"(?i)\.pdf$", "", name)
    name = re.sub(r"^\d{4}-\d{2}-\d{2}[ _]\d{2}[:_]\d{2}[:_]\d{2}", "", name)   # the upload stamp before the name
    return " ".join(re.sub(r"[-_]+", " ", name).split())


def captures(host: str, prefixes: list[str], name: re.Pattern | None) -> list[dict]:
    out, seen_digest = {}, set()
    q = urlencode([("url", f"{host}/*"), ("output", "json"), ("filter", "statuscode:200"),
                   ("filter", "mimetype:application/pdf"), ("fl", "timestamp,original,digest,length")])
    status, _ct, body = get(f"{CDX}?{q}")
    if status != 200:
        raise RuntimeError(f"CDX answered {status}")
    rows = json.loads(body or b"[]")[1:]
    for ts, orig, digest, length in sorted(rows, key=lambda x: x[0], reverse=True):     # latest capture first
        path = unquote(re.sub(r"^https?://[^/]+(:\d+)?", "", orig))
        if not any(path.lower().startswith(p.lower()) for p in prefixes):
            continue
        title = title_from(orig)
        if name and not name.search(title):
            continue
        if digest in seen_digest:
            continue
        seen_digest.add(digest)
        out[digest] = {"ts": ts, "orig": orig, "digest": digest, "title": title}
    return list(out.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--host", required=True)
    ap.add_argument("--prefix", action="append", required=True)
    ap.add_argument("--name", help="keep only captures whose title matches this regular expression")
    ap.add_argument("--portal", default="gb")
    ap.add_argument("--kind", default="act")
    a = ap.parse_args()
    files = a.out / "files"; files.mkdir(parents=True, exist_ok=True)
    dst = a.out / "staged.csv"
    done = {}
    if dst.exists():
        with dst.open(encoding="utf-8", newline="") as fh:
            done = {r["archive_digest"]: r for r in csv.DictReader(fh) if r.get("sha256")}
    caps = captures(a.host, a.prefix, re.compile(a.name, re.I) if a.name else None)
    print(f"{len(caps)} distinct captured files under {a.prefix}", flush=True)
    out = []
    for c in caps:
        if c["digest"] in done:
            out.append(done[c["digest"]]); continue
        raw = RAW.format(ts=c["ts"], orig=c["orig"])
        y = YEAR.findall(c["title"])
        row = {k: "" for k in FIELDS + ARCHIVE_FIELDS}
        row.update(portal=a.portal, kind=a.kind, year_or_dept=y[-1] if y else "", title=c["title"],
                   detail_url=c["orig"], pdf_url=c["orig"], archive_url=raw, archive_timestamp=c["ts"],
                   archive_digest=c["digest"])
        try:
            got = None
            for n in range(4):
                try:
                    got = get(raw)
                    if got[0] in (429, 503):
                        time.sleep(30 * (n + 1)); continue
                    break
                except (URLError, TimeoutError, OSError):
                    time.sleep(15 * (n + 1))
            if got is None:
                raise RuntimeError("archive did not answer")
            code, ctype, body = got
            row.update(http_status=code, content_type=ctype, bytes=len(body))
            if code != 200 or not body.startswith(b"%PDF"):
                row.update(status="not_pdf", grade="not_pdf", error=body[:120].decode("latin-1", "replace"))
            elif sha1_base32(body) != c["digest"]:
                row.update(status="digest_mismatch", grade="digest_mismatch",
                           error=f"sha1 {sha1_base32(body)} != archive digest {c['digest']}")
            else:
                h = hashlib.sha256(body).hexdigest(); p = files / f"{h}.pdf"; p.write_bytes(body)
                row.update(status="staged", sha256=h, **grade(p))
        except Exception as e:  # recorded, never fatal
            row.update(status="error", grade="error", error=f"{type(e).__name__}: {e}"[:200])
        out.append(row)
        print(f"{row['grade']:15} {row['title'][:90]}", flush=True)
        time.sleep(3)
    with dst.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS + ARCHIVE_FIELDS, extrasaction="ignore"); w.writeheader()
        w.writerows(out)
    by: dict = {}
    for r in out:
        by[r["grade"]] = by.get(r["grade"], 0) + 1
    print(by, "->", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
