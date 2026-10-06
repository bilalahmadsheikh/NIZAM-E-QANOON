"""Validate an owner decision-review export against the pack it was made from.

Checks the schema, that each answer names a card and question in the pack's
manifest, that the card has not changed since the owner saw it (card_sha256),
that the choice is one of the question's options, and that "other" carries a
note. It does not carry out any decision.

    python tools/validate_decision_review_export.py EXPORT.json [--manifest PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_MANIFEST = (Path(__file__).resolve().parent.parent
                    / ".artifacts" / "decision-review-pack" / "manifest.json")


def validate(export: dict, manifest: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if export.get("schema") != "nizam.decision_review.v1":
        errors.append("unsupported schema")
    if not str(export.get("reviewer_name") or "").strip():
        errors.append("reviewer_name is required")
    if export.get("pack_sha256") != manifest.get("pack_sha256"):
        warnings.append("export was made from an older pack build; answers are matched card by card")
    cards = {c["document_id"]: c for c in manifest["cards"]}
    seen = set()
    for a in export.get("answers", []):
        where = f"{a.get('document_id')}:{a.get('question_id')}"
        if where in seen:
            errors.append(f"{where}: answered twice")
        seen.add(where)
        card = cards.get(a.get("document_id"))
        if card is None:
            errors.append(f"{where}: document not in the pack")
            continue
        if a.get("card_sha256") != card["card_sha256"]:
            errors.append(f"{where}: the card changed after it was answered; re-check it in the current pack")
        question = next((q for q in card["questions"] if q["id"] == a.get("question_id")), None)
        if question is None:
            errors.append(f"{where}: no such question")
            continue
        if a.get("choice") not in question["options"]:
            errors.append(f"{where}: choice {a.get('choice')!r} is not an option")
        if a.get("choice") == "other" and not str(a.get("note") or "").strip():
            errors.append(f"{where}: 'other' needs a note")
        if not a.get("reviewed_page_images"):
            errors.append(f"{where}: page images not confirmed as reviewed")
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=Path)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = ap.parse_args()
    export = json.loads(args.export.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors, warnings = validate(export, manifest)
    print(json.dumps({"valid": not errors, "answers": len(export.get("answers", [])),
                      "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=1))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
