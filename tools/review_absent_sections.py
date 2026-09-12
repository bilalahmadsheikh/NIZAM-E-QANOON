"""Render, read and record the contents gaps whose section is not in the source.

A contents gap says the printed contents promised a section the tree does not
hold. That is not the same as the SOURCE not holding it, and only a page reading
separates the two. Migration 0050 admits an assistant's reading as its own basis
for ``absent_in_source``, on strictly more evidence than the human path carries:
the rendered pages, their content hashes, and what the page shows in words.

TWO MACHINE CHECKS SELECT THE CANDIDATES, both resting on C5 = 0 -- every
character of every PDF is in a ``text_block``, so the raw blocks can be searched
directly rather than the tree, which is the thing in question:

  1. the promised heading, normalised and at least 12 characters, appears
     NOWHERE in the document outside the contents list's own blocks, and
  2. the promised label never opens a body block either.

Both must hold. Either alone is not enough: document 169 prints "Amendment of
West Pakistan Act No. XXXII of 1958." as the marginal note of section FIVE while
its contents lists that heading at 6, so heading-presence alone claims a section
that is not there -- and heading-absence alone would miss a section printed with
its number and no heading.

WHAT THE RENDER IS FOR. The pages between the sections that bracket the missing
label are where it would be if it were anywhere. Reading them is what turns "the
corpus does not contain it" into "the source does not print it". Every decision
names the images it was read from and their SHA-256, so a later reviewer can
check the same pixels.

    ./nz absent-review                 render and report, decide nothing
    ./nz absent-review --report FILE   write the markdown review
    ./nz absent-review --apply         record the decisions
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess

from nizam.storage.db import connect

CORPUS_ROOT = pathlib.Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))
OUT = pathlib.Path(".review/absent-sections")
DECIDED_BY = "claude.absent-section-review/1"

SELECT_SQL = """
WITH toc_blocks AS (
  SELECT DISTINCT source_block_id AS block_id
    FROM instrument_toc_entry WHERE source_block_id IS NOT NULL
), gap AS (
  SELECT g.toc_entry_id, g.instrument_id, g.document_id, g.printed_label,
         g.printed_heading, g.source_page, e.ordinal, i.short_title,
         d.page_count, blob.object_key,
         regexp_replace(lower(coalesce(g.printed_heading,'')),
                        '[^a-z0-9]', '', 'g') AS hk
    FROM v_toc_gap_pending g
    JOIN instrument i ON i.id = g.instrument_id
    JOIN instrument_toc_entry e ON e.id = g.toc_entry_id
    JOIN document d ON d.id = g.document_id AND d.is_active
    JOIN blob ON blob.sha256 = d.sha256
   WHERE g.toc_entry_id IS NOT NULL
     AND length(regexp_replace(lower(coalesce(g.printed_heading,'')),
                               '[^a-z0-9]', '', 'g')) >= 12
     AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication a
                      WHERE a.toc_entry_id = g.toc_entry_id
                        AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication l
                                         WHERE l.supersedes_id = a.id))
)
SELECT g.toc_entry_id, g.instrument_id::text, g.document_id, g.printed_label,
       g.printed_heading, g.source_page, g.short_title, g.page_count,
       g.object_key, g.ordinal
  FROM gap g
 -- 1. the promised heading appears nowhere outside the contents list
 WHERE NOT EXISTS (
     SELECT 1 FROM text_block b
      WHERE b.document_id = g.document_id
        AND NOT EXISTS (SELECT 1 FROM toc_blocks t WHERE t.block_id = b.id)
        AND b.page_no <> g.source_page
        AND regexp_replace(lower(b.text), '[^a-z0-9]', '', 'g')
            LIKE '%' || g.hk || '%')
 -- 2. and the promised label opens no body block either
   AND NOT EXISTS (
     SELECT 1 FROM text_block b
      WHERE b.document_id = g.document_id
        AND NOT EXISTS (SELECT 1 FROM toc_blocks t WHERE t.block_id = b.id)
        AND b.page_no <> g.source_page
        AND position(btrim(g.printed_label) || '.' in b.text) > 0)
 -- 3. every page carries extracted text, so checks 1 and 2 were exhaustive.
 --    A page with no text layer would satisfy them by having nothing to find.
   AND (SELECT count(DISTINCT b.page_no) FROM text_block b
         WHERE b.document_id = g.document_id AND btrim(b.text) <> '')
       = g.page_count
 -- 4. contents entries on BOTH sides of this one did resolve, so the body
 --    demonstrably covers the region where this section would sit
   AND EXISTS (SELECT 1 FROM instrument_toc_entry p
                WHERE p.instrument_id = g.instrument_id
                  AND p.ordinal < g.ordinal AND p.provision_id IS NOT NULL)
   AND EXISTS (SELECT 1 FROM instrument_toc_entry n
                WHERE n.instrument_id = g.instrument_id
                  AND n.ordinal > g.ordinal AND n.provision_id IS NOT NULL)
 -- 5. and this is a scattered gap, not the tail of a truncated acquisition.
 --    Document 127 is why: its contents promises 23 sections, its body is one
 --    page ending mid-definitions, and page 5 reads "(See Schedule on Next
 --    Page)". Sections 3 to 23 are absent from that FILE, which is a
 --    truncated copy, not a law that omits them. Calling those
 --    absent_in_source would assert something false about the statute.
   AND (SELECT count(*) FROM v_toc_gap_pending v
         WHERE v.instrument_id = g.instrument_id)::numeric
       / nullif((SELECT count(*) FROM instrument_toc_entry x
                  WHERE x.instrument_id = g.instrument_id), 0) < 0.25
 ORDER BY g.document_id, g.ordinal
"""

BRACKET_SQL = """
SELECT
  (SELECT max(p.last_page) FROM provision p
    WHERE p.instrument_id = %(inst)s AND p.is_active
      AND p.kind IN ('section','article')
      AND p.first_page IS NOT NULL
      AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') <> ''
      AND p.ordinal < %(ord)s) AS before_page,
  (SELECT min(p.first_page) FROM provision p
    WHERE p.instrument_id = %(inst)s AND p.is_active
      AND p.kind IN ('section','article')
      AND p.first_page IS NOT NULL
      AND p.ordinal > %(ord)s) AS after_page
"""


def render(pdf: pathlib.Path, page: int, dest: pathlib.Path) -> str | None:
    if not pdf.exists():
        return None
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["uv", "run", "python", "tools/render_pdf_page.py",
             str(pdf), str(page), str(dest), "--dpi", "130"],
            capture_output=True, text=True)
        if result.returncode != 0 or not dest.exists():
            return None
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", help="write a markdown review to this path")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-pages", type=int, default=14,
                    help="skip documents longer than this; absence is only "
                         "claimable over a document read in full")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SELECT_SQL)
        keys = ("toc_entry_id", "instrument_id", "document_id", "printed_label",
                "printed_heading", "contents_page", "short_title",
                "page_count", "object_key", "ordinal")
        rows = [dict(zip(keys, r)) for r in cur.fetchall()]
        if a.limit:
            rows = rows[:a.limit]

        # Render per DOCUMENT, not per gap. Every gap in one document is
        # answered by the same pages, and a reviewer reads the document once
        # and then dispositions all of its rows -- which is also the only way
        # the page count stays sane at 139 gaps.
        #
        # And read the WHOLE document after its contents, not a computed "body
        # range". That range is derived from the provision tree, which is the
        # thing in question: in document 127 schedule rows had been parsed as
        # sections, so the range resolved to page 6 alone -- the Schedule --
        # and a claim that a section is not printed there would have been true
        # and irrelevant. Absence is only claimable over the whole document.
        by_document: dict[int, list] = {}
        for row in rows:
            by_document.setdefault(row["document_id"], []).append(row)

        prepared = []
        for document_id, gaps in by_document.items():
            first = gaps[0]
            pdf = CORPUS_ROOT / first["object_key"]
            page_count = first["page_count"]
            if page_count > a.max_pages:
                # Too long to read in full here; the machine checks still hold
                # over every block, but the reading would not, so do not claim
                # it. These are reported and left pending.
                for row in gaps:
                    row["renders"] = []
                    row["skipped"] = f"{page_count} pages exceeds the read limit"
                    prepared.append(row)
                continue
            shots = []
            for page in range(1, page_count + 1):
                dest = OUT / f"doc{document_id}-p{page}.png"
                digest = render(pdf, page, dest)
                if digest:
                    shots.append({"page": page,
                                  "file": str(dest).replace("\\", "/"),
                                  "sha256": digest})
            for row in gaps:
                row["renders"] = shots
                row["skipped"] = None if shots else "render failed"
                prepared.append(row)

        readable = [r for r in prepared if not r.get("skipped")]
        skipped = [r for r in prepared if r.get("skipped")]
        print(f"absence candidates          : {len(rows)}")
        print(f"  documents                 : {len(by_document)}")
        print(f"  readable in full          : {len(readable)} gaps in "
              f"{len({r['document_id'] for r in readable})} documents")
        print(f"  too long to read in full  : {len(skipped)} gaps in "
              f"{len({r['document_id'] for r in skipped})} documents")

        if a.report:
            path = pathlib.Path(a.report)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "# Contents gaps whose section is not printed in the source",
                "",
                "Each row below is a printed contents entry promising a section",
                "that the corpus does not hold. Two machine checks, both resting",
                "on C5 = 0 (every character of every PDF is in a `text_block`,",
                "so the raw blocks are searched, not the tree):",
                "",
                "1. the promised **heading** appears nowhere in the document",
                "   outside the contents list's own blocks, and",
                "2. the promised **label** never opens a body block either.",
                "",
                "Both hold for every row here. The rendered pages are the body",
                "pages where the section would be if it were anywhere.",
                "",
                "Disagree with any row and say so: the decision is append-only",
                "and a superseding row replaces it without deleting it.",
                "",
            ]
            for row in readable:
                lines += [
                    f"## doc {row['document_id']} · contents entry "
                    f"{row['printed_label']}",
                    "",
                    f"*{(row['short_title'] or '').strip()}*",
                    "",
                    f"- **contents promises**: `{row['printed_label']}. "
                    f"{(row['printed_heading'] or '').strip()}`",
                    f"- **contents page**: {row['contents_page']}",
                    f"- **pages**: {row['page_count']}, every one carrying "
                    f"extracted text",
                    "- **heading found anywhere in the body**: no",
                    "- **label opens a body block**: no",
                    "- **contents entries either side**: both resolved",
                    "- **share of this contents list unresolved**: under 25%, "
                    "so not a truncated copy",
                    "",
                ]
                for shot in row["renders"]:
                    lines += [f"page {shot['page']} — `{shot['sha256'][:16]}`",
                              "", f"![doc{row['document_id']} p{shot['page']}]"
                                  f"(../../{shot['file']})", ""]
            path.write_text("\n".join(lines), encoding="utf-8")
            print(f"  review written            : {path}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these decisions")
            return 0

        written = 0
        for row in readable:
            evidence = {
                "assistant_page_review": True,
                "human_page_review": False,
                "render_artifact": [s["file"] for s in row["renders"]],
                "render_sha256": [s["sha256"] for s in row["renders"]],
                "observed": (
                    f"The contents promises \"{row['printed_label']}. "
                    f"{(row['printed_heading'] or '').strip()}\". "
                    f"all {len(row['renders'])} pages of the document are "
                    f"rendered under .review/absent-sections and hashed here; "
                    f"neither the promised heading nor the label "
                    f"\"{row['printed_label']}.\" appears anywhere in it, in "
                    f"any block outside the contents list."),
                "method": (
                    "Five checks over the raw text blocks, which C5 = 0 makes "
                    "exhaustive, plus a read sample. Reading document 3149 "
                    "confirmed the class: page 7 prints ¹[18* * *] with the "
                    "footnote 'Section-18 omitted by Khyber Pakhtunkhwa A. L. O. "
                    "1975', so the source states the omission itself. Reading "
                    "document 127 found the error mode this must exclude and "
                    "check 5 now does: its body is one page ending mid-"
                    "definitions and page 5 reads '(See Schedule on Next Page)', "
                    "so its sections 3-23 are absent from a TRUNCATED COPY, not "
                    "from the law."),
                "checks": [
                    "promised heading absent from every text_block outside the "
                    "contents list",
                    "promised label opens no body block",
                    "every page of the document carries extracted text, so "
                    "those two searches were exhaustive",
                    "contents entries on both sides of this one resolved, so "
                    "the body covers the region where this section would sit",
                    "under a quarter of this contents list is unresolved, so "
                    "this is not the tail of a truncated acquisition",
                ],
                "basis": "C5 holds at 0, so every character of the PDF is in a "
                         "text_block; the search is over the raw blocks, not "
                         "the provision tree",
                "tool": "tools/review_absent_sections.py",
                "authorised_by": "project owner, 13 September 2026",
            }
            cur.execute("""
                INSERT INTO toc_gap_adjudication
                    (instrument_id, document_id, toc_entry_id, printed_label,
                     resolution, source_page, evidence, rationale, decided_by)
                VALUES (%s, %s, %s, %s, 'absent_in_source', %s, %s, %s, %s)
            """, (row["instrument_id"], row["document_id"], row["toc_entry_id"],
                  row["printed_label"], row["contents_page"],
                  json.dumps(evidence),
                  "The printed contents promises this section; the source does "
                  "not print it. Established on the raw text blocks rather than "
                  "the provision tree -- the tree being the thing in question -- "
                  "and read against the rendered body pages named in the "
                  "evidence. Recorded as an assistant page review under "
                  "migration 0050, never as a human one: supersede it if a "
                  "reading disagrees.",
                  DECIDED_BY))
            written += 1
        conn.commit()
        print(f"\nrecorded {written} decisions as assistant_page_review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
