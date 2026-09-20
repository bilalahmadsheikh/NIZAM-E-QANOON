"""Turn a catalogue reader's "found elsewhere" note into a provision id.

`toc_gap_adjudication` records `found_elsewhere` only with the provision the
entry was found as. Readers write what they saw -- a label and a page, sometimes
phrased ("rule 9(2)", "section 15 (body's own printed number)", "SCHEDULE") --
so the id has to be resolved against the tree before any of it can be recorded.

This resolves, it does not decide. For every `found_elsewhere` row without a
`found_provision_id` it looks for an active provision of the same instrument
whose citation label matches, preferring one that starts on the page the reader
named. A unique match is written back into the result file; anything ambiguous
or missing is reported and left alone, because a wrong id would point a contents
entry at the wrong law.

    python tools/resolve_found_elsewhere.py            report only
    python tools/resolve_found_elsewhere.py --write    write the ids back
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

from nizam.storage.db import connect

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / ".artifacts/catalogue/results"

# "rule 9(2)" -> 9 ; "section 15 (body's own printed number)" -> 15 ;
# "SCHEDULE" -> SCHEDULE ; "12-A" -> 12-A
LABEL = re.compile(r"(?:^|\b)(?:rule|section|article|regulation|clause)?\s*"
                   r"([0-9]+(?:\s*[-–]\s*[A-Za-z]{1,3})?[A-Za-z]{0,3}|SCHEDULE|Schedule)")


def wanted_label(text: str | None) -> str | None:
    if not text:
        return None
    m = LABEL.search(text.strip())
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1)).upper()


def key(label: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (label or "").lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rows: list[tuple[pathlib.Path, int, dict]] = []
    for shard in sorted(RESULTS.glob("defects-*")):
        for path in sorted(shard.glob("doc*.json")):
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for i, row in enumerate(content):
                detail = row.get("fix_detail") or {}
                if row.get("fix") == "found_elsewhere" and not detail.get("found_provision_id"):
                    rows.append((path, i, row))

    print(f"{len(rows)} found_elsewhere rows without a provision id")
    resolved = ambiguous = missing = unparsed = 0
    edits: dict[pathlib.Path, list] = {}

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        for path, index, row in rows:
            detail = row.get("fix_detail") or {}
            label = wanted_label(detail.get("found_label")) or wanted_label(detail.get("found_kind"))
            page = detail.get("found_page")
            if label is None:
                unparsed += 1
                print(f"  ? {path.parent.name}/{path.name} label {row.get('label')!r}: "
                      f"cannot read a label out of {detail.get('found_label')!r}")
                continue
            cur.execute("""
                SELECT p.id::text, p.kind::text, p.label, p.first_page,
                       (p.parent_id IS NULL) AS top_level
                  FROM provision p
                  JOIN instrument i ON i.id = p.instrument_id
                                   AND i.is_active AND i.duplicate_of IS NULL
                 WHERE i.document_id = %s AND p.is_active
                   AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') = %s
                 ORDER BY (p.first_page = %s) DESC, p.ordinal
            """, (row["document_id"], key(label), page))
            found = cur.fetchall()
            # A contents entry promises a top-level unit, so a sub-unit that
            # happens to carry the same number is not a candidate. This is what
            # separates "section 6 on page 3" from "sub-section (6) on page 3".
            if len(found) > 1:
                narrowed = [f for f in found if f[4]]
                if page is not None and any(f[3] == page for f in narrowed):
                    narrowed = [f for f in narrowed if f[3] == page]
                if narrowed:
                    found = narrowed
            if not found:
                missing += 1
                print(f"  - {path.parent.name}/{path.name} label {row.get('label')!r}: "
                      f"no active provision labelled {label!r} in document {row['document_id']}")
                continue
            on_page = [f for f in found if page is not None and f[3] == page]
            pick = on_page[0] if len(on_page) == 1 else (found[0] if len(found) == 1 else None)
            if pick is None:
                ambiguous += 1
                where = ", ".join(f"{f[1]} {f[2]} p{f[3]}" for f in found[:5])
                print(f"  ! {path.parent.name}/{path.name} label {row.get('label')!r}: "
                      f"{len(found)} provisions labelled {label!r} ({where}) -- page {page} does not separate them")
                continue
            resolved += 1
            detail["found_provision_id"] = pick[0]
            detail["resolved_by"] = {
                "tool": "tools/resolve_found_elsewhere.py",
                "matched_label": pick[2], "matched_kind": pick[1], "matched_first_page": pick[3],
                "reader_said": {"found_label": detail.get("found_label"), "found_page": page},
            }
            row["fix_detail"] = detail
            edits.setdefault(path, []).append((index, row))

    print(f"\nresolved {resolved}, ambiguous {ambiguous}, not found {missing}, unreadable label {unparsed}")
    if a.write and edits:
        for path, changes in edits.items():
            content = json.loads(path.read_text(encoding="utf-8"))
            for index, row in changes:
                content[index] = row
            path.write_text(json.dumps(content, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote ids into {len(edits)} result files")
    elif edits:
        print("(dry run: pass --write to store the ids)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
