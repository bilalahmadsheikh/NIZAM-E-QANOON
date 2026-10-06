"""Checkpoint the live blocked-review queue without adjudicating or releasing.

This intentionally does not infer source verdicts. It reuses the signed pack,
response-validation report and live release views, then emits a bounded queue
for manual/source-backed work. Re-running it is safe and replaces only local
derived ledgers; no production writer is called.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from nizam.storage.db import connect
from tools.second_parser_release import TARGET_SQL, _blocker_rows, _blocker_signatures, _rows


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n",
                    encoding="utf-8")


def dump_lines(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")


def case_state(question: dict, answer: dict | None, valid: set[str],
               invalid: dict[str, list[str]], released: bool,
               blocker_current: bool = True) -> tuple[str, str]:
    case_id = question["case_id"]
    if released:
        return "released", "Confirm current case resolution from the live revision."
    if not blocker_current:
        if case_id in valid or question["workflow_lane"] == "repair_from_existing_source_review":
            return "correction_verified", "The exact old blocker is absent; check other live blockers."
        return "pending", "The old blocker is absent, but source classification remains unverified."
    if case_id in valid:
        if answer["verdict"] == "needs_more_pages_or_review":
            return "evidence_insufficient", "Obtain the requested source pages."
        return "response_validated", "Submit through the established adjudication/correction workflow."
    if case_id in invalid or (answer is not None and answer != question["response_template"]):
        return "response_written", "Fix the validation errors before adjudication."
    if question["workflow_lane"] == "repair_from_existing_source_review":
        return "correction_required", "Existing source review is recorded; implement its exact correction."
    return "pending", "Review the supplied source images and surrounding blocks."


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", required=True, type=Path)
    ap.add_argument("--validation-report", required=True, type=Path)
    ap.add_argument("--released-evidence", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--batch-size", type=int, default=20)
    args = ap.parse_args()
    if not 1 <= args.batch_size <= 20:
        raise SystemExit("batch size must be 1..20 under the release handoff")
    pack = args.pack.resolve()
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "ready":
        raise SystemExit("review pack is not ready")
    validation = json.loads(args.validation_report.read_text(encoding="utf-8"))
    valid = set(validation["valid_case_ids"])
    invalid = validation["invalid_responses"]
    defects = set()
    with args.released_evidence.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["evidence_status"] == "CONFIRMED_DEFECT":
                defects.add(row["instrument_id"])

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        measured_at = _rows(cur, "SELECT now() measured_at")[0]["measured_at"]
        canonical = _rows(cur, """SELECT id::text instrument_id,document_id,
            source_observation_id,expression_ordinal,source_sha256,
            short_title FROM instrument
            WHERE is_active AND duplicate_of IS NULL
            ORDER BY document_id,expression_ordinal,id""")
        released_ids = {row["instrument_id"] for row in _rows(cur,
            "SELECT id::text instrument_id FROM v_release_instrument")}
        targets = _rows(cur, TARGET_SQL)
        toc, s7 = _blocker_rows(cur, [row["instrument_id"] for row in targets])
        signatures = _blocker_signatures(targets, toc, s7)
    target_by_id = {row["instrument_id"]: row for row in targets}
    canonical_by_id = {row["instrument_id"]: row for row in canonical}
    live_toc = {(row["instrument_id"], row["toc_entry_id"]): row for row in toc}
    live_s7 = {(row["instrument_id"], row["id"]): row for row in s7}
    canonical_by_identity = defaultdict(list)
    for item in canonical:
        canonical_by_identity[(item["document_id"], item["source_observation_id"],
                               item["expression_ordinal"], item["source_sha256"])].append(item)
    if len(canonical) != len(released_ids) + len(targets):
        raise SystemExit("canonical population does not partition into released/blocked")
    questions = []
    for path in sorted((pack / "questions").glob("doc-*/*.json")):
        question = json.loads(path.read_text(encoding="utf-8"))
        if question["case_id"] != path.stem:
            raise SystemExit(f"case ID and filename disagree: {path}")
        questions.append((question, path))
    if len(questions) != manifest["counts"]["questions"]:
        raise SystemExit("question count differs from signed pack")
    per_instrument = defaultdict(list)
    case_rows = []
    matched_toc: set[tuple[str, int]] = set()
    matched_s7: set[tuple[str, str]] = set()
    for question, path in questions:
        pack_iid = question["blocked_instrument_id"]
        matches = canonical_by_identity.get((question["document_id"],
            question["source_observation_id"], question["expression_ordinal"],
            question["source_sha256"]), [])
        if len(matches) != 1:
            raise SystemExit(f"no unique live expression for {question['case_id']}")
        iid = matches[0]["instrument_id"]
        target = target_by_id.get(iid)
        is_released = iid in released_ids
        if not is_released and (target is None or
                question["source_sha256"] != target["source_sha256"] or
                question["source_observation_id"] != target["source_observation_id"]):
            raise SystemExit(f"source identity changed: {question['case_id']}")
        if question["defect_type"] == "unresolved_contents_promise":
            key = (iid, question["how_found"]["toc_entry_id"])
            blocker_current = key in live_toc
            if blocker_current:
                matched_toc.add(key)
        else:
            key = (iid, question["how_found"]["candidate_id"])
            blocker_current = key in live_s7
            if blocker_current:
                matched_s7.add(key)
        response_path = pack / "responses" / f"doc-{question['document_id']}" / (path.stem + ".json")
        answer = (json.loads(response_path.read_text(encoding="utf-8"))
                  if response_path.is_file() else None)
        state, next_action = case_state(question, answer, valid, invalid,
                                        is_released, blocker_current)
        row = {
            "case_id": question["case_id"], "instrument_id": iid,
            "pack_instrument_id": pack_iid,
            "document_id": question["document_id"],
            "source_observation_id": question["source_observation_id"],
            "expression_ordinal": question["expression_ordinal"],
            "source_sha256": question["source_sha256"],
            "blocker_signature": question["blocker_signature"],
            "pack_snapshot_stale": not is_released and (
                pack_iid != iid or question["blocker_signature"] != signatures[iid]),
            "exact_blocker_still_pending": blocker_current,
            "defect_type": question["defect_type"],
            "workflow_lane": question["workflow_lane"],
            "question_path": str(path), "response_path": str(response_path),
            "response_exists": response_path.is_file(),
            "response_verdict": answer.get("verdict") if answer else None,
            "state": state, "next_action": next_action,
            "validation_errors": invalid.get(question["case_id"], []),
            "prior_source_review_recorded": question["workflow_lane"] ==
                "repair_from_existing_source_review",
            "adjudication_accepted": bool(question["workflow_lane"] ==
                "repair_from_existing_source_review" and
                ((question["how_found"].get("existing_review") or {}).get("resolution") or
                 question["how_found"].get("existing_adjudication_id"))),
        }
        case_rows.append(row)
        per_instrument[iid].append(row)
    unpacked = []
    for kind, rows, matched, id_name in (
        ("toc", toc, matched_toc, "toc_entry_id"),
        ("s7", s7, matched_s7, "id"),
    ):
        for blocker in rows:
            key = (blocker["instrument_id"], blocker[id_name])
            if key in matched:
                continue
            item = canonical_by_id[blocker["instrument_id"]]
            case_id = f"{kind}-{item['document_id']}-{blocker[id_name]}"
            row = {
                "case_id": case_id, "instrument_id": item["instrument_id"],
                "document_id": item["document_id"],
                "source_observation_id": item["source_observation_id"],
                "source_sha256": item["source_sha256"],
                "defect_type": "unresolved_contents_promise" if kind == "toc"
                               else "repeated_citation_label",
                "workflow_lane": "needs_new_source_review",
                "question_path": None, "response_path": None,
                "response_exists": False, "response_verdict": None,
                "state": "pending", "next_action": "Generate a source-backed review case for this live blocker.",
                "needs_review_pack": True,
                "exact_blocker_still_pending": True,
                "source_block_id": blocker["source_block_id"],
                "source_page": blocker["source_page"],
                "printed_label": blocker["printed_label"],
                "adjudication_accepted": False,
            }
            unpacked.append(row)
            case_rows.append(row)
            per_instrument[item["instrument_id"]].append(row)
    instrument_rows = []
    for item in canonical:
        iid = item["instrument_id"]
        target = target_by_id.get(iid)
        cases = per_instrument.get(iid, [])
        instrument_rows.append({**item,
            "production_release_status": "released" if iid in released_ids else "blocked",
            "confirmed_released_defect": iid in defects,
            "release_decision_model": "computed_release_view_no_separate_manual_decision_row",
            "blockers": ({"toc": target["toc_count"], "s7": target["s7_count"],
                          "boundary": target["boundary_count"]} if target else
                         {"toc": 0, "s7": 0, "boundary": 0}),
            "blocker_signature": signatures.get(iid),
            "case_ids": [case["case_id"] for case in cases],
            "case_states": dict(Counter(case["state"] for case in cases)),
            "release_attempted_by_this_worker": False,
        })
    ready_queue = [row for row in instrument_rows if
                   row["production_release_status"] == "blocked" and
                   sum(row["blockers"].values()) == 1 and row["case_ids"]]
    ready_queue.sort(key=lambda row: (
        0 if row["case_states"].get("response_validated") else 1,
        0 if row["case_states"].get("correction_required") else 1,
        row["document_id"], row["expression_ordinal"]))
    queue = ready_queue[:args.batch_size]
    summary = {
        "measured_at": measured_at,
        "canonical": len(canonical), "released": len(released_ids),
        "blocked": len(targets), "pending_toc_rows": len(toc),
        "pending_s7_units": len(s7), "pack_questions": len(questions),
        "live_unpacked_cases": len(unpacked),
        "case_states": dict(Counter(row["state"] for row in case_rows)),
        "confirmed_defective_released_instruments": len(defects & released_ids),
        "blocked_without_pack_cases": sum(not per_instrument.get(row["instrument_id"])
                                          for row in targets),
        "selected_one_blocker_batch_size": len(queue),
        "release_operations_performed": 0,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    dump_lines(args.out / "cases.jsonl", case_rows)
    dump_lines(args.out / "live-unpacked-cases.jsonl", unpacked)
    dump_lines(args.out / "instruments.jsonl", instrument_rows)
    dump_lines(args.out / "unresolved-blockers.jsonl", [
        {"instrument_id": row["instrument_id"],
         "document_id": row["document_id"],
         "source_observation_id": row["source_observation_id"],
         "blockers": row["blockers"], "case_ids": row["case_ids"],
         "case_states": row["case_states"]}
        for row in instrument_rows
        if row["production_release_status"] == "blocked"])
    dump(args.out / "next-batch.json", {"count": len(queue), "instruments": queue})
    dump(args.out / "summary.json", summary)
    checkpoint = {"measured_at": measured_at, "summary": summary,
                  "selected_instrument_ids": [row["instrument_id"] for row in queue]}
    with (args.out / "checkpoints.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(checkpoint, default=str) + "\n")
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    main()
