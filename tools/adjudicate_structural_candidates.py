"""Independently adjudicate high-evidence S7 repeated-label candidates.

This is intentionally narrower than the segmenter.  It accepts a retyped unit
only when the immutable source block independently looks like a table/form row,
or when the printed TOC identifies the canonical occurrence and the candidate's
heading does not.  Everything else remains pending and therefore excluded from
``v_release_instrument``.  No source text, provision, or prior revision changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re

from nizam.storage.db import connect

METHOD = "nizam.structural_adjudicator/1"

_INLINE_ITEM = re.compile(r"(?:^|\n|\s{2,})(\d{1,4}[A-Z]?)\s*[.)]\s+\S")
_TOKEN = re.compile(r"\b\w+\b", re.UNICODE)
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_FORM_BLANK = re.compile(r"_{3,}|\.{5,}|…{2,}")


def evidence_rules(row: dict) -> tuple[list[str], dict]:
    text = row["candidate_text"] or ""
    tokens = _TOKEN.findall(text)
    numbers = _NUMBER.findall(text)
    inline_items = _INLINE_ITEM.findall(text)
    density = len(numbers) / max(len(tokens), 1)
    source = row["candidate_source_evidence"] or {}
    canonical_score = source.get("canonical_heading_score")
    candidate_score = source.get("candidate_heading_score")
    toc_heading = source.get("toc_heading")

    rules: list[str] = []
    if len(inline_items) >= 2:
        rules.append("multiple_numbered_items_in_one_source_block")
    if _FORM_BLANK.search(text):
        rules.append("printed_form_blank_or_dot_leader")
    if len(numbers) >= 6 and density >= 0.22:
        rules.append("numeric_table_density")
    if row["toc_selects_canonical"] and toc_heading:
        if not (source.get("candidate_heading") or "").strip():
            rules.append("printed_toc_selects_canonical_candidate_headingless")
        elif (canonical_score is not None and candidate_score is not None
              and canonical_score >= 0.80
              and canonical_score - candidate_score >= 0.20):
            rules.append("printed_toc_heading_score_selects_canonical")

    evidence = {
        "rules": rules,
        "candidate_block_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "canonical_block_sha256": hashlib.sha256(
            (row["canonical_text"] or "").encode("utf-8")).hexdigest(),
        "inline_item_count": len(inline_items),
        "numeric_token_count": len(numbers),
        "token_count": len(tokens),
        "numeric_density": round(density, 4),
        "toc_selects_canonical": row["toc_selects_canonical"],
        "source_page": row["source_page"],
        "canonical_source_page": row["canonical_source_page"],
        "candidate_preview": " ".join(text.split())[:240],
        "canonical_preview": " ".join((row["canonical_text"] or "").split())[:240],
    }
    return rules, evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="append machine-evidenced decisions; default is dry-run")
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.id,c.source_observation_id,c.document_id,c.instrument_id,
                   c.printed_label,c.source_page,c.canonical_source_page,
                   c.evidence AS candidate_source_evidence,
                   b.text AS candidate_text,cb.text AS canonical_text,
                   EXISTS (SELECT 1 FROM instrument_toc_entry e
                            WHERE e.instrument_id=c.instrument_id
                              AND e.provision_id=c.canonical_provision_id)
                       AS toc_selects_canonical
              FROM v_structural_adjudication_pending c
              JOIN text_block b ON b.id=c.source_block_id
              JOIN text_block cb ON cb.id=c.canonical_source_block_id
             ORDER BY c.document_id,c.source_page,c.id
        """)
        names = [d.name for d in cur.description]
        rows = [dict(zip(names, values)) for values in cur.fetchall()]

        accepted: list[tuple] = []
        rule_counts: dict[str, int] = {}
        for row in rows:
            rules, evidence = evidence_rules(row)
            if not rules:
                continue
            for rule in rules:
                rule_counts[rule] = rule_counts.get(rule, 0) + 1
            accepted.append((
                row["id"], "accept_non_citable", "machine_evidenced", METHOD,
                "Independent TOC/layout evidence confirms that this repeated "
                "label is not a second directly citable sibling.",
                json.dumps(evidence, ensure_ascii=False), METHOD,
            ))

        print(json.dumps({
            "pending": len(rows),
            "machine_evidenced": len(accepted),
            "left_for_source_or_human_review": len(rows) - len(accepted),
            "rule_counts": rule_counts,
            "applied": bool(args.apply),
        }, indent=2, ensure_ascii=False))

        if args.apply and accepted:
            with cur.copy("""
                COPY segmentation_structural_adjudication
                    (candidate_id,resolution,review_basis,method,rationale,evidence,decided_by)
                FROM STDIN
            """) as cp:
                for decision in accepted:
                    cp.write_row(decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
