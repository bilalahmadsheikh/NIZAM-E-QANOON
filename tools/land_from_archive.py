"""Land an unacquired law from the operator's own August portal archive.

Five zips under data/ hold what the portals served on 17 August 2026, a month
before the September scrape. The federal site names its files by content hash
and rotates them, so a URL cached in August 404s in September even where the Act
is still published -- and the August copy of that Act is sitting in the archive.

This is not a fetch. The provenance recorded says exactly that: the bytes came
from a local archive of the portal, with the archive's name and the entry path,
so nobody later mistakes it for a live download.

MATCHING IS DELIBERATELY STRICT. Titles alone are not identity: "PROVINCIAL
MOTOR VEHICLES (AMENDMENT) ACT, 2020" scores 0.98 against the 2021 Act and they
are different laws, and "ISRA UNIVERSITY ACT, 1997" is not the Ordinance of the
same name and year. A candidate is accepted only when the normalised titles
agree closely, the years agree, the instrument kind agrees, and the file opens
as a readable PDF. Everything else is reported and left alone.

Nothing is overwritten. The failed observation stays exactly as it is; a new
landed observation is appended beside it, as the HTTP recovery worker does.

    ./nz land-archive            dry run: what it would land
    ./nz land-archive --apply    land them
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import re
import tempfile
import zipfile
from difflib import SequenceMatcher

import pymupdf

from nizam.storage.db import connect

CORPUS_ROOT = pathlib.Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
DATA = pathlib.Path("data")
ARCHIVE_TAKEN = "2026-08-17"
PORTAL_ZIP = {
    "pk-federal": "Federal Laws-20260817T002958Z-1-001.zip",
    "pk-sindh": "sindh_code-20260817T003015Z-1-001.zip",
    "pk-punjab": "punjab_code-20260817T003007Z-1-001.zip",
    "pk-balochistan": "balochistan_code-20260817T002957Z-1-001.zip",
    "pk-kp": "kp_code-20260817T002959Z-1-001.zip",
}
YEAR = re.compile(r"\b(1[89]\d{2}|20[0-4]\d)\b")
KINDS = ("regulation", "rules", "ordinance", "order", "notification", "act")


def norm(value: str) -> str:
    value = re.sub(r"\.pdf$", "", value.lower())
    value = re.sub(r"\((?:repeal|repealed|under review|same as)[^)]*\)", " ", value)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def kind_of(text: str) -> str:
    low = text.lower()
    return next((k for k in KINDS if k in low), "")


def unresolved() -> list[tuple]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT o.id, o.source_id, o.canonical_url, o.referring_url,
                   o.source_metadata
              FROM v_acquisition_exception_latest e
              JOIN source_observation o ON o.id = e.source_observation_id
             ORDER BY o.id
        """)
        return cur.fetchall()


def match(rows: list[tuple], threshold: float) -> tuple[list[dict], list[str]]:
    accepted: list[dict] = []
    notes: list[str] = []
    for portal, name in PORTAL_ZIP.items():
        wanted = [r for r in rows if r[1] == portal]
        path = DATA / name
        if not wanted or not path.exists():
            continue
        with zipfile.ZipFile(path) as zf:
            keyed = [(norm(pathlib.PurePosixPath(n).name), n)
                     for n in zf.namelist() if n.lower().endswith(".pdf")]
            for observation_id, source_id, url, referring, metadata in wanted:
                title = (metadata or {}).get("title") or ""
                want = norm(title)
                if not want:
                    continue
                best, score = None, 0.0
                for key, orig in keyed:
                    ratio = 1.0 if key == want else SequenceMatcher(None, want, key).ratio()
                    if ratio > score:
                        best, score = orig, ratio
                if best is None or score < threshold:
                    continue
                filename = pathlib.PurePosixPath(best).name
                want_kind, file_kind = kind_of(title), kind_of(filename)
                if want_kind and file_kind and want_kind != file_kind:
                    notes.append(f"obs {observation_id}: kind {want_kind} vs "
                                 f"{file_kind} -- {filename[:54]}")
                    continue
                want_years = set(YEAR.findall(title))
                file_years = set(YEAR.findall(filename))
                if want_years and file_years and not (want_years & file_years):
                    notes.append(f"obs {observation_id}: year "
                                 f"{sorted(want_years)} vs {sorted(file_years)} "
                                 f"-- {filename[:54]}")
                    continue
                data = zf.read(best)
                try:
                    doc = pymupdf.open(stream=io.BytesIO(data), filetype="pdf")
                    pages = doc.page_count
                    doc.close()
                except Exception as exc:                       # noqa: BLE001
                    notes.append(f"obs {observation_id}: unreadable "
                                 f"({type(exc).__name__}) -- {filename[:44]}")
                    continue
                if pages < 1:
                    notes.append(f"obs {observation_id}: zero pages -- {filename[:44]}")
                    continue
                accepted.append({
                    "observation_id": observation_id, "source_id": source_id,
                    "canonical_url": url, "referring_url": referring,
                    "metadata": metadata or {}, "title": title,
                    "archive": name, "entry": best, "score": score,
                    "pages": pages, "data": data,
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
    return accepted, notes


def store(source_id: str, digest: str, data: bytes) -> str:
    rel = f"raw/{source_id}/{digest}"
    dest = CORPUS_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"content-address collision at {dest}")
        return rel
    tmp_dir = CORPUS_ROOT / "recovery" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="archive-", dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, dest)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return rel


def land(item: dict) -> str:
    object_key = store(item["source_id"], item["sha256"], item["data"])
    provenance = (f"local archive {item['archive']} entry {item['entry']}; "
                  f"portal copy taken {ARCHIVE_TAKEN}")
    metadata = dict(item["metadata"])
    metadata["recovery_of"] = item["observation_id"]
    metadata["recovered_from"] = "operator archive, not a live fetch"
    metadata["archive"] = item["archive"]
    metadata["archive_entry"] = item["entry"]
    metadata["archive_taken_on"] = ARCHIVE_TAKEN
    metadata["title_match_score"] = round(item["score"], 4)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO acquisition_attempt
              (source_observation_id,requested_url,final_url,http_status,media_type,
               byte_length,response_sha256,object_key,outcome,error)
            VALUES (%s,%s,%s,NULL,'application/pdf',%s,%s,%s,'recovered',NULL)
        """, (item["observation_id"], provenance, item["canonical_url"],
              len(item["data"]), item["sha256"], object_key))
        cur.execute("""
            INSERT INTO blob (sha256,source_id,object_key,byte_length,media_type,first_seen)
            VALUES (%s,%s,%s,%s,'application/pdf',now())
            ON CONFLICT (sha256) DO NOTHING
        """, (item["sha256"], item["source_id"], object_key, len(item["data"])))
        cur.execute("""
            INSERT INTO source_observation
              (source_id,canonical_url,referring_url,discovered_at,fetched_at,
               http_status,media_type,byte_length,sha256,object_key,
               scraper_version,source_metadata,outcome)
            VALUES (%s,%s,%s,now(),now(),NULL,'application/pdf',%s,%s,%s,
                    'land-from-archive/1',%s,'landed')
            ON CONFLICT DO NOTHING
        """, (item["source_id"], item["canonical_url"], item["referring_url"],
              len(item["data"]), item["sha256"], object_key,
              json.dumps(metadata, ensure_ascii=False)))
    return object_key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.90,
                    help="minimum normalised-title similarity (default 0.90)")
    a = ap.parse_args()

    rows = unresolved()
    accepted, notes = match(rows, a.threshold)
    print(f"unresolved acquisitions: {len(rows)}")
    print(f"archive candidates accepted at >= {a.threshold}: {len(accepted)}\n")
    for item in accepted:
        print(f"  obs {item['observation_id']:<6} {item['source_id']:<15} "
              f"match {item['score']:.2f}  {item['pages']:>3} pages  "
              f"{len(item['data'])/1024:>6.0f} KB")
        print(f"    {item['title'][:72]}")
        print(f"    {item['entry']}")
    if notes:
        print(f"\n  rejected on evidence ({len(notes)}):")
        for note in notes:
            print(f"    {note}")
    if not a.apply:
        print("\ndry run -- pass --apply to land these")
        return 0
    for item in accepted:
        key = land(item)
        print(f"  landed obs {item['observation_id']} -> {key}")
    print(f"\nlanded {len(accepted)}; run extract, verify and segment next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
