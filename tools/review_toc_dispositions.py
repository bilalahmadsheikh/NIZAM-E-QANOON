"""Prepare direct source evidence for omitted/repealed TOC entries.

This is deliberately a review tool, not an adjudicator.  A contents heading
that says ``Repeal and savings`` is usually a live operative section; one that
says ``[Omitted]`` is an editorial lifecycle marker.  Keyword matching alone
cannot safely distinguish them.  The tool therefore:

* selects only direct past-participle markers (omitted/repealed), never the
  noun/verb heading ``Repeal``;
* searches current non-contents blocks for a citation-equivalent body label;
* renders the exact printed contents block for source review; and
* writes a hash-addressed manifest.  It never writes corpus rows.

    ./nz disposition-review
    ./nz disposition-review --render

Governing contract: docs/02-corpus-and-ingestion.html sections 5 and 8.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from nizam.corpus.segment import _citation_label_key, _classify_body, subdivide
from nizam.storage.db import connect


ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
DEFAULT_OUT = ROOT / ".artifacts" / "toc-dispositions"

DIRECT_DISPOSITION = re.compile(
    r"^\s*(?:\d+\s*)?[\[(]*\s*(omitted|repealed)\b", re.I,
)

ENTRY_SQL = """
SELECT g.toc_entry_id,g.instrument_id::text,g.document_id,
       i.source_observation_id,g.short_title,g.jurisdiction::text,g.ordinal,
       g.printed_label,g.printed_heading,g.entry_kind,g.source_block_id,
       g.source_page,b.object_key,d.sha256,
       sb.x0,sb.y0,sb.x1,sb.y1,sb.text
  FROM v_toc_gap_pending g
  JOIN instrument i ON i.id=g.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
  JOIN document d ON d.id=g.document_id AND d.is_active
  JOIN blob b ON b.sha256=d.sha256
  LEFT JOIN text_block sb ON sb.id=g.source_block_id
 WHERE g.toc_entry_id IS NOT NULL
 ORDER BY g.document_id,g.source_page,g.ordinal,g.toc_entry_id
"""

BLOCK_SQL = """
WITH active_role AS (
  SELECT pb.block_id,array_agg(DISTINCT pb.role::text) AS roles
    FROM provision_block pb
    JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
   GROUP BY pb.block_id
), toc_source AS (
  SELECT DISTINCT e.source_block_id AS block_id
    FROM instrument_toc_entry e
    JOIN instrument i ON i.id=e.instrument_id
                     AND i.is_active AND i.duplicate_of IS NULL
   WHERE i.document_id=ANY(%s) AND e.source_block_id IS NOT NULL
)
SELECT b.document_id,b.id,b.page_no,b.text,coalesce(r.roles,ARRAY[]::text[]),
       (t.block_id IS NOT NULL) AS is_toc_source
  FROM text_block b
  JOIN document d ON d.id=b.document_id AND d.is_active
  LEFT JOIN active_role r ON r.block_id=b.id
  LEFT JOIN toc_source t ON t.block_id=b.id
 WHERE b.document_id=ANY(%s)
"""


def _equivalent_label_pattern(label: str) -> re.Pattern[str]:
    """Match 12A, 12-A and 12 A without matching 112A or 12AA."""
    compact = re.sub(r"[-\s]", "", label.strip())
    match = re.fullmatch(r"(\d+)([A-Za-z]+)?", compact)
    if not match:
        core = re.escape(label.strip())
    else:
        number, suffix = match.groups()
        core = re.escape(number)
        if suffix:
            core += r"\s*-?\s*" + re.escape(suffix)
    return re.compile(rf"(?<![0-9A-Za-z]){core}\s*[.)](?![0-9A-Za-z])", re.I)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render(entry: dict, output: Path, dpi: int) -> dict:
    pdf = CORPUS_ROOT / entry["object_key"]
    page = int(entry["source_page"])
    target = output / "pages" / (
        f"doc-{entry['document_id']}-page-{page}-block-"
        f"{entry['source_block_id']}.png"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    coordinates = [entry.get(key) for key in ("x0", "y0", "x1", "y1")]
    if not target.exists():
        command = [sys.executable, str(ROOT / "tools" / "render_pdf_page.py"),
                   str(pdf), str(page), str(target), "--dpi", str(dpi)]
        if all(value is not None for value in coordinates):
            x0, y0, x1, y1 = (float(value) for value in coordinates)
            # Include neighbouring print so the row is interpreted in context.
            command.extend(["--clip", f"{max(0,x0-24)},{max(0,y0-18)},{x1+24},{y1+18}"])
        subprocess.run(command, check=True, capture_output=True, text=True)
    return {
        "path": str(target.relative_to(ROOT)),
        "sha256": _sha256(target),
        "dpi": dpi,
        "clip": coordinates if all(value is not None for value in coordinates) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--record", action="store_true",
                        help="record the visually reviewed rendered entries")
    parser.add_argument("--reviewed-by",
                        default="openai.codex/rendered-source-review/1")
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(ENTRY_SQL)
        columns = [column.name for column in cur.description]
        entries = [dict(zip(columns, row)) for row in cur.fetchall()]
        entries = [entry for entry in entries
                   if DIRECT_DISPOSITION.match(entry["printed_heading"] or "")]
        document_ids = sorted({entry["document_id"] for entry in entries})
        cur.execute(BLOCK_SQL, (document_ids, document_ids))
        body_blocks: dict[int, list[dict]] = defaultdict(list)
        for document_id, block_id, page_no, text, roles, is_toc_source in cur.fetchall():
            # A block with any current non-contents assignment is admissible.
            # Unassigned blocks are also searched: the defect may be precisely
            # that segmentation never classified the body section.
            if is_toc_source or (roles and all(role == "contents" for role in roles)):
                continue
            body_blocks[document_id].append({
                "id": block_id, "page": page_no, "text": text, "roles": roles,
            })

    for entry in entries:
        hits = []
        for block in body_blocks[entry["document_id"]]:
            decisions = [
                decision
                for piece in subdivide(block["text"] or "")
                for decision in [_classify_body(
                    piece, {entry["printed_label"]: entry["printed_heading"] or ""},
                )]
                if decision is not None
                and decision[0] == "section"
                and _citation_label_key(decision[1])
                    == _citation_label_key(entry["printed_label"])
            ]
            if decisions:
                hits.append({
                    "block_id": block["id"], "page": block["page"],
                    "roles": block["roles"],
                    "parsed_labels": [decision[1] for decision in decisions],
                    "text": re.sub(r"\s+", " ", block["text"] or "")[:500],
                })
        entry["body_hits"] = hits[:20]
        # Schedule rows frequently repeat ordinary numbers (4, 31, 32 ...).
        # They are not the citable section promised by this TOC entry.  Keep
        # them visible as collisions, but never count them as recovered body
        # sections.  This distinction reproduces the 27/135 split that an
        # unrestricted label search obscures.
        section_hits = [hit for hit in hits
                        if "schedule_row" not in hit["roles"]]
        entry["body_section_hits"] = section_hits[:20]
        entry["schedule_label_collisions"] = [
            hit for hit in hits if "schedule_row" in hit["roles"]
        ][:20]
        entry["body_text_present"] = bool(section_hits)
        entry["classification"] = DIRECT_DISPOSITION.match(
            entry["printed_heading"] or "").group(1).lower()

    render_groups: dict[tuple, list[dict]] = defaultdict(list)
    for entry in entries:
        key = (entry["document_id"], entry["source_page"], entry["source_block_id"])
        render_groups[key].append(entry)
    if args.render or args.record:
        for group in render_groups.values():
            artifact = _render(group[0], args.output, args.dpi)
            for entry in group:
                entry["render_artifact"] = artifact

    manifest = {
        "contract": "docs/02-corpus-and-ingestion.html sections 5 and 8",
        "method": (
            "direct omitted/repealed heading; current non-contents body search; "
            "exact source-block render; no corpus writes"
        ),
        "counts": {
            "entries": len(entries),
            "documents": len({entry["document_id"] for entry in entries}),
            "source_pages": len({(entry["document_id"], entry["source_page"])
                                 for entry in entries}),
            "render_groups": len(render_groups),
            "body_text_present": sum(entry["body_text_present"] for entry in entries),
            "toc_only": sum(not entry["body_text_present"] for entry in entries),
            "schedule_label_collisions": sum(
                bool(entry["schedule_label_collisions"]) for entry in entries
            ),
        },
        "entries": entries,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                        default=str) + "\n", encoding="utf-8")
    inserted = unchanged = 0
    if args.record:
        # This flag is deliberately explicit: reaching this branch attests that
        # a reviewer has looked at every rendered source block in this manifest.
        # The actor and reviewer type remain honest; this is not labelled human.
        with connect() as conn, conn.cursor() as cur:
            refused = 0
            for entry in entries:
                artifact = entry.get("render_artifact")
                if not artifact:
                    raise RuntimeError("recording requires a rendered artifact")
                # A body that HAS text under this label contradicts the reading.
                # Document 2243's "entry" for label 3 is not a contents row at
                # all -- the render shows three FOOTNOTES, superscript markers
                # against amendment history:
                #
                #     2.  Subs Vide the Khyber Pakhtunkhwa Act.IV of 2011.
                #     3.  Omitted Vide Khyber Pakhtunkhwa Act No.XII of 1973.
                #
                # Recording that would assert section 3 of the Act was omitted,
                # on the evidence of a footnote about some other provision. The
                # detector already computes body_text_present and it is exactly
                # the signal that separates the two; it was not consulted here.
                if entry.get("body_text_present"):
                    refused += 1
                    continue
                citation_match = re.search(
                    r"\b(?:by|through)\s+(?:the\s+)?(.+)$",
                    entry["printed_heading"], re.I,
                )
                citation = citation_match.group(1).strip(" .") if citation_match else None
                cur.execute("""
                    SELECT id,printed_heading,source_block_id,source_page,render_sha256
                      FROM v_toc_disposition_assertion_latest
                     WHERE source_observation_id=%s AND expression_ordinal=0
                       AND source_block_id=%s AND printed_label=%s
                """, (entry["source_observation_id"],entry["source_block_id"],
                      entry["printed_label"]))
                previous = cur.fetchone()
                if (previous is not None
                        and previous[1] == entry["printed_heading"]
                        and previous[2] == entry["source_block_id"]
                        and previous[3] == entry["source_page"]
                        and previous[4] == artifact["sha256"]):
                    unchanged += 1
                    continue
                evidence = {
                    "visual_review": True,
                    "reviewer_type": "ai_assistant",
                    "detector": "direct-past-participle/1",
                    "source_heading_verbatim": entry["printed_heading"],
                    "render_artifact": artifact["path"],
                    "render_sha256": artifact["sha256"],
                    "body_section_hits": entry["body_section_hits"],
                    "schedule_label_collisions": entry["schedule_label_collisions"],
                }
                cur.execute("""
                    INSERT INTO toc_disposition_assertion
                        (source_observation_id,expression_ordinal,toc_entry_ordinal,
                         reviewed_toc_entry_id,printed_label,printed_heading,
                         disposition,source_block_id,source_page,render_artifact,
                         render_sha256,amending_instrument_citation,evidence,
                         reviewed_by,supersedes_id)
                    VALUES (%s,0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    entry["source_observation_id"],entry["ordinal"],
                    entry["toc_entry_id"],entry["printed_label"],
                    entry["printed_heading"],entry["classification"],
                    entry["source_block_id"],entry["source_page"],
                    artifact["path"],artifact["sha256"],citation,
                    json.dumps(evidence,ensure_ascii=False),args.reviewed_by,
                    previous[0] if previous is not None else None,
                ))
                inserted += 1
        print(f"assertions: {inserted} inserted, {unchanged} unchanged, "
              f"{refused} refused because the body has text under that label")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
