"""Validate returned blocked-review answers; never promote them to the DB."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from tools.second_parser_release import _load_run, verify_state


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_schema(answer: dict, schema: dict) -> list[str]:
    """Enforce the pack's closed, simple response schema without new fields."""
    if not isinstance(answer, dict):
        return ["response must be a JSON object"]
    errors = []
    properties = schema["properties"]
    for key in schema["required"]:
        if key not in answer:
            errors.append(f"required field missing: {key}")
    for key, value in answer.items():
        spec = properties.get(key)
        if spec is None:
            errors.append(f"field not in response schema: {key}")
            continue
        allowed = spec.get("type")
        if allowed is not None:
            types = allowed if isinstance(allowed, list) else [allowed]
            matches = any({
                "string": lambda: isinstance(value, str),
                "null": lambda: value is None,
                "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
                "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
                "array": lambda: isinstance(value, list),
            }[name]() for name in types)
            if not matches:
                errors.append(f"schema type mismatch: {key}")
                continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"schema enum mismatch: {key}")
        if isinstance(value, str) and len(value) < spec.get("minLength", 0):
            errors.append(f"schema minimum length: {key}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in spec and value < spec["minimum"]:
                errors.append(f"schema minimum: {key}")
            if "maximum" in spec and value > spec["maximum"]:
                errors.append(f"schema maximum: {key}")
        if isinstance(value, list):
            if spec.get("uniqueItems") and len(set(map(str, value))) != len(value):
                errors.append(f"schema duplicate array item: {key}")
            item_type = spec.get("items", {}).get("type")
            for item in value:
                if item_type == "string" and not isinstance(item, str):
                    errors.append(f"schema array item type: {key}")
                if item_type == "integer" and (not isinstance(item, int)
                                               or isinstance(item, bool)):
                    errors.append(f"schema array item type: {key}")
    return errors


def validate_one(case: dict, answer: dict, pack: Path,
                 image_hashes: dict[str, str]) -> list[str]:
    errors = []
    if answer.get("case_id") != case["case_id"]:
        errors.append("case_id differs from question")
    verdict = answer.get("verdict")
    if verdict not in case["allowed_verdicts"]:
        errors.append("verdict is not an allowed choice")
    observed = answer.get("observed_on_page")
    if not isinstance(observed, str) or len(observed.strip()) < 20:
        errors.append("observed_on_page needs a specific source observation")
    if answer.get("reviewer_kind") not in ("tool", "human"):
        errors.append("reviewer_kind must be tool or human")
    if not isinstance(answer.get("reviewer_id"), str) or not answer[
            "reviewer_id"].strip():
        errors.append("reviewer_id is required")
    confidence = answer.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append("confidence must be a number from 0 to 1")
    cited = answer.get("evidence_image_paths")
    if not isinstance(cited, list) or not cited:
        errors.append("cite at least one supplied image")
        cited = []
    allowed_images = {row["path"]: row["sha256"] for row in case["images"]
                      if "sha256" in row}
    for path in cited:
        if not isinstance(path, str) or path not in allowed_images:
            errors.append(f"image is not part of this case: {path!r}")
            continue
        if path not in image_hashes:
            image = pack / path
            image_hashes[path] = _sha(image) if image.is_file() else "missing"
        if image_hashes[path] != allowed_images[path]:
            errors.append(f"image SHA-256 changed: {path}")
    if verdict == "absent_in_official_source":
        if case["defect_type"] != "unresolved_contents_promise":
            errors.append("source absence is only a TOC verdict")
        if answer.get("reviewer_kind") != "human":
            errors.append("source absence requires actual human page review")
        page_count = (case.get("source_pdf") or {}).get("page_count")
        cited_pages = {row["page"] for row in case["images"]
                       if row.get("role") == "full_page" and row["path"] in cited}
        whole_pdf_cited = (isinstance(page_count, int) and page_count > 0
                           and cited_pages == set(range(1, page_count + 1)))
        if (case["how_found"]["body_search"]["coverage_limited"]
                and not whole_pdf_cited):
            errors.append("body-page search is limited; cite every PDF page or ask for more pages")
        if not answer.get("exact_printed_text"):
            errors.append("absence needs an exact nearby printed section quote")
    if verdict == "operative_text_present_parser_missed":
        if not isinstance(answer.get("body_page"), int):
            errors.append("operative text requires its exact body_page")
        if not answer.get("exact_printed_text"):
            errors.append("operative text requires an exact printed quote")
    if verdict == "needs_more_pages_or_review":
        pages = answer.get("requested_additional_pages")
        if not isinstance(pages, list) or not pages or any(
                not isinstance(page, int) or page < 1 for page in pages):
            errors.append("request positive page numbers for further review")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--responses", type=Path)
    ap.add_argument("--offline", action="store_true",
                    help="skip the live DB freshness check for draft review")
    ap.add_argument("--summary-only", action="store_true",
                    help="print counts rather than every invalid case")
    ap.add_argument("--report", type=Path,
                    help="write the complete validation report to this path")
    args = ap.parse_args()
    pack = args.pack.resolve()
    responses = (args.responses or pack / "responses").resolve()
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((pack / "response-schema.json").read_text(encoding="utf-8"))
    if manifest["status"] != "ready":
        raise SystemExit("pack is not ready; repair images before importing answers")
    if not args.offline:
        state = _load_run(Path(manifest["signed_run"]))
        if not verify_state(state)["safe"]:
            raise SystemExit("signed blocked/released baseline is stale")
    questions = {}
    by_doc = defaultdict(set)
    for path in (pack / "questions").glob("doc-*/*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case["case_id"] in questions:
            raise SystemExit(f"duplicate question {case['case_id']}")
        questions[case["case_id"]] = case
        if case["needs_new_source_classification"]:
            by_doc[case["document_id"]].add(case["case_id"])
    if len(questions) != manifest["counts"]["questions"]:
        raise SystemExit("question count differs from manifest")
    seen = set()
    valid = set()
    templates_pending = set()
    errors = {}
    hashes = {}
    for path in responses.rglob("*.json") if responses.is_dir() else []:
        case_id = path.stem
        if case_id in seen:
            errors[case_id] = ["duplicate response file"]
            continue
        seen.add(case_id)
        case = questions.get(case_id)
        if case is None:
            errors[case_id] = ["no matching live-pack question"]
            continue
        try:
            answer = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors[case_id] = [f"invalid JSON: {exc}"]
            continue
        if answer == case.get("response_template"):
            templates_pending.add(case_id)
            continue
        found = validate_schema(answer, schema)
        found.extend(validate_one(case, answer, pack, hashes))
        if found:
            errors[case_id] = found
        else:
            valid.add(case_id)
    reviewed = [case for case in questions.values()
                if not case["needs_new_source_classification"]]
    report = {
        "pack": str(pack), "responses_seen": len(seen),
        "live_signed_snapshot_checked": not args.offline,
        "pending_templates": len(templates_pending),
        "pending_template_case_ids": sorted(templates_pending),
        "valid_proposals": len(valid), "invalid_responses": errors,
        "valid_case_ids": sorted(valid),
        "already_reviewed_repair_cases": len(reviewed),
        "new_source_questions": sum(map(len, by_doc.values())),
        "new_source_questions_unanswered": sum(
            len(ids - valid) for ids in by_doc.values()),
        "documents_with_all_new_source_answers": sum(
            ids <= valid for ids in by_doc.values()),
        "verdicts": dict(Counter(
            json.loads(path.read_text(encoding="utf-8")).get("verdict")
            for path in responses.rglob("*.json")
            if path.stem in valid)),
        "warning": "Valid proposals are not adjudications or release approval.",
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    if args.summary_only:
        report = {key: value for key, value in report.items()
                  if key not in ("invalid_responses", "valid_case_ids",
                                 "pending_template_case_ids")}
        report["invalid_response_count"] = len(errors)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
