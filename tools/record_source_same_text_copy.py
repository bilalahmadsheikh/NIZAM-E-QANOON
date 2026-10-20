"""Record that a landed copy prints the same text as a canonical document (migration 0062).

Two different files of one instrument -- typically the same portal serving it
twice -- must not be published twice. When the trees are byte-identical,
tools/resolve_exact_instrument_duplicates.py links them (0036). When the files
differ only in page furniture (page numbers, page-turn lines), the trees differ
too, and the link needs a recorded decision: a `source_same_text_copy` row
naming the copy's observation, its document, the canonical document, the
owner's answer and the diff that confirms the condition. The instrument-level
`duplicate_of` flag is then derived from it by tools/apply_source_same_text_copy.py
(post_replay_sequence.sh step 2b).

    python tools/record_source_same_text_copy.py --copy-document 2673 \\
        --canonical-document 2191 \\
        --export .artifacts/decision-review/exports/decision-review-2026-10-10-i.json \\
        --decision-document 2191 --question-id q2 --choice keep-2191 \\
        --observed "..." --recorded-by claude.agBW/same-text-copy/1         dry run
    ... --apply                                                             record

THE DIFF IS THE CONFIRMATION. Every text block of both documents is split into
words in reading order and aligned (difflib, no autojunk). The record is
refused unless every word on either side of every difference sits in a block
made ENTIRELY of page furniture -- a bare page number of up to three digits, or
a page-turn line such as "Cont...P/4" -- or is the page's own number standing
first on the page or last on it (a page head or foot fused into a line of
text). A word of law inside a differing span, or any other number inside a
block that also holds words, refuses the record: "rule 3" against "rule 4" is
a difference of law, not furniture. A file that also adds
or loses a substantive word is not this record's case.

It also refuses unless the cited export holds exactly one answer for that
document and question with that choice and confirmed page review, and checks
every rule migration 0062's trigger enforces, so the dry run says why.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = "tools/record_source_same_text_copy.py"

# A token of page furniture: a bare page number, a "Cont"/"Contd" marker, or a
# page-turn pointer "...P/4" (with or without "Cont" fused before it).
FURNITURE_TOKEN = re.compile(
    r"^(?:\d{1,3}"
    r"|Cont(?:d)?[.:]*"
    r"|(?:Cont(?:d)?[.:]*)?\.*(?:\u2026|\.{2,})?P/\d{1,3}\.?)$")

STATE_SQL = """
SELECT d.id, d.sha256, d.is_active,
       ARRAY(SELECT o.id FROM source_observation o
              WHERE o.sha256 = d.sha256 AND o.outcome = 'landed' ORDER BY o.id),
       EXISTS (SELECT 1 FROM instrument i
                WHERE i.document_id = d.id AND i.is_active AND i.duplicate_of IS NULL),
       EXISTS (SELECT 1 FROM source_same_text_copy s WHERE s.document_id = d.id),
       EXISTS (SELECT 1 FROM source_same_text_copy s WHERE s.canonical_document_id = d.id)
  FROM document d WHERE d.id = %s
"""
STATE_KEYS = ("id", "sha256", "is_active", "landed_observations",
              "has_canonical_instrument", "recorded_as_copy",
              "recorded_as_canonical")

INSERT_SQL = """
INSERT INTO source_same_text_copy
       (source_observation_id, document_id, canonical_document_id, observed,
        owner_decision, evidence, recorded_by)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id, recorded_at::text
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_furniture_block(text: str) -> bool:
    tokens = (text or "").split()
    return bool(tokens) and all(FURNITURE_TOKEN.match(t) for t in tokens)


def words(blocks: list[dict]) -> list[tuple[str, int, bool]]:
    """(word, page, is_furniture) in reading order.

    A word is furniture when its whole block is furniture, or when it is the
    page's own number standing as the first word of the page's first block or
    the last word of its last block -- a page head or foot fused into the first
    or last line of text (doc 2673 prints "3" above "(2) The secretary ...")."""
    first_block, last_block = {}, {}
    for b in blocks:
        if (b["text"] or "").split():
            first_block.setdefault(b["page_no"], b["id"])
            last_block[b["page_no"]] = b["id"]
    out = []
    for b in blocks:
        tokens = (b["text"] or "").split()
        whole = bool(tokens) and all(FURNITURE_TOKEN.match(t) for t in tokens)
        page = str(b["page_no"])
        for n, w in enumerate(tokens):
            head = n == 0 and first_block.get(b["page_no"]) == b["id"] and w == page
            foot = (n == len(tokens) - 1 and last_block.get(b["page_no"]) == b["id"]
                    and w == page)
            out.append((w, b["page_no"], whole or head or foot))
    return out


def compare(canonical_blocks: list[dict], copy_blocks: list[dict]) -> dict:
    """Align the two documents word by word and classify every difference."""
    a, b = words(canonical_blocks), words(copy_blocks)
    matcher = difflib.SequenceMatcher(a=[w for w, _, _ in a], b=[w for w, _, _ in b],
                                      autojunk=False)
    differences, substantive = [], []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        span = {
            "op": op,
            "canonical_pages": sorted({p for _, p, _ in a[i1:i2]}),
            "copy_pages": sorted({p for _, p, _ in b[j1:j2]}),
            "canonical_text": " ".join(w for w, _, _ in a[i1:i2]),
            "copy_text": " ".join(w for w, _, _ in b[j1:j2]),
        }
        # A word the text layer split or joined at a space -- doc 3525 reads the
        # superscript ordinal of '[24th July, 2006]' as '24 th' where doc 3247
        # reads '24th' -- prints the same characters: the two sides, with their
        # spaces removed, are identical. It is a spacing difference, not one of
        # law; any other character on either side keeps the span substantive.
        joined_a = "".join(w for w, _, _ in a[i1:i2])
        spacing = op == "replace" and bool(joined_a) and joined_a == "".join(w for w, _, _ in b[j1:j2])
        if spacing:
            span["kind"] = "spacing"
        differences.append(span)
        if not spacing and not all(furniture for _, _, furniture in a[i1:i2] + b[j1:j2]):
            substantive.append(span)
    return {"canonical_words": len(a), "copy_words": len(b),
            "ratio": round(matcher.ratio(), 5),
            "differences": differences, "substantive": substantive}


def answer_problem(answer: dict, choice: str) -> str | None:
    if answer.get("choice") != choice:
        return f"the export answers {answer.get('choice')!r}, not {choice!r}"
    if not answer.get("reviewed_page_images"):
        return "the owner did not confirm reviewing the page images"
    if not re.fullmatch(r"[0-9a-f]{64}", str(answer.get("card_sha256") or "")):
        return "the answer carries no card_sha256"
    return None


def state_problem(copy: dict | None, canonical: dict | None, observation: int | None,
                  released: bool, decision_document: int, choice: str) -> str | None:
    """The tool-side mirror of migration 0062's trigger.

    The owner's choice names the document kept -- the decision-review card's
    option is 'keep-<document id>' -- so the record's direction is checked
    against it: the copy can never be the document the owner chose to keep."""
    if copy is None or canonical is None:
        return "no such document"
    if copy["id"] == canonical["id"]:
        return "the copy and the canonical document are the same document"
    if copy["sha256"] == canonical["sha256"]:
        return ("the two documents are the same file; use "
                "tools/resolve_exact_instrument_duplicates.py (0036)")
    if not canonical["is_active"]:
        return f"canonical document {canonical['id']} is not active"
    if not canonical["has_canonical_instrument"]:
        return (f"canonical document {canonical['id']} has no active canonical "
                "instrument; a copy is never retired in favour of nothing")
    if canonical["recorded_as_copy"]:
        return f"canonical document {canonical['id']} is itself recorded as a copy"
    if copy["recorded_as_canonical"]:
        return f"document {copy['id']} is the canonical of another copy"
    if copy["recorded_as_copy"]:
        return f"document {copy['id']} is already recorded as a copy"
    if observation is None:
        return (f"document {copy['id']} has landed observations "
                f"{copy['landed_observations']}; name exactly one with --observation")
    if observation not in copy["landed_observations"]:
        return f"observation {observation} did not land document {copy['id']}"
    if released:
        return (f"observation {observation} has a released instrument; this route "
                "never withdraws a released tree")
    if decision_document not in (copy["id"], canonical["id"]):
        return (f"the owner decision is about document {decision_document}, "
                f"not {copy['id']} or {canonical['id']}")
    if choice != f"keep-{canonical['id']}":
        return (f"the owner's choice {choice!r} does not keep document "
                f"{canonical['id']}; the answer must read 'keep-{canonical['id']}'")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--copy-document", type=int, required=True)
    ap.add_argument("--canonical-document", type=int, required=True)
    ap.add_argument("--observation", type=int,
                    help="the copy's landed observation (inferred when there is one)")
    ap.add_argument("--export", required=True)
    ap.add_argument("--decision-document", type=int, required=True,
                    help="the document the owner's answer is filed under")
    ap.add_argument("--question-id", required=True)
    ap.add_argument("--choice", required=True)
    ap.add_argument("--observed", required=True,
                    help="what the comparison found, in words")
    ap.add_argument("--recorded-by", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.observed.strip() or not args.recorded_by.strip():
        raise SystemExit("refused: --observed and --recorded-by must not be blank")

    from nizam.storage import legal_write
    from nizam.storage.db import connect
    from nizam.workers.segment import owner_decision_answer

    citation = {"export": args.export, "document_id": args.decision_document,
                "question_id": args.question_id}
    export_path = Path(args.export)
    if not export_path.is_absolute():
        export_path = ROOT / export_path
    try:
        answer = owner_decision_answer(dict(citation, export=str(export_path)),
                                       args.decision_document)
    except ValueError as exc:
        raise SystemExit(f"refused: {exc}")
    problem = answer_problem(answer, args.choice)
    if problem:
        raise SystemExit(f"refused: {problem}")
    export = json.loads(export_path.read_text(encoding="utf-8-sig"))

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('source_same_text_copy')")
        if cur.fetchone()[0] is None:
            raise SystemExit("refused: migration 0062 is not applied")
        found = {}
        for doc in (args.copy_document, args.canonical_document):
            cur.execute(STATE_SQL, (doc,))
            row = cur.fetchone()
            found[doc] = dict(zip(STATE_KEYS, row)) if row else None
        copy, canonical = found[args.copy_document], found[args.canonical_document]
        observation = args.observation
        if observation is None and copy and len(copy["landed_observations"]) == 1:
            observation = copy["landed_observations"][0]
        cur.execute("SELECT EXISTS (SELECT 1 FROM v_release_instrument "
                    "WHERE source_observation_id = %s)", (observation,))
        released = bool(cur.fetchone()[0])
        problem = state_problem(copy, canonical, observation, released,
                                args.decision_document, args.choice)
        if problem:
            raise SystemExit(f"refused: {problem}")

    diff = compare(legal_write.blocks_for(args.canonical_document),
                   legal_write.blocks_for(args.copy_document))
    report = {"mode": "apply" if args.apply else "dry run",
              "copy": {"document_id": args.copy_document, "observation": observation,
                       "sha256": copy["sha256"]},
              "canonical": {"document_id": args.canonical_document,
                            "sha256": canonical["sha256"]},
              "canonical_words": diff["canonical_words"],
              "copy_words": diff["copy_words"], "ratio": diff["ratio"],
              "differences": diff["differences"]}
    if diff["substantive"]:
        report["refused"] = "differences outside page furniture"
        report["substantive"] = diff["substantive"]
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1

    owner_decision = dict(citation, choice=args.choice)
    evidence = {
        "copy_sha256": copy["sha256"], "canonical_sha256": canonical["sha256"],
        "copy_words": diff["copy_words"], "canonical_words": diff["canonical_words"],
        "ratio": diff["ratio"], "finding": "page_furniture_only",
        "differences": diff["differences"],
        "furniture_rule": ("every word of every difference lies in a block made "
                           "entirely of tokens matching " + FURNITURE_TOKEN.pattern
                           + ", or is the page's own number as the first word of "
                           "its first block or the last word of its last block"),
        "diff_tool": TOOL, "diff_tool_sha256": sha256_file(ROOT / TOOL),
        "export_sha256": sha256_file(export_path),
        "card_sha256": answer["card_sha256"], "answer": answer,
        "export_reviewer_name": export.get("reviewer_name"),
        "export_exported_at": export.get("exported_at"),
    }
    report["owner_decision"] = owner_decision
    if args.apply:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(INSERT_SQL, (observation, args.copy_document,
                                     args.canonical_document, args.observed,
                                     json.dumps(owner_decision, ensure_ascii=False),
                                     json.dumps(evidence, ensure_ascii=False),
                                     args.recorded_by))
            record_id, recorded_at = cur.fetchone()
        report["recorded"] = {"source_same_text_copy_id": record_id,
                              "recorded_at": recorded_at}
        report["next"] = "python tools/apply_source_same_text_copy.py --apply"
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
