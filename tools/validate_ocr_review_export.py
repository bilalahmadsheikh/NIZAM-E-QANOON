"""Validate a human OCR-review JSON export against its immutable local pack.

This does not adjudicate or promote a candidate. A later writer must also check
the current active source and candidate identities in the database.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA = "nizam.ocr_page_review.v1"


def validate(export: dict, manifest: dict, pack_dir: Path) -> list[str]:
    errors: list[str] = []
    for key in ("schema", "document_id", "source_sha256", "result_sha256",
                "candidate_engine", "source_page_count", "candidate_page_count"):
        if export.get(key) != manifest.get(key):
            errors.append(f"{key} differs from source review pack")
    if export.get("schema") != SCHEMA:
        errors.append("unsupported schema")
    if not str(export.get("reviewer_name") or "").strip():
        errors.append("reviewer_name is required")
    pages = {page["page_no"]: page for page in manifest["pages"]}
    seen: set[int] = set()
    for collection in ("decisions", "reviewed_unresolved"):
        entries = export.get(collection, [])
        if not isinstance(entries, list):
            errors.append(f"{collection} must be a list")
            continue
        for item in entries:
            if not isinstance(item, dict):
                errors.append(f"{collection} contains a non-object")
                continue
            number = item.get("page_no")
            page = pages.get(number)
            if page is None or number in seen:
                errors.append(f"unknown or repeated page {number}")
                continue
            seen.add(number)
            if item.get("document_id") != manifest["document_id"]:
                errors.append(f"page {number}: document ID mismatch")
            if item.get("candidate_text_sha256") != page["candidate_text_sha256"]:
                errors.append(f"page {number}: OCR text hash mismatch")
            if item.get("reviewed_source_image") is not True:
                errors.append(f"page {number}: source-image review checkbox absent")
            if not (pack_dir / page["image"]).is_file():
                errors.append(f"page {number}: source image missing")
            if collection == "decisions":
                if item.get("decision") not in ("accepted", "rejected"):
                    errors.append(f"page {number}: invalid decision")
                # A reviewer may export before shadow candidates are imported;
                # the exact OCR-text hash still binds that null-ID review.
                if (item.get("candidate_id") is not None
                        and item.get("candidate_id") != page["candidate_id"]):
                    errors.append(f"page {number}: candidate ID mismatch")
                if item.get("source_image") != page["image"]:
                    errors.append(f"page {number}: image path mismatch")
                if item.get("decision") == "rejected" and not str(item.get("reason") or "").strip():
                    errors.append(f"page {number}: rejection reason required")
    if not seen:
        errors.append("no reviewed pages")
    undecided = export.get("undecided_candidate_pages")
    if undecided != [page["page_no"] for page in manifest["pages"]
                     if page["page_no"] not in {d.get("page_no") for d in export.get("decisions", [])
                                                if isinstance(d, dict)}]:
        errors.append("undecided_candidate_pages differs from exported decisions")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", type=Path, help="JSON downloaded from the reviewer UI")
    parser.add_argument("--pack", type=Path, default=Path(".artifacts/ocr-review-pack-r5"))
    args = parser.parse_args()
    export = json.loads(args.export.read_text(encoding="utf-8"))
    document_id = export.get("document_id")
    if not isinstance(document_id, int) or document_id < 1:
        parser.error("export needs a positive document_id")
    pack_dir = args.pack / f"doc-{document_id}"
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    errors = validate(export, manifest, pack_dir)
    print(json.dumps({"valid": not errors, "document_id": document_id,
                      "decisions": len(export.get("decisions", [])),
                      "reviewed_unresolved": len(export.get("reviewed_unresolved", [])),
                      "errors": errors}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
