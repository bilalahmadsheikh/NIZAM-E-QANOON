"""Create editable, unanswered response files mirroring a blocked review pack."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def initialize(pack: Path) -> dict[str, int]:
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "ready":
        raise ValueError("review pack is not ready")
    questions = sorted((pack / "questions").glob("doc-*/*.json"))
    if len(questions) != manifest["counts"]["questions"]:
        raise ValueError("question count differs from manifest")
    created = existing = 0
    for question_path in questions:
        case = json.loads(question_path.read_text(encoding="utf-8"))
        if case["case_id"] != question_path.stem or case["document_id"] != int(question_path.parent.name[4:]):
            raise ValueError(f"question identity mismatch: {question_path}")
        target = pack / "responses" / question_path.parent.name / question_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8") as stream:
                json.dump(case["response_template"], stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            created += 1
        except FileExistsError:
            existing += 1
    return {"questions": len(questions), "created": created, "preserved_existing": existing}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(initialize(args.pack.resolve()), indent=2))


if __name__ == "__main__":
    main()
