"""Withdraw a recorded contents disposition on a cited owner decision (migration 0061).

A `toc_disposition_assertion` makes the segmenter materialise an empty,
operation='omitted' version for the printed contents entry it names. When the
owner decides that the entry is not a repeal or omission after all, this tool
records a `toc_disposition_withdrawal`: the assertion stays on record, and
`v_toc_disposition_assertion_latest` -- which every consumer reads -- stops
returning it. Nothing is updated or deleted.

    python tools/withdraw_toc_disposition.py --assertion-id 17 \\
        --export .artifacts/decision-review/exports/decision-review-2026-10-08-f.json \\
        --document-id 1457 --question-id q1 --choice body \\
        --reason "..." --withdrawn-by claude.agBW/toc-disposition-withdrawal/1   dry run
    ... --apply                                                                   record

It refuses unless:

  * the cited export exists and holds exactly one answer for that document and
    question (`nizam.workers.segment.owner_decision_answer`), the answer's
    choice is the one named, and the owner confirmed reviewing the page images;
  * the assertion exists, its observation was built into that document, it is
    the governing (latest) assertion for its printed entry, and it is not
    already withdrawn;
  * no instrument built from the assertion's observation is released.

The database trigger enforces the last three again; they are checked here
first so the dry run says why.

A withdrawal changes no tree by itself. The dry run lists the provision
versions that still cite the assertion: the one in the active tree remains
until the document is replayed, and the replay builds without the
disposition. Governing contract: migration 0061, docs/SCHEMA.md
`toc_disposition_withdrawal`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ASSERTION_SQL = """
SELECT a.id, a.source_observation_id, a.expression_ordinal, a.printed_label,
       a.printed_heading, a.disposition, a.source_block_id, a.source_page,
       a.reviewed_by, a.reviewed_at::text,
       (SELECT g.id FROM toc_disposition_assertion g
         WHERE g.source_observation_id = a.source_observation_id
           AND g.expression_ordinal = a.expression_ordinal
           AND g.source_block_id = a.source_block_id
           AND g.printed_label = a.printed_label
         ORDER BY g.reviewed_at DESC, g.id DESC LIMIT 1) AS governing_id,
       (SELECT w.id FROM toc_disposition_withdrawal w
         WHERE w.assertion_id = a.id) AS withdrawal_id,
       EXISTS (SELECT 1 FROM v_release_instrument r
                WHERE r.source_observation_id = a.source_observation_id) AS released,
       ARRAY(SELECT DISTINCT i.document_id FROM instrument i
              WHERE i.source_observation_id = a.source_observation_id
              ORDER BY 1) AS document_ids
  FROM toc_disposition_assertion a
 WHERE a.id = %s
"""

ASSERTION_KEYS = ("id", "source_observation_id", "expression_ordinal",
                  "printed_label", "printed_heading", "disposition",
                  "source_block_id", "source_page", "reviewed_by", "reviewed_at",
                  "governing_id", "withdrawal_id", "released", "document_ids")

REFERENCES_SQL = """
SELECT pv.id::text, p.label, p.path::text, i.id::text,
       (p.is_active AND i.is_active AND i.duplicate_of IS NULL) AS in_active_tree
  FROM provision_version pv
  JOIN provision p ON p.id = pv.provision_id
  JOIN instrument i ON i.id = p.instrument_id
 WHERE pv.source_toc_disposition_assertion_id = %s
 ORDER BY i.created_at, pv.id
"""

INSERT_SQL = """
INSERT INTO toc_disposition_withdrawal
       (assertion_id, reason, owner_decision, evidence, withdrawn_by)
VALUES (%s, %s, %s, %s, %s)
RETURNING id, withdrawn_at::text
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def answer_problem(answer: dict, choice: str) -> str | None:
    """Does the export's answer say what the withdrawal claims it says?"""
    if answer.get("choice") != choice:
        return (f"the export answers {answer.get('choice')!r}, "
                f"not {choice!r}")
    if not answer.get("reviewed_page_images"):
        return "the owner did not confirm reviewing the page images"
    if not re.fullmatch(r"[0-9a-f]{64}", str(answer.get("card_sha256") or "")):
        return "the answer carries no card_sha256"
    return None


def assertion_problem(row: dict | None, document_id: int) -> str | None:
    """The tool-side mirror of migration 0061's trigger, plus the
    already-withdrawn check the table's UNIQUE constraint makes."""
    if row is None:
        return "no such toc_disposition_assertion"
    if row["withdrawal_id"] is not None:
        return (f"assertion {row['id']} is already withdrawn "
                f"(toc_disposition_withdrawal {row['withdrawal_id']})")
    if row["governing_id"] != row["id"]:
        return (f"assertion {row['id']} is superseded by {row['governing_id']}; "
                "withdraw the governing assertion")
    if row["released"]:
        return (f"observation {row['source_observation_id']} has a released "
                "instrument; a withdrawal cannot change a released tree")
    if document_id not in (row["document_ids"] or []):
        return (f"the owner decision is about document {document_id}; "
                f"observation {row['source_observation_id']} was built into "
                f"{row['document_ids']}")
    return None


def build_record(*, assertion: dict, citation: dict, choice: str, answer: dict,
                 export: dict, export_sha256: str, references: list[dict],
                 note: str | None) -> tuple[dict, dict]:
    """The owner_decision and evidence payloads written with the row."""
    owner_decision = dict(citation, choice=choice)
    evidence = {
        "export_sha256": export_sha256,
        "card_sha256": answer["card_sha256"],
        "answer": answer,
        "export_reviewer_name": export.get("reviewer_name"),
        "export_exported_at": export.get("exported_at"),
        "assertion": {key: assertion[key] for key in (
            "id", "source_observation_id", "expression_ordinal",
            "printed_label", "printed_heading", "disposition",
            "source_block_id", "source_page", "reviewed_by", "reviewed_at")},
        "provision_versions_citing": {
            "active_tree": [r["provision_version_id"] for r in references
                            if r["in_active_tree"]],
            "superseded_trees": sum(not r["in_active_tree"] for r in references),
        },
        "tool": "tools/withdraw_toc_disposition.py",
    }
    if note:
        evidence["note"] = note
    return owner_decision, evidence


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assertion-id", type=int, required=True)
    ap.add_argument("--export", required=True,
                    help="decision-review export, as a path relative to the repo")
    ap.add_argument("--document-id", type=int, required=True)
    ap.add_argument("--question-id", required=True)
    ap.add_argument("--choice", required=True,
                    help="the answer's choice, as the export records it")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--withdrawn-by", required=True)
    ap.add_argument("--note", help="further context kept in evidence.note")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not args.reason.strip() or not args.withdrawn_by.strip():
        raise SystemExit("refused: --reason and --withdrawn-by must not be blank")
    if not re.fullmatch(r"q\d+", args.question_id):
        raise SystemExit(f"refused: question id {args.question_id!r}")

    from nizam.storage.db import connect
    from nizam.workers.segment import owner_decision_answer

    citation = {"export": args.export, "document_id": args.document_id,
                "question_id": args.question_id}
    export_path = Path(args.export)
    if not export_path.is_absolute():
        export_path = ROOT / export_path
    try:
        answer = owner_decision_answer(dict(citation, export=str(export_path)),
                                       args.document_id)
    except ValueError as exc:
        raise SystemExit(f"refused: {exc}")
    problem = answer_problem(answer, args.choice)
    if problem:
        raise SystemExit(f"refused: {problem}")
    export = json.loads(export_path.read_text(encoding="utf-8-sig"))

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('toc_disposition_withdrawal')")
        if cur.fetchone()[0] is None:
            raise SystemExit("refused: migration 0061 is not applied")
        cur.execute(ASSERTION_SQL, (args.assertion_id,))
        found = cur.fetchone()
        assertion = dict(zip(ASSERTION_KEYS, found)) if found else None
        problem = assertion_problem(assertion, args.document_id)
        if problem:
            raise SystemExit(f"refused: {problem}")
        cur.execute(REFERENCES_SQL, (args.assertion_id,))
        references = [{"provision_version_id": r[0], "label": r[1], "path": r[2],
                       "instrument_id": r[3], "in_active_tree": r[4]}
                      for r in cur.fetchall()]
        owner_decision, evidence = build_record(
            assertion=assertion, citation=citation, choice=args.choice,
            answer=answer, export=export, export_sha256=sha256_file(export_path),
            references=references, note=args.note)

        report = {
            "mode": "apply" if args.apply else "dry run",
            "assertion": evidence["assertion"],
            "owner_decision": owner_decision,
            "reason": args.reason,
            "withdrawn_by": args.withdrawn_by,
            "provision_versions_citing": references,
            "after": ("the entry drops out of v_toc_disposition_assertion_latest; "
                      "the active tree keeps its omitted version until the "
                      "document is replayed"),
        }
        if args.apply:
            cur.execute(INSERT_SQL, (args.assertion_id, args.reason,
                                     json.dumps(owner_decision, ensure_ascii=False),
                                     json.dumps(evidence, ensure_ascii=False),
                                     args.withdrawn_by))
            withdrawal_id, withdrawn_at = cur.fetchone()
            cur.execute("SELECT count(*) FROM v_toc_disposition_assertion_latest "
                        "WHERE id = %s", (args.assertion_id,))
            if cur.fetchone()[0] != 0:
                raise RuntimeError("the view still returns the withdrawn assertion")
            report["recorded"] = {"toc_disposition_withdrawal_id": withdrawal_id,
                                  "withdrawn_at": withdrawn_at}
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
