"""Generate the context pack an agent (or a person) needs before touching this database.

WHY THIS EXISTS. Over one working day, two coding agents made the same four
classes of mistake against this corpus:

    wrong column name          4 times  (problems, started_at, proposed_kind)
    wrong table name           1 time   (multi_instrument_boundary)
    forgot `duplicate_of`      1 time   (every theft section counted twice)
    forgot `is_active`         repeatedly (retired revisions counted as live)

The first two are ignorance of the schema and a catalog dump fixes them. The last
two are not: `text_block` has no `is_active` column of its own, the rule lives on
`document`, and no amount of DDL says so. A tool that prints structure without
semantics fixes half the problem and leaves the more expensive half.

So this emits both: the catalog, read live so it cannot drift, and the curated
rules that make a query correct rather than merely valid. It is regenerated, not
maintained -- the numbers in it are measurements, and a stale measurement is
worse than none.

    ./nz context                 writes docs/AGENT-CONTEXT.md
    ./nz context --stdout        print instead
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from nizam.storage.db import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AGENT-CONTEXT.md"

# --- the part no catalog can tell you -----------------------------------------
#
# Keyed by relation. `rule` is the filter a correct query needs; `purpose` is
# what the table is for. Anything absent here is emitted with structure only,
# which is honest: a blank purpose says nobody has written one down yet.
NOTES: dict[str, dict[str, str]] = {
    "document": {
        "purpose": "One extraction revision of one PDF. NOT one law -- re-extracting "
                   "makes a new row and retires the old.",
        "rule": "is_active — without it you count every generation ever produced.",
    },
    "instrument": {
        "purpose": "One legal instrument: an Act, Ordinance, Rules. The thing a "
                   "citation names.",
        "rule": "is_active AND duplicate_of IS NULL — duplicate_of links exact copies; "
                "counting them doubles your answer.",
    },
    "provision": {
        "purpose": "A section/subsection in the instrument's tree. INV-4 makes this "
                   "the citable unit. Text lives in provision_version, not here.",
        "rule": "p.is_active AND join instrument for i.is_active — a provision can be "
                "active under a retired instrument.",
    },
    "provision_version": {
        "purpose": "The text of a provision over time. INV-5: read as at a date.",
        "rule": "bounded by validity; never read the base table for current text.",
    },
    "text_block": {
        "purpose": "Raw extracted text with page and geometry. The input to "
                   "segmentation, not a citable unit.",
        "rule": "has NO is_active of its own — join document and filter d.is_active.",
    },
    "page": {"purpose": "One page of one document revision.",
             "rule": "join document for is_active."},
    "source_observation": {
        "purpose": "One catalogued item from a source portal. outcome='landed' and a "
                   "sha256 mean the file landed; acquisition_attempt can record a later recovery.",
        "rule": "For unresolved acquisition work, exclude observations with a recovered attempt; "
                "a raw sha256-null count includes recovered historical failures.",
    },
    "blob": {"purpose": "One stored PDF, addressed by sha256.", "rule": ""},
    "extraction_verification": {
        "purpose": "Evidence from the independent pdftotext cross-check. char_recall "
                   "and char_precision are COLUMNS, not keys in detail.",
        "rule": "take the newest row per document; it is append-only.",
    },
    "page_ocr_candidate": {
        "purpose": "A proposed OCR reading of one page. A proposal, never applied "
                   "automatically.",
        "rule": "points at the document revision it was made against, which may now "
                "be retired.",
    },
    "page_ocr_adjudication": {
        "purpose": "A person's decision about which OCR reading the corpus keeps.",
        "rule": "newest row per candidate wins; rejecting never deletes the candidate.",
    },
    "segmentation_structural_candidate": {
        "purpose": "A sibling-label collision the segmenter resolved automatically "
                   "(S7). Its evidence->>'group_size' says how many shared the label.",
        "rule": "",
    },
    "segmentation_structural_adjudication": {
        "purpose": "A decision on one structural candidate. Today every row was made "
                   "by nizam.structural_adjudicator/1 -- a machine, unreviewed.",
        "rule": "",
    },
    "segmentation_boundary_candidate": {
        "purpose": "A detected boundary where one PDF holds several instruments (S10). "
                   "NOT called multi_instrument_boundary.",
        "rule": "",
    },
    "instrument_expression_manifest": {
        "purpose": "Versioned, source-block-anchored boundaries for every legal expression "
                   "materialized from a multi-instrument PDF.",
        "rule": "is_active for the current boundary map; retired rows are preserved evidence.",
    },
    "extraction_assertion": {
        "purpose": "A human statement about a source page: content confirmed, decode "
                   "damage, visibility reviewed.",
        "rule": "is_active.",
    },
}

VIEW_NOTES = {
    "v_release_instrument": "Instruments that pass every release gate. THE set an app may serve.",
    "v_release_provision": "Provisions under release-ready instruments.",
    "v_release_provision_version": "Version text under release-ready provisions; retrieval indexes this view.",
    "v_toc_gap": "Documents whose printed contents list a section the body lacks.",
    "v_structural_adjudication_pending": "S7 work not yet decided.",
    "v_boundary_adjudication_pending": "S10 multi-instrument boundaries not yet decided.",
    "v_ocr_adjudication_evidence": "Stored text beside a proposed OCR reading, per page.",
    "v_document_quality_status": "Per-document verdict from every quality verifier.",
    "v_toc": "Printed contents entries with their source anchors.",
}

RULES = """\
### The four rules that make a query correct rather than merely valid

1. **`is_active` on every current-state query.** The corpus is append-only
   (migration 0012). Re-extracting or re-segmenting *retires* the previous
   revision rather than deleting it. A query that reads a base table without
   this counts every generation ever produced — {retired:,} of the
   {total_prov:,} provision rows belong to superseded revisions.

2. **`duplicate_of IS NULL` on `instrument`.** Exact duplicates are *linked*,
   not removed. {dupes} instruments are marked as duplicates today. Omitting
   this silently doubles counts — it is how a search for theft sections
   returned every section twice.

3. **`text_block` and `page` have no `is_active` of their own.** The flag lives
   on `document`. Join it. This is the single easiest way to get a plausible
   wrong number out of this database.

4. **Text is not on `provision`.** `provision` carries structure (label, path,
   heading); the words live in `provision_version`, bounded by validity, because
   INV-5 answers law as at a date.
"""


def q(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the agent context pack")
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        counts = q(cur, """
            SELECT (SELECT count(*) FROM document WHERE is_active),
                   (SELECT count(*) FROM instrument WHERE is_active AND duplicate_of IS NULL),
                   (SELECT count(*) FROM instrument WHERE duplicate_of IS NOT NULL),
                   (SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id
                     WHERE p.is_active AND i.is_active),
                   (SELECT count(*) FROM provision),
                   (SELECT count(*) FROM provision p JOIN instrument i ON i.id=p.instrument_id
                     WHERE NOT i.is_active),
                   (SELECT count(*) FROM v_release_instrument),
                   (SELECT count(*) FROM text_block b JOIN document d ON d.id=b.document_id
                     WHERE d.is_active),
                   (SELECT pg_size_pretty(pg_database_size(current_database())))
        """)[0]
        (docs, instr, dupes, prov_live, prov_all, prov_retired,
         release, blocks, dbsize) = counts

        problems = q(cur, """
            SELECT 'S7 pending label decisions',
                   (SELECT count(*) FROM v_structural_adjudication_pending)::text
            UNION ALL SELECT 'S10 multi-instrument boundaries',
                   (SELECT count(*) FROM v_boundary_adjudication_pending)::text
            UNION ALL SELECT 'TOC gaps across active provenance trees (raw)',
                   coalesce((SELECT sum(gaps)::text FROM v_toc_gap), '0')
            UNION ALL SELECT 'Canonical TOC gaps pending resolution',
                   (SELECT count(*) FROM v_toc_gap_pending)::text
            UNION ALL SELECT 'Instruments blocked from release',
                   ((SELECT count(*) FROM instrument WHERE is_active AND duplicate_of IS NULL)
                    - (SELECT count(*) FROM v_release_instrument))::text
            UNION ALL SELECT 'Catalogue entries that never landed a file',
                   (SELECT count(*) FROM source_observation o
                     WHERE o.outcome<>'landed'
                       AND NOT EXISTS (SELECT 1 FROM acquisition_attempt x
                                        WHERE x.source_observation_id=o.id
                                          AND x.outcome='recovered'))::text
            UNION ALL SELECT 'Structural adjudications made by machine alone',
                   (SELECT count(*) FROM segmentation_structural_adjudication)::text
        """)

        rels = q(cur, """
            SELECT c.relname, c.relkind,
                   CASE WHEN c.relkind='r' THEN greatest(c.reltuples,0)::bigint END,
                   CASE WHEN c.relkind='r' THEN pg_size_pretty(pg_total_relation_size(c.oid)) END
              FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relkind IN ('r','v')
             ORDER BY c.relkind, c.relname""")

        cols = {}
        for name, dtype, nullable in q(cur, """
                SELECT table_name, column_name || ' ' || data_type, is_nullable
                  FROM information_schema.columns WHERE table_schema='public'
                 ORDER BY table_name, ordinal_position"""):
            cols.setdefault(name, []).append(dtype)

        fks = {}
        for tbl, col, ftbl in q(cur, """
                SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text
                  FROM pg_constraint c
                  JOIN unnest(c.conkey) k(attnum) ON true
                  JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
                 WHERE c.contype='f' ORDER BY 1,2"""):
            fks.setdefault(tbl, []).append(f"{col} → {ftbl}")

        enums = q(cur, """
            SELECT t.typname, string_agg(e.enumlabel, ' · ' ORDER BY e.enumsortorder)
              FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid
              JOIN pg_namespace n ON n.oid=t.typnamespace
             WHERE n.nspname='public' GROUP BY t.typname ORDER BY t.typname""")

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = []
    w = L.append
    w(f"# Agent context — Nizam-e-Qanoon corpus\n")
    w(f"*Generated {now} from `nizam_clean`. Regenerate with `./nz context`.*\n")
    w("Every number here is a measurement, not a target. If it looks stale, it is — "
      "regenerate rather than trusting it.\n")

    w(RULES.format(retired=prov_retired, total_prov=prov_all, dupes=dupes))

    w("\n### Where the corpus stands\n")
    w("| | |")
    w("|---|---|")
    w(f"| Active documents | {docs:,} |")
    w(f"| Instruments (live, non-duplicate) | {instr:,} |")
    w(f"| — of those, release-ready | **{release:,}** |")
    w(f"| — marked duplicate | {dupes:,} |")
    w(f"| Provisions live / retired | {prov_live:,} / {prov_retired:,} |")
    w(f"| Text blocks (active documents) | {blocks:,} |")
    w(f"| Database size | {dbsize} |")

    w("\n### Known problems right now\n")
    w("| problem | count |")
    w("|---|---|")
    for label, n in problems:
        w(f"| {label} | {n} |")

    w("\n### Tables\n")
    for name, kind, rows, size in rels:
        if kind != "r":
            continue
        note = NOTES.get(name, {})
        w(f"\n**`{name}`** — {rows:,} rows, {size}" if rows is not None else f"\n**`{name}`**")
        if note.get("purpose"):
            w(f"  \n{note['purpose']}")
        if note.get("rule"):
            w(f"  \n⚠️ **Filter:** {note['rule']}")
        w(f"  \n`{', '.join(cols.get(name, []))}`")
        if fks.get(name):
            w(f"  \nFK: {'; '.join(fks[name])}")

    w("\n### Views — prefer these over base tables\n")
    for name, kind, _r, _s in rels:
        if kind != "v":
            continue
        note = VIEW_NOTES.get(name, "")
        w(f"- **`{name}`**" + (f" — {note}" if note else ""))

    w("\n### Enums (these are the only valid values)\n")
    for name, labels in enums:
        w(f"- **`{name}`**: {labels}")

    w("\n### Where things are decided\n")
    w("| topic | document |")
    w("|---|---|")
    for topic, doc in [
        ("Layers, domain model, ADRs", "`docs/01-master-architecture`"),
        ("Extraction, segmentation, quality gates", "`docs/02-corpus-and-ingestion`"),
        ("Schema, indexes, publish transaction", "`docs/03-data-and-storage`"),
        ("Legal graph: 14 edge types, 9 facets", "`docs/03b-legal-data-model`"),
        ("Retrieval and the gate", "`docs/04-retrieval`"),
        ("The 30 audit criteria", "`tools/audit/criteria.sql`"),
    ]:
        w(f"| {topic} | {doc} |")

    text = "\n".join(L) + "\n"
    if a.stdout:
        print(text)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}  ({len(text):,} bytes, "
              f"{len(rels)} relations, {len(enums)} enums)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
