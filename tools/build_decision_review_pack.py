"""Build the owner's local decision-review pack from decision cards.

Cards (one per blocked document, written by the card agents to
.artifacts/decision-review/cards/batch-*.json; schema in
.artifacts/decision-review/CARD-BRIEF.md) become one self-contained HTML page:
every open question with its page images, options and their effects, a notes
box, progress kept in the browser, and an "Export answers JSON" button. The
export is a proposed decision for the lead to validate
(tools/validate_decision_review_export.py) and carry out. Nothing here touches
the database.

    python tools/build_decision_review_pack.py
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CARDS = REPO / ".artifacts" / "decision-review" / "cards"
OUT = REPO / ".artifacts" / "decision-review-pack"
RENDER_ROOT = REPO / ".artifacts" / "release-work-2026-09-24"
TEMPLATE = Path(__file__).with_name("decision_review_template.html")


def card_sha256(card: dict) -> str:
    body = {k: v for k, v in card.items() if k != "card_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def check_card(card: dict) -> list[str]:
    problems = []
    for field in ("document_id", "title", "needs_owner", "kind", "questions"):
        if field not in card:
            problems.append(f"missing {field}")
    if problems:
        return problems
    if card["needs_owner"] and card["kind"] != "ocr-review" and not card["questions"]:
        problems.append("needs_owner but no questions")
    seen = set()
    for q in card["questions"]:
        if q.get("id") in seen:
            problems.append(f"duplicate question id {q.get('id')}")
        seen.add(q.get("id"))
        values = [o.get("value") for o in q.get("options", [])]
        if len(values) < 2 or len(set(values)) != len(values):
            problems.append(f"{q.get('id')}: options need two or more distinct values")
        if "other" not in values:
            problems.append(f"{q.get('id')}: no 'other' option")
        if q.get("recommended") not in (None, *values):
            problems.append(f"{q.get('id')}: recommended is not an option")
        for page in q.get("pages", []):
            path = RENDER_ROOT / page.get("render", "")
            if not path.is_file():
                problems.append(f"{q.get('id')}: render missing {page.get('render')}")
            elif page.get("sha256") and hashlib.sha256(path.read_bytes()).hexdigest() != page["sha256"]:
                problems.append(f"{q.get('id')}: render sha256 differs {page.get('render')}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cards", type=Path, default=CARDS)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    cards, problems = [], {}
    for path in sorted(args.cards.glob("batch-*.json")):
        for card in json.loads(path.read_text(encoding="utf-8")):
            card.setdefault("summary", "")
            card.setdefault("context", "")
            card.setdefault("reason", "")
            issues = check_card(card)
            if issues:
                problems[f"{path.name}:{card.get('document_id')}"] = issues
                if any(i.startswith("missing") for i in issues):
                    continue
            card["source_file"] = path.name
            card["card_sha256"] = card_sha256(card)
            cards.append(card)
    ids = [c["document_id"] for c in cards]
    dupes = sorted({d for d in ids if ids.count(d) > 1})
    if dupes:
        problems["duplicate documents"] = [str(d) for d in dupes]
    cards.sort(key=lambda c: (not c["needs_owner"] or not c["questions"], c["document_id"]))
    pack_sha = hashlib.sha256("".join(c["card_sha256"] for c in cards).encode()).hexdigest()
    built = datetime.datetime.now().isoformat(timespec="seconds")
    data = {"pack_sha256": pack_sha, "built_at": built, "cards": cards,
            "render_base": "../release-work-2026-09-24/"}

    args.out.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DECISION_REVIEW_DATA__*/", encoded)
    (args.out / "index.html").write_text(html, encoding="utf-8")
    manifest = {"schema": "nizam.decision_review_pack.v1", "pack_sha256": pack_sha, "built_at": built,
                "cards": [{"document_id": c["document_id"], "card_sha256": c["card_sha256"],
                           "needs_owner": c["needs_owner"], "kind": c["kind"],
                           "questions": [{"id": q["id"], "options": [o["value"] for o in q["options"]]}
                                         for q in c["questions"]]} for c in cards]}
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    questions = sum(len(c["questions"]) for c in cards if c["needs_owner"])
    print(json.dumps({"output": str(args.out / "index.html"), "documents": len(cards),
                      "documents_needing_owner": sum(1 for c in cards if c["needs_owner"] and c["questions"]),
                      "questions": questions, "problems": problems}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
