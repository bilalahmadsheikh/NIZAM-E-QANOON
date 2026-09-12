"""Rebuild one manifest for every rendered contents-gap page.

``tools/review_toc_gaps.py`` writes ``manifest.json`` fresh on each invocation,
so driving it one document at a time -- the only way to target a chosen set --
keeps every PNG but keeps only the last document's manifest. The renders are the
expensive part and they are all on disk; the manifest is derivable from them.

This walks the rendered files, re-hashes each one (the hash is a property of the
file, not of the run that made it), joins them back to the gap queue, and writes
a single manifest a decision can cite in its ``render_artifact``. It renders
nothing and touches no corpus row.

A file whose gap is no longer pending is kept and flagged ``gap_closed_since``:
the render still evidences what the page showed when it was taken, and deleting
it would discard evidence.

    ./nz toc-manifest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

from nizam.storage.db import connect

OUT = pathlib.Path(".artifacts/toc-gap-review")
NAME = re.compile(r"^doc(?P<document>\d+)-e(?P<entry>\d+|None)"
                  r"-label(?P<label>.+)-p(?P<page>\d+)\.png$")

PENDING = """
SELECT g.toc_entry_id, g.document_id, g.instrument_id::text, g.printed_label,
       g.printed_heading, g.source_page, i.short_title,
       i.source_observation_id
  FROM v_toc_gap_pending g
  JOIN instrument i ON i.id = g.instrument_id
 WHERE g.toc_entry_id IS NOT NULL
"""


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT / "manifest.json"))
    a = ap.parse_args()

    files = sorted(OUT.glob("*.png"))
    if not files:
        print(f"no rendered pages under {OUT}")
        return 1

    with connect() as conn, conn.cursor() as cur:
        cur.execute(PENDING)
        keys = ("toc_entry_id", "document_id", "instrument_id", "printed_label",
                "printed_heading", "contents_page", "short_title",
                "source_observation_id")
        pending = {r[0]: dict(zip(keys, r)) for r in cur.fetchall()}

    by_entry: dict[tuple, dict] = {}
    unparsed = []
    for path in files:
        match = NAME.match(path.name)
        if not match:
            unparsed.append(path.name)
            continue
        document_id = int(match["document"])
        entry = match["entry"]
        entry_id = None if entry == "None" else int(entry)
        key = (document_id, entry_id, match["label"])
        record = by_entry.setdefault(key, {
            "toc_entry_id": entry_id,
            "document_id": document_id,
            "printed_label": match["label"],
            "renders": [],
        })
        record["renders"].append({
            "page": int(match["page"]),
            "file": str(path).replace("\\", "/"),
            "sha256": digest(path),
        })

    manifest = []
    closed = 0
    for record in by_entry.values():
        record["renders"].sort(key=lambda item: item["page"])
        record["searched_pages"] = [r["page"] for r in record["renders"]]
        row = pending.get(record["toc_entry_id"])
        if row is None:
            record["gap_closed_since"] = True
            closed += 1
        else:
            record["gap_closed_since"] = False
            record["instrument_id"] = row["instrument_id"]
            record["source_observation_id"] = row["source_observation_id"]
            record["short_title"] = row["short_title"]
            record["printed_heading"] = row["printed_heading"]
            record["contents_page"] = row["contents_page"]
        manifest.append(record)

    manifest.sort(key=lambda item: (item["document_id"],
                                    str(item["printed_label"])))
    path = pathlib.Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    pages = sum(len(item["renders"]) for item in manifest)
    print(f"page images        : {len(files)}")
    print(f"gaps covered       : {len(manifest)} in "
          f"{len({item['document_id'] for item in manifest})} documents")
    print(f"pages in manifest  : {pages}")
    print(f"already closed     : {closed}")
    if unparsed:
        print(f"unparsed filenames : {len(unparsed)} (e.g. {unparsed[0]})")
    print(f"written            : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
