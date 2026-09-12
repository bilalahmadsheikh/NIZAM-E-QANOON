"""Record, with source evidence, the contents gaps whose section IS printed.

A gap says the contents promised a section the tree does not hold. That is not
the same as the SOURCE not holding it, and the difference decides the repair:

  * printed and not in the tree  -> a parser defect; the law exists and is not
    citable, and only a corrected parse fixes it,
  * not printed at all          -> the contents outlived its section, which is
    a disposition a person must read the page to assert (migration 0042).

C5 = 0 guarantees every character of every PDF sits in a ``text_block``, so the
first case can be established from the corpus rather than guessed. Search the
raw blocks for the promised heading, excluding the contents list's own blocks --
they otherwise match themselves and return a meaningless 100%.

Three of these were read against rendered pages before this was written, and all
three showed the same thing:

  * document 173 page 3 prints "3. (1) The Government may, by notification in
    the official Gazette, declare any Education Service to be an Essential
    Service", with "Declaration of Essential Service and prohibition of Strike,
    lockout and other illegal acts." in the margin -- the contents' exact words.
    The tree holds it as ``clause 3`` under section 2, so it is not citable as
    section 3.
  * document 176 page 5 prints "12. The provisions of this Act shall prevail
    notwithstanding anything contained to the contrary in any other Law." with
    "Provisions of this Act to override other laws." in the margin.
  * document 169 is the counter-example, and the first version of this tool got
    it wrong. Its contents prints rows 4 and 5 with identical text and promises
    six sections where the body ends at five; the heading listed at 6 is the
    marginal note of section FIVE. Matching the heading alone therefore claimed
    a section that is not there. Requiring the promised NUMBER to be printed
    beside it excludes the document, which reading the page had already shown.

``parser_defect`` is the honest resolution and it deliberately does NOT close
the gap: ``v_toc_gap_pending`` keeps parser defects pending until a replay
proves them fixed. This classifies the queue with evidence; it does not empty
it, and it releases no instrument.

    ./nz toc-classify            dry run
    ./nz toc-classify --apply    record the classifications
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

from nizam.storage.db import connect

DECIDED_BY = "claude.toc-printed-not-parsed/1"
RENDERS = pathlib.Path(".artifacts/toc-gap-review")

# A gap whose promised heading is printed somewhere in the document OTHER than
# the contents list. The heading must be long enough to be evidence: a short one
# ("Repeal.", "Rules.") matches too much to prove anything.
SELECT_SQL = """
WITH toc_blocks AS (
  SELECT DISTINCT e.source_block_id AS block_id
    FROM instrument_toc_entry e WHERE e.source_block_id IS NOT NULL
), gap AS (
  SELECT g.toc_entry_id, g.instrument_id, g.document_id, g.printed_label,
         g.printed_heading, g.source_page,
         regexp_replace(lower(g.printed_label), '[^a-z0-9]', '', 'g') AS lk,
         regexp_replace(lower(coalesce(g.printed_heading,'')), '[^a-z0-9]', '', 'g') AS hk
    FROM v_toc_gap_pending g
   WHERE g.toc_entry_id IS NOT NULL
     AND length(regexp_replace(lower(coalesce(g.printed_heading,'')),
                               '[^a-z0-9]', '', 'g')) >= 16
     AND NOT EXISTS (
       SELECT 1 FROM toc_gap_adjudication a
        WHERE a.toc_entry_id = g.toc_entry_id
          AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication l
                           WHERE l.supersedes_id = a.id))
)
SELECT g.toc_entry_id, g.instrument_id::text, g.document_id, g.printed_label,
       g.printed_heading, g.source_page, b.page_no, b.id, b.reading_order,
       left(regexp_replace(b.text, '\\s+', ' ', 'g'), 160) AS body_text,
       EXISTS (SELECT 1 FROM provision p
                WHERE p.instrument_id = g.instrument_id AND p.is_active
                  AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') = g.lk
              ) AS label_in_tree_somewhere,
       (SELECT p.kind::text FROM provision p
         WHERE p.instrument_id = g.instrument_id AND p.is_active
           AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g') = g.lk
         LIMIT 1) AS label_kind
  FROM gap g
  JOIN LATERAL (
    SELECT b.id, b.page_no, b.text, b.reading_order FROM text_block b
     WHERE b.document_id = g.document_id
       AND NOT EXISTS (SELECT 1 FROM toc_blocks t WHERE t.block_id = b.id)
       AND b.page_no <> g.source_page
       AND regexp_replace(lower(b.text), '[^a-z0-9]', '', 'g') LIKE '%' || g.hk || '%'
     ORDER BY b.page_no, b.reading_order LIMIT 1) b ON true
 ORDER BY g.document_id, g.toc_entry_id
"""

# The heading alone is not enough, and this is the reason the label is checked
# in Python rather than in the query: a marginal note belonging to a DIFFERENT
# section matches the heading just as well. Document 169 prints "Amendment of
# West Pakistan Act No. XXXII of 1958." beside section 5, and its contents lists
# that heading at 6 only because rows 4 and 5 are a duplicated line. Reading the
# page settled it -- the Act ends at section 5 -- and no aggregate could have.
# So the promised NUMBER must be printed too: the matched block, or one of the
# two blocks after it in reading order, must open with this label. Labels carry
# ".", "-", "(" and brackets ("4-A", "3A", "1[Repeal]"), so they are escaped
# with re.escape; hand-escaping them into SQL produced an unbalanced bracket
# expression twice.
NEIGHBOURS_SQL = """
SELECT n.text FROM text_block n
 WHERE n.document_id = %s
   AND n.reading_order BETWEEN %s AND %s + 2
 ORDER BY n.reading_order
"""

RATIONALE = (
    "The section this contents row promises IS printed in the source: its exact "
    "heading appears on page {page}, in a block that is not part of the contents "
    "list. So the source does not omit it and no disposition is owed -- what is "
    "wrong is the parse. {tree_note} Established from the corpus, not inferred: "
    "C5 holds at 0, so every character of the PDF is in a text_block, and the "
    "search excludes the contents list's own blocks. Three gaps of this class "
    "were read against rendered pages first (documents 173, 176 and 169); the "
    "two printed ones showed the section with its number and its marginal "
    "heading exactly as the contents promises, and the third, where nothing is "
    "printed, is excluded by this search. Recorded as parser_defect, which "
    "leaves the gap pending: only a corrected parse resolves it."
)

IN_TREE = ("The label does exist in the tree, but as a {kind} rather than a "
           "section, so the provision is not citable at the number the source "
           "prints (INV-4).")
NOT_IN_TREE = ("The label is not in the tree at all, so the parser did not open "
               "the section.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(SELECT_SQL)
        keys = ("toc_entry_id", "instrument_id", "document_id", "printed_label",
                "printed_heading", "contents_page", "body_page", "block_id",
                "reading_order", "body_text", "label_in_tree", "label_kind")
        candidates = [dict(zip(keys, r)) for r in cur.fetchall()]

        rows, heading_only = [], []
        for row in candidates:
            cur.execute(NEIGHBOURS_SQL, (row["document_id"],
                                         row["reading_order"],
                                         row["reading_order"]))
            opener = re.compile(
                r"(^|\s)" + re.escape(str(row["printed_label"]).strip())
                + r"\s*\.")
            if any(opener.search(text or "") for (text,) in cur.fetchall()):
                rows.append(row)
            else:
                heading_only.append(row)
        if a.limit:
            rows = rows[:a.limit]

        cur.execute("SELECT count(*) FROM v_toc_gap_pending")
        pending = cur.fetchone()[0]
        demoted = sum(1 for r in rows if r["label_in_tree"])
        print(f"contents gaps pending                     : {pending}")
        print(f"  heading matched somewhere in the body    : {len(candidates)}")
        print(f"  ... AND the promised number printed there: {len(rows)}")
        print(f"  ... heading only, no number -- EXCLUDED   : {len(heading_only)}")
        print(f"    ... label in the tree, but not a section: {demoted}")
        print(f"    ... label not in the tree at all        : {len(rows) - demoted}")
        print(f"  documents                               : "
              f"{len({r['document_id'] for r in rows})}")
        for r in rows[:a.show]:
            kind = r["label_kind"] or "absent"
            print(f"    doc {r['document_id']:<6} label {str(r['printed_label']):<7} "
                  f"contents p{r['contents_page']} -> printed p{r['body_page']} "
                  f"[{kind}]  {(r['printed_heading'] or '')[:40]}")

        if not a.apply:
            print("\ndry run -- pass --apply to record these classifications")
            return 0

        written = 0
        for r in rows:
            artifacts = sorted(
                str(p).replace("\\", "/") for p in RENDERS.glob(
                    f"doc{r['document_id']}-e{r['toc_entry_id']}-*.png"))
            evidence = {
                "defect_class": ("printed_section_held_as_a_non_section"
                                 if r["label_in_tree"]
                                 else "printed_section_absent_from_tree"),
                "printed_on_page": r["body_page"],
                "printed_block_id": r["block_id"],
                "printed_block_text": r["body_text"],
                "contents_page": r["contents_page"],
                "label_in_tree_as": r["label_kind"],
                "method": "the promised heading, normalised, occurs in a "
                          "text_block of this document that is not part of the "
                          "contents list and is not on the contents page",
                "tool": "tools/classify_printed_but_uncitable_gaps.py",
                "corroborated_by_reading": ["document 173 page 3",
                                            "document 176 page 5"],
                "reviewer_type": "assistant",
                "human_page_review": False,
            }
            if artifacts:
                evidence["render_artifact"] = artifacts
            note = (IN_TREE.format(kind=r["label_kind"]) if r["label_in_tree"]
                    else NOT_IN_TREE)
            cur.execute("""
                INSERT INTO toc_gap_adjudication
                    (instrument_id, document_id, toc_entry_id, printed_label,
                     resolution, source_page, evidence, rationale, decided_by)
                VALUES (%s, %s, %s, %s, 'parser_defect', %s, %s, %s, %s)
            """, (r["instrument_id"], r["document_id"], r["toc_entry_id"],
                  r["printed_label"], r["contents_page"], json.dumps(evidence),
                  RATIONALE.format(page=r["body_page"], tree_note=note),
                  DECIDED_BY))
            written += 1
        conn.commit()
        print(f"\nclassified {written} gaps (all remain pending by design)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
