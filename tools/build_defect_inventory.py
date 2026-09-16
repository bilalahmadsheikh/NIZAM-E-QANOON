"""Inventory every defect that withholds an instrument, with the pages to read.

Step 1 of the catalogue: one row per defect across every withheld canonical
instrument, each naming the exact source pages a reader must look at and the
text evidence the corpus already holds. It decides nothing and writes no corpus
row; it writes `.artifacts/catalogue/inventory.json` and renders any page image
that does not already exist (a PDF page never changes, so every earlier render
under .artifacts/ is reused by document and page).

Where to look, per defect:

  * contents gap -- the printed contents page, plus the body page where the
    label or heading is printed (text search, heading-corroborated first); when
    nothing matches, the pages between the nearest linked contents entries on
    either side (the place the section should be), capped at three;
  * S7 unit not yet read from source -- the demoted unit's page and the kept
    unit's page;
  * S7 unit already read -- no pages; the recorded source-verified observation
    is carried into the row.

    uv run python tools/build_defect_inventory.py --render
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from nizam.storage.db import connect

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path("/mnt/e/nizam-data")
OUT = ROOT / ".artifacts" / "catalogue"
RENDER_DIR = OUT / "pages"

WITHHELD = """
SELECT i.id::text, i.document_id, i.source_observation_id, coalesce(i.short_title, ''),
       d.page_count, b.object_key,
       (SELECT r.body_starts_page FROM segmentation_run r WHERE r.instrument_id = i.id
         ORDER BY r.run_at DESC LIMIT 1),
       (SELECT q.overall_outcome FROM v_document_quality_status q WHERE q.document_id = i.document_id)
  FROM instrument i
  JOIN document d ON d.id = i.document_id AND d.is_active
  JOIN blob b ON b.sha256 = d.sha256
 WHERE i.is_active AND i.duplicate_of IS NULL
   AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id = i.id)
 ORDER BY i.document_id, i.id
"""

GAPS = """
SELECT g.toc_entry_id, g.printed_label, coalesce(g.printed_heading, ''), g.source_page, g.ordinal
  FROM v_toc_gap_pending g WHERE g.instrument_id = %s ORDER BY g.ordinal
"""

NEIGHBOURS = """
SELECT e.ordinal, p.first_page, p.last_page, e.printed_label
  FROM instrument_toc_entry e JOIN provision p ON p.id = e.provision_id AND p.is_active
 WHERE e.instrument_id = %s AND e.provision_id IS NOT NULL
 ORDER BY e.ordinal
"""

S7 = """
SELECT s.id::text, s.printed_label, s.source_page, c.canonical_source_page,
       left(regexp_replace(coalesce(db.text, ''), '\\s+', ' ', 'g'), 300),
       left(regexp_replace(coalesce(kb.text, ''), '\\s+', ' ', 'g'), 300),
       (SELECT coalesce(sum(pb.chars), 0) FROM provision x
          JOIN provision_block pb ON pb.provision_id = x.id
         WHERE x.instrument_id = s.instrument_id AND x.is_active AND x.path <@ cand.path),
       a.resolution, a.review_basis, a.rationale
  FROM v_structural_adjudication_pending s
  JOIN segmentation_structural_candidate c ON c.id = s.id
  JOIN provision cand ON cand.id = s.candidate_provision_id
  LEFT JOIN text_block db ON db.id = s.source_block_id
  LEFT JOIN text_block kb ON kb.id = c.canonical_source_block_id
  LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id = s.id
 WHERE s.instrument_id = %s
 ORDER BY s.source_page, s.printed_label
"""

BODY_BLOCKS = """
SELECT page_no, text FROM text_block WHERE document_id = %s AND page_no >= %s ORDER BY reading_order
"""


def _index_existing_renders() -> dict[tuple[int, int], str]:
    index: dict[tuple[int, int], str] = {}
    for base in (ROOT / ".artifacts" / "toc-gap-review", ROOT / ".artifacts" / "s7-source", RENDER_DIR):
        if not base.exists():
            continue
        for png in base.glob("*.png"):
            m = re.match(r"^(?:audit-)?doc(\d+)\D.*?-p(\d+)(?:-\d+)?\.png$", png.name)
            if m:
                index.setdefault((int(m.group(1)), int(m.group(2))), str(png.relative_to(ROOT)).replace("\\", "/"))
    return index


def _render(object_key: str, doc: int, page: int) -> str | None:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    stem = RENDER_DIR / f"doc{doc}-p{page}"
    existing = sorted(RENDER_DIR.glob(f"doc{doc}-p{page}-*.png"))
    if not existing:
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "110", "-png",
                        str(CORPUS / object_key), str(stem)], check=False, capture_output=True)
        existing = sorted(RENDER_DIR.glob(f"doc{doc}-p{page}-*.png"))
    return str(existing[0].relative_to(ROOT)).replace("\\", "/") if existing else None


def _label_pattern(label: str) -> re.Pattern:
    loose = r"\s*".join(re.escape(ch) for ch in label.strip() if not ch.isspace())
    return re.compile(rf"(?:^|\n)\s*[\d*†]{{0,3}}\s*\[?\s*{loose}\s*[.,:]?\s", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    renders = _index_existing_renders()
    instruments = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute(WITHHELD)
        for (iid, doc, obs, title, pages, key, body_page, quality) in cur.fetchall():
            row = {"instrument_id": iid, "document_id": doc, "source_observation_id": obs,
                   "title": title, "page_count": pages, "object_key": key,
                   "body_starts_page": body_page, "quality": quality, "defects": []}
            cur.execute(NEIGHBOURS, (iid,))
            linked = cur.fetchall()
            cur.execute(BODY_BLOCKS, (doc, body_page or 1))
            body = cur.fetchall()
            cur.execute(GAPS, (iid,))
            for entry_id, label, heading, cpage, ordinal in cur.fetchall():
                pat = _label_pattern(label)
                hk = re.sub(r"[^a-z0-9]", "", heading.lower())[:24]
                hits = [(pg, t) for pg, t in body if pat.search(t)]
                agreeing = [(pg, t) for pg, t in hits if len(hk) >= 10 and hk in re.sub(r"[^a-z0-9]", "", t.lower())]
                hit = (agreeing or hits or [None])[0]
                look = {cpage} if cpage else set()
                evidence = None
                if hit:
                    look.add(hit[0])
                    i = pat.search(hit[1]).start()
                    evidence = " ".join(hit[1][i:i + 220].split())
                else:
                    before = [r for r in linked if r[0] < ordinal]
                    after = [r for r in linked if r[0] > ordinal]
                    lo = (before[-1][2] or before[-1][1]) if before else (body_page or 1)
                    hi = after[0][1] if after else min((pages or lo), lo + 2)
                    if lo and hi and hi >= lo:
                        span = list(range(lo, hi + 1))
                        look.update(span if len(span) <= 3 else [lo, hi])
                    elif lo:
                        look.add(lo)
                row["defects"].append({
                    "kind": "contents_gap", "toc_entry_id": entry_id, "label": label,
                    "printed_heading": heading, "contents_page": cpage,
                    "body_hit_page": hit[0] if hit else None, "body_hit_text": evidence,
                    "agreeing_heading": bool(agreeing and hit and hit in agreeing),
                    "pages": sorted(p for p in look if p)})
            cur.execute(S7, (iid,))
            for (cid, label, spage, kpage, demoted, kept, dsub, res, basis, rationale) in cur.fetchall():
                already = basis == "source_verified"
                row["defects"].append({
                    "kind": "s7_unit", "candidate_id": cid, "label": label,
                    "demoted_page": spage, "kept_page": kpage, "demoted_text": demoted,
                    "kept_text": kept, "demoted_subtree_chars": dsub,
                    "already_read": already,
                    "prior_resolution": res if already else None,
                    "prior_observation": rationale if already else None,
                    "pages": [] if already else sorted({p for p in (spage, kpage) if p})})
            if quality and quality != "passed":
                row["defects"].append({"kind": "quality_gate", "quality": quality, "pages": []})
            instruments.append(row)

    page_set = sorted({(r["document_id"], p) for r in instruments for d in r["defects"] for p in d["pages"]})
    keys = {r["document_id"]: r["object_key"] for r in instruments}
    missing = [(d, p) for d, p in page_set if (d, p) not in renders]
    if a.render:
        for n, (d, p) in enumerate(missing, 1):
            path = _render(keys[d], d, p)
            if path:
                renders[(d, p)] = path
            if n % 200 == 0:
                print(f"  rendered {n}/{len(missing)}", flush=True)
    for r in instruments:
        for d in r["defects"]:
            d["renders"] = []
            for p in d["pages"]:
                path = renders.get((r["document_id"], p))
                if path:
                    d["renders"].append({"page": p, "file": path,
                                         "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()})
    (OUT / "inventory.json").write_text(json.dumps(instruments, indent=1, ensure_ascii=False), encoding="utf-8")
    defects = [d for r in instruments for d in r["defects"]]
    print(f"withheld instruments : {len(instruments)}")
    print(f"defects              : {len(defects)}  "
          f"(gaps {sum(d['kind']=='contents_gap' for d in defects)}, "
          f"s7 {sum(d['kind']=='s7_unit' for d in defects)}, "
          f"s7 already read {sum(d.get('already_read', False) for d in defects)})")
    print(f"distinct pages       : {len(page_set)}  (had renders for {len(page_set) - len(missing)}, "
          f"{'rendered' if a.render else 'missing'} {len(missing)})")
    unrendered = sum(1 for dd in page_set if dd not in renders)
    print(f"pages still without an image: {unrendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
