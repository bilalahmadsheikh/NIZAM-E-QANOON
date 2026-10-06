"""Read-only, release-safe probe for missing opening section 1.

Select only live, still-blocked expressions with one TOC gap and no S7 or
boundary blocker. Try a few character-count-preserving text-layer corrections
in memory, then report the candidates that remove the gap without losing any
existing section or source character. This is *triage*, not source review or
permission to write a legal tree.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from nizam.storage import legal_write
from nizam.workers.segment import build, reviewed_structural_overrides
from tools.second_parser_release import _load_run, verify_state


def suggestions(text: str):
    """Yield conservative same-length trial edits, never applied to the DB."""
    seen = set()

    # A printed 1 misread as lowercase l at the opening heading. The precise
    # glyph still needs visual confirmation from the official page.
    for match in re.finditer(
        r"(?<![A-Za-z0-9])l(?=\.[ \t\n]{0,12}"
        r"(?:Short\s+title|Commencement|Title\s+and\s+commencement))",
        text, re.I,
    ):
        pos = match.start()
        before = text[max(0, pos - 5):min(len(text), pos + 65)]
        after = before[:pos - max(0, pos - 5)] + "1" + before[pos - max(0, pos - 5) + 1:]
        if before not in seen and text.count(before) == 1:
            seen.add(before)
            yield "one_glyph_l_to_1", before, after

    # A number in a separate print column can be collapsed by extraction to
    # one space before subsection (1). A newline is the same character count.
    for match in re.finditer(r"(?<!\d)1 (?=\(\s*1\s*\)\s*[A-Za-z])", text):
        pos = match.start()
        before = text[pos:min(len(text), pos + 65)]
        after = "1\n" + before[2:]
        if before not in seen and text.count(before) == 1:
            seen.add(before)
            yield "column_gap_before_first_subsection", before, after

    # A PDF may drop the printed number but leave two whitespace characters
    # at the head of its block. Reuse those positions for a citable label.
    if re.match(r"^ \nShort\s+title", text, re.I):
        before = text[:min(len(text), 65)]
        after = "1." + before[2:]
        if before not in seen and text.count(before) == 1:
            yield "missing_number_in_whitespace", before, after


def _section_keys(inst) -> set[tuple[str, str]]:
    return {(str(row["kind"]), str(row["label"]))
            for row in inst.provisions if row["kind"] in ("section", "article")}


def _ledger(inst) -> tuple[int, int]:
    return len(inst.block_roles), sum(row[3] for row in inst.block_roles)


def page_is_contents(blocks: list[dict], page_no: int) -> bool:
    """Do not turn an index entry into operative law, even if TOC joins pass."""
    page_text = "\n".join(b["text"] for b in blocks if b["page_no"] == page_no)
    return bool(re.search(r"(?im)^\s*(?:table\s+of\s+)?contents\s*$", page_text))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-documents", type=int, default=50)
    args = ap.parse_args()
    state = _load_run(args.run.resolve())
    freshness = verify_state(state)
    if not freshness["safe"]:
        raise SystemExit("signed release baseline is stale; refusing probe")
    fresh = set(freshness["fresh_target_ids"])
    targets = {t["document_id"]: t for t in state["targets"]
               if t["instrument_id"] in fresh
               and t["toc_count"] == 1 and t["s7_count"] == 0
               and t["boundary_count"] == 0}
    toc_docs = {t["document_id"] for t in state["toc"]
                if t["instrument_id"] in fresh
                and str(t.get("printed_label", "")).strip().rstrip(".") == "1"}
    chosen = sorted(toc_docs & targets.keys())[:args.max_documents]
    live_rows = {r[0]: r for r in legal_write.documents_needing_segmentation(
        redo=True, include_review=True) if r[0] in chosen}

    yielded = []
    examined = []
    for doc_id in chosen:
        row = live_rows.get(doc_id)
        if row is None:
            continue
        (document_id, sha, observation_id, source_id, title, year,
         _kind, source_url) = row
        target = targets[doc_id]
        if (observation_id != target["source_observation_id"]
                or sha != target["source_sha256"]):
            continue
        blocks = legal_write.blocks_for(doc_id)
        existing = legal_write.segmentation_patches_for(observation_id)
        reviewed = legal_write.structural_resolutions_for(doc_id)
        common = dict(
            toc_dispositions=legal_write.toc_dispositions_for(observation_id),
            structural_resolutions=reviewed,
            structural_overrides=reviewed_structural_overrides(
                reviewed, existing) or None,
        )
        baseline, baseline_seg = build(
            doc_id, sha, observation_id, source_id, title, year, source_url,
            blocks, legal_write.observed_on(observation_id), existing, **common)
        baseline_gaps = sum(t.get("provision_key") is None
                            for t in baseline.toc_entries)
        if baseline_gaps != 1 or baseline_seg.repeated_labels_demoted != 0:
            continue
        examined.append(doc_id)
        old_sections = _section_keys(baseline)
        old_ledger = _ledger(baseline)
        for block in blocks:
            if block["page_no"] > 8:
                continue
            if page_is_contents(blocks, block["page_no"]):
                continue
            for kind, before, after in suggestions(block["text"]):
                assert len(before) == len(after)
                # The target block's own opening text is the unique locator.
                match_text = block["text"][:min(len(block["text"]), 80)].strip()
                if not match_text or sum(
                    b["page_no"] == block["page_no"]
                    and match_text.casefold() in b["text"].casefold()
                    for b in blocks) != 1:
                    continue
                patch = {"id": "read-only-probe", "page_no": block["page_no"],
                         "match_text": match_text,
                         "before_text": before, "after_text": after}
                try:
                    candidate, segment_result = build(
                        doc_id, sha, observation_id, source_id, title, year,
                        source_url, blocks, legal_write.observed_on(observation_id),
                        existing + [patch], **common)
                except (ValueError, KeyError):
                    continue
                new_sections = _section_keys(candidate)
                gaps = sum(t.get("provision_key") is None
                           for t in candidate.toc_entries)
                if (gaps != 0 or segment_result.repeated_labels_demoted != 0
                        or _ledger(candidate) != old_ledger
                        or not old_sections <= new_sections
                        or ("section", "1") not in new_sections):
                    continue
                yielded.append({
                    "document_id": doc_id,
                    "instrument_id": target["instrument_id"],
                    "source_observation_id": observation_id,
                    "source_sha256": sha,
                    "source_block_id": block["id"],
                    "source_page": block["page_no"],
                    "proposal_kind": kind,
                    "match_text": match_text,
                    "before_text": before,
                    "after_text": after,
                    "provisions_before": len(baseline.provisions),
                    "provisions_after": len(candidate.provisions),
                    "sections_before": len(old_sections),
                    "sections_after": len(new_sections),
                    "ledger_entries": old_ledger[0],
                    "ledger_characters": old_ledger[1],
                    "review_state": "needs_official_page_review",
                })

    report = {"signed_run": str(args.run), "baseline_released":
              freshness["released_baseline"], "examined_documents": examined,
              "candidates": yielded}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({"examined": len(examined), "candidates": len(yielded),
                      "documents": sorted({r["document_id"] for r in yielded}),
                      "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
