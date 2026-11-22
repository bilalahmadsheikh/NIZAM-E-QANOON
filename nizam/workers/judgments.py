"""Land one court's judgment archive: sources, readings, judgments (docs/PRECEDENT-MODEL.md §3, §7 step 3).

    uv run python -m nizam.workers.judgments --archive /mnt/e/nizam-data/scp_judgments.zip --court SC \
        --source-id pk-scp-judgments [--limit N] [--apply]

Without --apply nothing is written. The run prints what would land and why each held file is held.

1. Every PDF in the archive becomes a judgment_source row, with the portal URL where the archive's manifest gives
   one. Its bytes are kept under raw/judgments/<source_id>/<sha256>, never overwritten.
2. Each distinct file without an active reading is extracted (PyMuPDF, lane E2) and parsed. The extraction and
   parse run in parallel; the writes run one transaction per document in this process.
3. Each file gets a judgment_document whatever happened: parsed, held (with the gate it failed), needs_ocr,
   reporter_reprint or duplicate. A scanned file waits for the OCR lane (D-114).

Resumable: a file with an active reading is not read again unless --redo.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import os
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from nizam.corpus.judgment import PARSER, Held, parse_judgment
from nizam.shared.corpus_types import ExtractionRejected

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
_REF: tuple | None = None


def _manifest(z: zipfile.ZipFile) -> dict[str, tuple[str, str]]:
    """filename -> (url, status) from an archive's manifest.csv, preferring an 'ok' row."""
    out: dict[str, tuple[str, str]] = {}
    for name in z.namelist():
        if name.endswith("manifest.csv"):
            for r in csv.DictReader(io.StringIO(z.read(name).decode("utf-8", "replace"))):
                fn = r.get("filename") or ""
                if fn and (fn not in out or (out[fn][1] != "ok" and r.get("status") == "ok")):
                    out[fn] = (r.get("url") or None, r.get("status") or None)
    return out


def _init(ref):
    global _REF
    _REF = ref


def _read(args):
    """Extract and parse one file (in a worker process). Returns a picklable result."""
    archive, member, sha, court = args
    import pymupdf
    from nizam.corpus.extract import extract_pdf
    pymupdf.TOOLS.mupdf_display_errors(False)
    data = zipfile.ZipFile(archive).read(member)
    extractor = f"pymupdf-{getattr(pymupdf, '__version__', 'unknown')}"
    try:
        doc = extract_pdf(data, sha)
    except ExtractionRejected as exc:
        try:
            pages = pymupdf.open(stream=data, filetype="pdf").page_count or 1
        except Exception:                                       # noqa: BLE001
            pages = 1
        return dict(sha256=sha, extractor=extractor, lane="E4", language="en", page_count=pages, char_count=0,
                    blocks=[], outcome="needs_ocr", reason=f"no usable text layer: {exc}"[:500], detail={},
                    parsed=None)
    except Exception as exc:                                    # noqa: BLE001
        return dict(sha256=sha, extractor=extractor, lane="E2", language="en", page_count=1, char_count=0,
                    blocks=[], outcome="held", reason=f"unreadable PDF: {type(exc).__name__}: {exc}"[:500],
                    detail={}, parsed=None)
    aliases, types = _REF
    r = parse_judgment(doc, aliases, types, expected_court=court)
    common = dict(sha256=sha, extractor=doc.extractor, lane=doc.lane if doc.lane in ("E2", "E4") else "E2",
                  page_count=doc.page_count, char_count=doc.char_count, blocks=doc.blocks)
    if isinstance(r, Held):
        lang = "ur" if "Urdu" in r.reason else "en"
        return dict(common, language=lang, outcome=r.outcome, reason=r.reason, detail=r.detail, parsed=None)
    return dict(common, language="en", outcome="parsed", reason=None, detail=r.detail, parsed=r)


def main() -> int:
    ap = argparse.ArgumentParser(description="land a court's judgment archive (docs/PRECEDENT-MODEL.md §3)")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--court", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--redo", action="store_true",
                    help="re-read files read by an earlier parser (the earlier reading is retired, not deleted)")
    ap.add_argument("--held", metavar="GATE",
                    help="re-read only files whose active reading is held at this gate, e.g. J1 (D-124)")
    a = ap.parse_args()

    from nizam.storage import judgment_write as jw
    archive = Path(a.archive)
    z = zipfile.ZipFile(archive)
    manifest = _manifest(z)
    members = sorted(n for n in z.namelist() if n.lower().endswith(".pdf"))
    if a.limit:
        members = members[:a.limit]
    store = CORPUS_ROOT / "raw" / "judgments" / a.source_id
    rows, sha_of = [], {}
    for n in members:
        info = z.getinfo(n)
        data = z.read(n)
        sha = hashlib.sha256(data).hexdigest()
        sha_of[n] = sha
        url, status = manifest.get(n.split("/")[-1], (None, None))
        rows.append(dict(source_id=a.source_id, court_code=a.court, archive=archive.name, member=n, source_url=url,
                         url_status=status, sha256=sha, byte_length=len(data),
                         object_key=f"raw/judgments/{a.source_id}/{sha}",
                         observed_at=dt.datetime(*info.date_time, tzinfo=dt.timezone.utc)))
        if a.apply:
            target = store / sha
            if not target.exists():
                store.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(target)
    distinct = sorted(set(sha_of.values()))
    print(f"{len(members)} files, {len(distinct)} distinct, {len(manifest)} manifest names")
    if a.apply:
        print("sources added:", jw.record_sources(rows))
        todo = set(jw.unread_hashes(a.court, archive.name, parser=PARSER if a.redo else None, held_gate=a.held))
    elif a.held:
        todo = set(jw.unread_hashes(a.court, archive.name, held_gate=a.held))
    else:
        todo = set(distinct)
    first_member = {}
    for n in members:
        first_member.setdefault(sha_of[n], n)
    work = [(str(archive), first_member[s], s, a.court) for s in distinct if s in todo]
    print(f"to read: {len(work)}")

    ref = jw.reference_data()
    counts, reasons = collections.Counter(), collections.Counter()
    t0 = time.time()
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(ref,)) as ex:
        for k, res in enumerate(ex.map(_read, work, chunksize=4), 1):
            outcome = res["outcome"]
            if a.apply:
                _, outcome = jw.save_reading(court_code=a.court, parser=PARSER, **res)
            counts[outcome] += 1
            if outcome == "parsed" and res["parsed"].decided_on_basis == "undated":
                counts["parsed, undated"] += 1
            if outcome != "parsed":
                reasons[(outcome, (res["reason"] or "").split(":")[0][:70])] += 1
            if k % 200 == 0:
                print(f"  {k}/{len(work)} {dict(counts)} {time.time() - t0:.0f}s", flush=True)
    print("outcomes:", dict(counts))
    for (o, r), n in reasons.most_common():
        print(f"  {n:5} {o:17} {r}")
    if not a.apply:
        print("dry run: nothing written (add --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
