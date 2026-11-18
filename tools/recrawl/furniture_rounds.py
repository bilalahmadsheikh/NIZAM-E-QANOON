"""furniture_rounds.py DUMP_DIR PATCH_DIR DRY_LOG OUT_DIR SUFFIX [DOC,DOC,...]

Narrow a page-furniture batch (D-085) to the readings that prove pure, one round at a time.

For every document whose rebuild failed the batch proof, write a reduced patch-<doc><SUFFIX>.json to OUT_DIR. The
reduced file drops the readings of every page where the rebuilt tree departs from the stored release, and keeps the
rest. A page is offending when any of these holds there:
  * a path is added or removed;
  * a kind, label, parent or heading changes;
  * text changes other than by deleting that document's furniture words.
Each such node's pages are taken from both the stored and the rebuilt row (first_page..last_page). A reading the dry
run reports as matching no block ("curation patch <id> matched 0 blocks") is dropped by its own page and locator.

Dropping a reading only leaves the furniture where it already is, so the next round's proof decides again. Prints one
line per document: the pages dropped and the readings kept. Read-only against the database.
"""
from __future__ import annotations

import difflib
import json
import pathlib
import re
import sys

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")


def head_words(readings: list[dict]) -> set[str]:
    words: set[str] = set()
    for r in readings:
        m = re.search(r"running head '(.*)' at its head", r.get("observed", ""), re.S)
        if m:
            words.update(w for w in re.split(r"\s+|/", m.group(1)) if w)
        m = re.search(r"prints its folio '(\d+)'", r.get("observed", ""))
        if m:
            words.add(m.group(1))
    return words


def span(row: dict | None) -> set[int]:
    if not row or row.get("first_page") is None:
        return set()
    a, b = int(row["first_page"]), int(row.get("last_page") or row["first_page"])
    return set(range(a, b + 1)) if b - a <= 4 else {a, b}   # a long node: its ends, where a page head sits


def offending_pages(dump_paths: list[pathlib.Path], words: set[str]) -> set[int]:
    pages: set[int] = set()
    for dp in dump_paths:
        d = json.loads(dp.read_text(encoding="utf-8"))
        f = d["fields"]
        stored = {r[0]: dict(zip(f, r)) for r in d["stored"]}
        built = {r[0]: dict(zip(f, r)) for r in d["built"]}
        for path in set(stored) ^ set(built):
            pages |= span(stored.get(path)) | span(built.get(path))
            parent = (stored.get(path) or built.get(path) or {}).get("parent")
            pages |= span(stored.get(parent)) & span(built.get(parent))
        for path in set(stored) & set(built):
            a, b = stored[path], built[path]
            bad = any((a.get(k) or "") != (b.get(k) or "") for k in ("kind", "label", "parent", "heading"))
            if not bad and (a.get("text") or "") != (b.get("text") or ""):
                x, y = (a.get("text") or "").split(), (b.get("text") or "").split()
                for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
                    if tag == "equal":
                        continue
                    if tag != "delete" or any(w not in words for w in x[i1:i2]):
                        bad = True
                        break
            if bad:
                pages |= span(a) | span(b)
    return pages


def zero_match_patches(dry_log: pathlib.Path) -> dict[int, set[str]]:
    """{doc: {patch uuid}} from the dry run's 'matched 0 blocks' errors."""
    out: dict[int, set[str]] = {}
    if dry_log.exists():
        for m in re.finditer(r"ERROR #(\d+): ValueError: curation patch ([0-9a-f-]{36}) matched 0 blocks",
                             dry_log.read_text(encoding="utf-8", errors="replace")):
            out.setdefault(int(m.group(1)), set()).add(m.group(2))
    return out


def main() -> int:
    dump_dir, patch_dir, dry_log, out_dir = map(pathlib.Path, sys.argv[1:5])
    suffix = sys.argv[5]
    only = {int(x) for x in sys.argv[6].split(",")} if len(sys.argv) > 6 and sys.argv[6] else None
    out_dir.mkdir(parents=True, exist_ok=True)
    zero = zero_match_patches(dry_log)
    zero_loc: dict[int, set[tuple[int, str]]] = {}
    if zero:
        from nizam.storage.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id::text, page_no, match_text FROM segmentation_curation_patch WHERE id = ANY(%s::uuid[])",
                        ([u for s in zero.values() for u in s],))
            byid = {i: (p, m) for i, p, m in cur.fetchall()}
        for doc, ids in zero.items():
            zero_loc[doc] = {byid[i] for i in ids if i in byid}
    for pf in sorted(patch_dir.glob(f"patch-*{suffix}.json")):
        doc = int(re.search(rf"patch-(\d+){suffix}", pf.name).group(1))
        if only is not None and doc not in only:
            continue
        readings = json.loads(pf.read_text(encoding="utf-8"))
        drop = offending_pages(sorted(dump_dir.glob(f"{doc}_*.json")), head_words(readings))
        kept = [r for r in readings
                if r["page_no"] not in drop and (r["page_no"], r["match_text"]) not in zero_loc.get(doc, set())]
        dropped = sorted({r["page_no"] for r in readings} - {r["page_no"] for r in kept})
        (out_dir / pf.name).write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{doc}: dropped pages {dropped} ; kept {len(kept)} of {len(readings)} readings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
