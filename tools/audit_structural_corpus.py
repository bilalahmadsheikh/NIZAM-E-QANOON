"""Read-only, whole-active-corpus structural screening; flags are not verdicts."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from nizam.storage.db import connect


QUERIES = {
    "repeated_sibling_label": """
        SELECT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          LEFT JOIN text_block t ON t.id=p.first_block
         WHERE i.is_active AND p.is_active
           AND p.kind NOT IN ('proviso','explanation','illustration')
           AND EXISTS (SELECT 1 FROM provision q
                        WHERE q.instrument_id=p.instrument_id AND q.is_active
                          AND q.id<>p.id AND q.parent_id IS NOT DISTINCT FROM p.parent_id
                          AND q.kind=p.kind AND lower(trim(q.label))=lower(trim(p.label)))
    """,
    "top_level_nested_kind": """
        SELECT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          LEFT JOIN text_block t ON t.id=p.first_block
         WHERE i.is_active AND p.is_active AND p.parent_id IS NULL
           AND p.kind IN ('subsection','clause','proviso','explanation','illustration')
    """,
    "path_parent_mismatch": """
        SELECT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          JOIN provision parent ON parent.id=p.parent_id
          LEFT JOIN text_block t ON t.id=p.first_block
         WHERE i.is_active AND p.is_active AND NOT parent.path @> p.path
    """,
    "source_document_mismatch": """
        SELECT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          JOIN text_block t ON t.id=p.first_block
         WHERE i.is_active AND p.is_active AND t.document_id<>i.document_id
    """,
    "root_source_order_inversion": """
        WITH ordered AS (
          SELECT p.*,i.document_id,
                 lag(p.first_block) OVER (PARTITION BY p.instrument_id ORDER BY p.ordinal,p.id) AS prior_block
            FROM provision p JOIN instrument i ON i.id=p.instrument_id
           WHERE i.is_active AND p.is_active AND p.parent_id IS NULL)
        SELECT p.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM ordered p LEFT JOIN text_block t ON t.id=p.first_block
         WHERE p.first_block<p.prior_block
    """,
    "numbered_proviso_without_own_node": """
        SELECT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,t.id AS first_block,t.page_no AS first_page,
               t.text AS source_text,p.first_block AS owner_first_block
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          JOIN block_assignment_set s ON s.document_id=i.document_id AND s.is_active
          JOIN provision_block pb ON pb.assignment_set_id=s.id AND pb.provision_id=p.id
          JOIN text_block t ON t.id=pb.block_id
         WHERE i.is_active AND p.is_active AND t.text ~* '^\\s*[0-9]{1,2}\\s*\\[\\s*Provided'
           AND p.first_block<>t.id
    """,
    "footnote_phrase_in_operative_text": """
        SELECT DISTINCT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          JOIN provision_version v ON v.provision_id=p.id
          LEFT JOIN text_block t ON t.id=p.first_block
         WHERE i.is_active AND p.is_active AND coalesce(v.text_en,'') ~* 
               '(this act was passed by|published in the.*gazette.*dated|substituted for the.*by the.*amendment.*ordinance)'
    """,
    "toc_source_promoted": """
        SELECT i.document_id,p.instrument_id::text,p.id::text,p.parent_id::text,
               p.kind::text,p.label,p.path::text,p.first_block,p.first_page,
               t.text AS source_text
          FROM provision p JOIN instrument i ON i.id=p.instrument_id
          JOIN instrument_toc_entry toc ON toc.instrument_id=i.id AND toc.source_block_id=p.first_block
          LEFT JOIN text_block t ON t.id=p.first_block
         WHERE i.is_active AND p.is_active
    """,
}


def audit(pack: Path | None) -> dict:
    questions: dict[tuple[int, int], list[str]] = defaultdict(list)
    if pack is not None:
        for path in (pack / "questions").glob("doc-*/*.json"):
            case = json.loads(path.read_text(encoding="utf-8"))
            found = case.get("how_found", {})
            for key in ("candidate_source_block", "canonical_source_block"):
                block = found.get(key)
                if isinstance(block, dict) and block.get("id") is not None:
                    questions[(case["document_id"], int(block["id"]))].append(case["case_id"])
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("""SELECT (SELECT count(*) FROM instrument WHERE is_active),
                              (SELECT count(DISTINCT document_id) FROM instrument WHERE is_active),
                              (SELECT count(*) FROM provision WHERE is_active),
                              (SELECT count(*) FROM v_structural_adjudication_pending),
                              (SELECT count(*) FROM instrument_toc_entry t JOIN instrument i
                                ON i.id=t.instrument_id WHERE i.is_active)""")
        instruments, documents, nodes, pending_s7, toc_entries = cur.fetchone()
        findings = []
        for category, query in QUERIES.items():
            cur.execute(query)
            names = [column.name for column in cur.description]
            for values in cur.fetchall():
                row = dict(zip(names, values))
                row["first_block"] = int(row["first_block"]) if row["first_block"] is not None else None
                row["source_text"] = (row["source_text"] or "")[:500]
                row["category"] = category
                row["evidence_status"] = "heuristic_flag_not_source_verified"
                row["case_ids"] = questions.get((row["document_id"], row["first_block"]), [])
                findings.append(row)
        cur.execute("""SELECT count(*) FROM (
          SELECT p.instrument_id,p.kind,p.label FROM provision p
          JOIN instrument i ON i.id=p.instrument_id
          WHERE i.is_active AND p.is_active
          GROUP BY p.instrument_id,p.kind,p.label
          HAVING count(DISTINCT coalesce(p.parent_id::text,'ROOT'))>1) x""")
        reused_label_across_parents = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FROM provision_block pb
          JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
          WHERE pb.role='unassigned'""")
        unassigned_blocks = cur.fetchone()[0]
        parent_ids = sorted({row["parent_id"] for row in findings
                             if row["parent_id"] is not None})
        cur.execute("SELECT id::text,path::text FROM provision WHERE id=ANY(%s::uuid[])",
                    (parent_ids,))
        parent_paths = dict(cur.fetchall())
        cur.execute("""SELECT d.id,d.sha256,b.object_key FROM document d
                       LEFT JOIN blob b ON b.sha256=d.sha256""")
        sources = {doc_id: (sha, object_key) for doc_id, sha, object_key
                   in cur.fetchall()}
        for row in findings:
            row["current_parent_path"] = parent_paths.get(row["parent_id"])
            row["proposed_parent_path"] = None
            row["proposed_path"] = None
            row["source_evidence"] = None
            sha, object_key = sources.get(row["document_id"], (None, None))
            row["source_sha256"] = sha
            row["source_pdf_object_key"] = object_key
            row["source_pdf_local_path"] = (
                f"/mnt/e/nizam-data/{object_key}" if object_key else None)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "all active stored instruments and nodes; SQL-only screening, not source verification",
        "counts": {"instruments_inspected": instruments, "documents_inspected": documents,
                   "parsed_nodes_inspected": nodes, "toc_entries_inspected": toc_entries,
                   "pending_s7_candidates": pending_s7,
                   "same_label_different_parent_groups_neutral": reused_label_across_parents,
                   "active_unassigned_blocks": unassigned_blocks,
                   "heuristic_flags_by_category": dict(Counter(row["category"] for row in findings)),
                   "affected_document_count": len({row["document_id"] for row in findings})},
        "findings": findings,
        "caveat": "Flags are screening leads only. Each needs PDF/page and surrounding-block review before correction. Categories not inferable from stored structure remain unverified.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.pack)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
