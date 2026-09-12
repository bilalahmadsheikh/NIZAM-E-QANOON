"""Find what is probably wrong, as distinct from what is provably wrong.

`./nz audit` tests thirty INVARIANTS: statements that must hold, where a failure
is a defect by definition. That leaves a gap, and today filled it with examples:

  * two text blocks mix Arabic heh (U+0647) with Urdu heh goal (U+06C1). Both are
    valid characters, no invariant is violated, and Urdu search will still miss
    one of them.
  * ten of thirteen instruments classified `kind='constitution'` are not
    constitutions -- they matched the word in titles like "PROSECUTION SERVICE
    (CONSTITUTION, FUNCTIONS AND POWERS) ACT".
  * one document has 194 top-level sections sharing the label "1", which is not
    illegal, and is near-certain evidence of several Acts stored as one.

None of those is catchable by an invariant, because each is a judgement about
plausibility. So this reports SMELLS, ranked, with an example and a next step,
and it exits 0 whatever it finds. A linter that fails a build teaches people to
silence it; this one is meant to be read.

    ./nz lint                 every check
    ./nz lint --check kind    one check by name prefix
    ./nz lint --limit 10      more examples per finding
"""
from __future__ import annotations

import argparse
import textwrap

from nizam.storage.db import connect

# severity: 'high' -- almost certainly a defect; 'medium' -- worth a look;
# 'low' -- informational, may be entirely fine.
CHECKS = [
    {
        "name": "mixed-arabic-urdu-codepoints",
        "severity": "high",
        "why": "The same printed letter stored two ways in one block. Urdu search "
               "matches codepoints, so one spelling becomes unfindable.",
        "fix": "Normalise confusables (U+0647→U+06C1, U+0649→U+06CC, "
               "U+064A→U+06CC, Arabic-Indic digits→extended) at extraction, and "
               "again in the query path before matching.",
        "sql": """
            SELECT b.document_id, b.page_no, b.block_no,
                   (SELECT count(*) FROM regexp_matches(b.text, chr(1607), 'g')) AS arabic_heh,
                   (SELECT count(*) FROM regexp_matches(b.text, chr(1729), 'g')) AS urdu_heh
              FROM text_block b JOIN document d ON d.id=b.document_id AND d.is_active
             WHERE b.text LIKE '%' || chr(1607) || '%'
               AND b.text LIKE '%' || chr(1729) || '%'
             ORDER BY b.document_id, b.page_no""",
    },
    {
        "name": "kind-does-not-match-title",
        "severity": "high",
        "why": "`kind` is what callers filter on. A misfiled instrument is invisible "
               "to the right query and noise in the wrong one.",
        "fix": "Reclassify, or supersede `kind` with the nine facets in docs/03b.",
        "sql": """
            SELECT id, jurisdiction, year, left(short_title, 62) AS title, kind
              FROM instrument
             WHERE is_active AND duplicate_of IS NULL AND kind = 'constitution'
               AND short_title NOT ILIKE '%constitution of%'
             ORDER BY year""",
    },
    {
        "name": "many-top-level-sections-share-a-label",
        "severity": "high",
        "why": "Several Acts stored as one document: each brings its own section 1. "
               "A citation naming that instrument is ambiguous.",
        "fix": "Split the document (S10). Compare against "
               "v_boundary_adjudication_pending, which finds only some of these.",
        "sql": """
            WITH top AS (
              SELECT i.document_id, p.label, count(*) AS cnt
                FROM provision p JOIN instrument i ON i.id = p.instrument_id
               WHERE p.is_active AND i.is_active AND i.duplicate_of IS NULL
                 AND p.parent_id IS NULL AND p.label IS NOT NULL
               GROUP BY i.document_id, p.label)
            SELECT t.document_id, max(t.cnt) AS worst_collision,
                   left(max(i.short_title), 48) AS title,
                   (SELECT count(*) FROM v_boundary_adjudication_pending b
                     WHERE b.document_id = t.document_id) AS s10_already_found
              FROM top t JOIN instrument i ON i.document_id = t.document_id AND i.is_active
             GROUP BY t.document_id HAVING max(t.cnt) >= 10
             ORDER BY 2 DESC""",
    },
    {
        "name": "adjudications-with-no-human",
        "severity": "medium",
        "why": "S7 exists to catch automatic choices. A decision made and approved by "
               "the same program is not a review. The last column says whether the "
               "decisions cite a rendered-source audit in their own evidence -- a "
               "method that does is still machine-evidenced, but its rule has been "
               "checked against pages a person read, and that is the difference "
               "between an unexamined rule and a measured one.",
        "fix": "Sample-audit against source pages before treating the criterion as "
               "met: ./nz s7-audit --render N draws the weighted sample and renders "
               "it; E:/nizam-data/s7-audit/RESULT.md records what reading them found.",
        "sql": """
            SELECT decided_by, resolution, count(*) AS decisions,
                   min(decided_at)::date AS first, max(decided_at)::date AS last,
                   CASE WHEN bool_and(evidence ? 'sample_pages_rendered_and_read')
                        THEN 'yes, ' || max((evidence->>'sample_pages_rendered_and_read')::int)
                             || ' pages'
                        ELSE 'no' END AS source_audited
              FROM segmentation_structural_adjudication
             GROUP BY decided_by, resolution
            HAVING decided_by NOT ILIKE '%@%' AND decided_by NOT ILIKE '%human%'
             ORDER BY count(*) DESC""",
    },
    {
        "name": "instrument-title-looks-like-a-placeholder",
        "severity": "medium",
        "why": "A title that is a document id, blank, or carries a raw carriage return "
               "is a parse failure surfacing as data. It is what a user sees.",
        "fix": "Re-derive the title from the source, or record that the source has none.",
        # Grouped by cause, not listed row by row: 243 individual rows says
        # "something is wrong somewhere", four counts say which thing is wrong.
        "sql": """
            SELECT CASE
                     WHEN short_title ~ '^document [0-9]+$'          THEN 'title is a document id'
                     WHEN short_title ILIKE '%untitled%'             THEN 'literally untitled'
                     WHEN short_title LIKE '%' || chr(13) || '%'     THEN 'raw carriage return in title'
                     ELSE 'shorter than 8 characters'
                   END AS cause,
                   count(*) AS instruments,
                   left(min(short_title), 46) AS example
              FROM instrument
             WHERE is_active AND duplicate_of IS NULL
               AND (short_title ~ '^document [0-9]+$'
                    OR short_title ILIKE '%untitled%'
                    OR short_title LIKE '%' || chr(13) || '%'
                    OR length(btrim(short_title)) < 8)
             GROUP BY 1 ORDER BY 2 DESC""",
    },
    {
        "name": "ocr-candidate-points-at-a-retired-revision",
        "severity": "low",
        "why": "Expected after a promotion -- the candidate was made against the "
               "revision it replaced. Listed because it silently empties "
               "v_ocr_adjudication_evidence, which joins on d.is_active.",
        "fix": "Nothing to repair. Reach the evidence via sha256 or "
               "extractor_config->'ocr_promotion' instead of the view.",
        "sql": """
            SELECT c.engine, count(*) AS candidates,
                   count(DISTINCT c.document_id) AS documents
              FROM page_ocr_candidate c JOIN document d ON d.id = c.document_id
             WHERE NOT d.is_active
             GROUP BY c.engine ORDER BY 2 DESC""",
    },
    {
        "name": "document-with-no-instrument",
        "severity": "high",
        "why": "An active document nothing points at is text the corpus cannot cite. "
               "A document whose source was reviewed and found to carry no citable "
               "structure -- a repeal placeholder, a cadre table -- is excluded, "
               "because the reason is recorded and checkable; what this reports is "
               "the ones nobody has explained.",
        "fix": "Segment it, or record why it carries no instrument: an "
               "extraction_assertion naming the document and the reason its source "
               "has no provisions (see tools/evidence/declare-uncitable-documents.sql).",
        "sql": """
            SELECT d.id AS document_id, d.lane, d.page_count, d.char_count
              FROM document d
             WHERE d.is_active
               AND NOT EXISTS (SELECT 1 FROM instrument i
                                WHERE i.document_id = d.id AND i.is_active)
               AND NOT EXISTS (SELECT 1 FROM extraction_assertion a
                                WHERE a.sha256 = d.sha256
                                  AND a.kind = 'source_content_confirmed'
                                  AND (a.detail ->> 'document_id')::bigint = d.id
                                  AND a.detail ->> 'purpose' IN (
                                        'no-operative-text',
                                        'table-document-no-provisions'))
             ORDER BY d.char_count DESC""",
    },
    {
        "name": "acquisition-exception-with-no-decision",
        "severity": "medium",
        "why": "A catalogued item that did not land, was not recovered, and carries "
               "no declared reason is indistinguishable from work nobody has done. "
               "The attempt ledger says what happened on each fetch; only an "
               "acquisition_exception says that no further fetch is expected to "
               "succeed, and why.",
        "fix": "Retry it with nizam.workers.recover_acquisition, or declare it: "
               "see tools/evidence/declare-acquisition-exceptions.sql, which reads "
               "its evidence from the attempt ledger rather than asserting it.",
        "sql": """
            SELECT source_id,
                   coalesce(error_code, '<none>') AS error_code,
                   count(*) AS items,
                   max(attempts) AS attempts_so_far
              FROM v_acquisition_unresolved
             GROUP BY 1, 2 ORDER BY items DESC""",
    },
    {
        "name": "provision-with-nothing-at-all",
        "severity": "medium",
        "why": "A citable unit that resolves to nothing: no text, no children, and no "
               "source block either. C6 accepts a provision backed by a block alone, "
               "so this must test all three or it reports thousands of healthy rows.",
        "fix": "Usually a heading parsed as a section. Re-segment the document.",
        "sql": """
            SELECT i.document_id, p.label, left(coalesce(p.heading, ''), 44) AS heading
              FROM provision p JOIN instrument i ON i.id = p.instrument_id
             WHERE p.is_active AND i.is_active AND i.duplicate_of IS NULL
               AND p.first_block IS NULL
               AND NOT EXISTS (SELECT 1 FROM provision c WHERE c.parent_id = p.id AND c.is_active)
               AND NOT EXISTS (SELECT 1 FROM provision_version v WHERE v.provision_id = p.id)
             ORDER BY i.document_id LIMIT 200""",
    },
]

ORDER = {"high": 0, "medium": 1, "low": 2}


def main() -> int:
    ap = argparse.ArgumentParser(description="Report corpus smells, not invariants")
    ap.add_argument("--check", help="run only checks whose name starts with this")
    ap.add_argument("--limit", type=int, default=5, help="examples per finding")
    a = ap.parse_args()

    checks = [c for c in CHECKS if not a.check or c["name"].startswith(a.check)]
    if not checks:
        print(f"no check matches {a.check!r}. names: "
              + ", ".join(c["name"] for c in CHECKS))
        return 0

    findings, clean = [], []
    with connect() as conn, conn.cursor() as cur:
        for c in sorted(checks, key=lambda c: ORDER[c["severity"]]):
            try:
                cur.execute(c["sql"])
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
            except Exception as exc:
                conn.rollback()
                findings.append((c, ["error"], [(f"{type(exc).__name__}: {exc}",)], 1))
                continue
            (findings if rows else clean).append((c, cols, rows, len(rows)))

    print(f"\ncorpus lint — {len(checks)} check(s), "
          f"{len(findings)} with findings, {len(clean)} clean\n")

    for c, cols, rows, n in findings:
        bar = {"high": "!!", "medium": "! ", "low": "  "}[c["severity"]]
        print(f"{bar} [{c['severity'].upper()}] {c['name']} — {n} row(s)")
        for line in textwrap.wrap(c["why"], 92):
            print(f"     {line}")
        print(f"     {'-' * 88}")
        widths = [min(34, max(len(str(x)) for x in [cols[i]] + [r[i] for r in rows[:a.limit]]))
                  for i in range(len(cols))]
        print("     " + "  ".join(str(h)[:w].ljust(w) for h, w in zip(cols, widths)))
        for r in rows[:a.limit]:
            print("     " + "  ".join(str(v)[:w].ljust(w) for v, w in zip(r, widths)))
        if n > a.limit:
            print(f"     … {n - a.limit} more")
        for line in textwrap.wrap("FIX: " + c["fix"], 92):
            print(f"     {line}")
        print()

    if clean:
        print("clean: " + ", ".join(c["name"] for c, *_ in clean) + "\n")
    # Always zero: this reports, it does not gate. The audit is the gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
