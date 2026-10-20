"""Record a source-verified parser-input correction read from the official page.

`segmentation_curation_patch` (migration 0025) corrects the text the parser
reads, never `text_block`: extracted evidence stays immutable, and a replay of
the one document applies the patch. This is the lane for a printed number the
text layer misread -- "2IF" for 21F, "5." for 55. -- where linking the contents
row to the misnumbered node would render a wrong section number (INV-1).

    python tools/record_curation_patch.py --readings FILE.json          dry run
    python tools/record_curation_patch.py --readings FILE.json --apply  record

A reading:

    {"document_id": 4225, "page_no": 47,
     "match_text": "Remissions.__ Notwithstanding anything",   # >= 12 chars, unique on the page
     "before_text": "2IF. Remissions", "after_text": "21F. Remissions",
     "extracted_number": "2IF", "printed_number": "21F",
     "observed": "Page 47 prints '21F. Remissions.__ ...'",
     "render": ".artifacts/.../page-47.png", "render_sha256": "..."}

The dry run applies the locator exactly as the segmenter will (page plus a
case-insensitive fragment matching one block, `before_text` occurring once in
it) and refuses anything ambiguous. After --apply, replay the document with
`python -m nizam.workers.segment --document N --redo` (dry-run it first).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

from nizam.corpus.segment import _norm
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import (SECTION_GROUP_CAPTION_CHOICES, _bz_block_order_move_ok,  # group 33 (agent K6)
                                   _bz_section_group_caption_ok)
from nizam.workers.segment import (_bz_margin_heading_owner_ok, _bz_owner_schedule_part_ok,
                                   _bz_schedule_paragraph_heading_ok)
from nizam.workers.segment import (APPENDIX_OPENER_CHOICES, NAMED_SCHEDULE_ROW_CHOICES, ORDER_SUFFIX_CHOICES,
                                   UNLABELLED_OPENER_LABELS,
                                   OWNER_CITED_LABEL_CHOICES,
                                   SCHEDULE_GROUP_CAPTION_CHOICES, SUBSTITUTED_SCHEDULE_CHOICES,
                                   DF_BLOCK_KEYS, block_id_list_ok, decoded_underscore_dash_ok, long_suffix_openers_ok, contents_row_links_ok, level_cell_block_shape_ok,
                                   substituted_schedule_items_shape_ok,
                                   owner_cited_label_shape_ok, schedule_group_caption_shape_ok,
                                   named_schedule_row_shape_ok,
                                   order_suffix_label_shape_ok, owner_decision_answer,
                                   printed_heading_shape_ok,
                                   quoted_table_row_blocks_shape_ok,
                                   unlabelled_schedule_opener_shape_ok,
                                   unnumbered_opener_shape_ok)

CREATED_BY = "claude.ocr-digit-review/3"

# Every key a reading may carry. A key outside this set is refused, never
# dropped: a structural key the recorder does not know would otherwise record
# a patch without it, and the replay would build a different tree from the
# one the reading was checked against (doc 691's prototype keys, 6 Oct 2026).
STRUCTURAL_KEYS = frozenset({
    "source_unit_moves", "source_reviewed_grid_rows",
    # rule `reviewed_hyphen_rule_numbers` (agent JE, doc 4498)
    "source_hyphen_rule_numbers",
    # rule `reviewed_printed_rule_opener` (agent JE, doc 4431)
    "source_printed_rule_openers", "source_set_aside_units",
    # rules `reviewed_schedule_heading`, `reviewed_repeal_stub_cut` (stage 3, agent DC, doc 2703)
    "source_schedule_heading_blocks", "source_repeal_stub_cut_blocks",
    "source_body_start_block", "source_apparatus_blocks", "source_reparent_blocks",
    "source_continuation_parent_blocks", "source_unnumbered_section_openers",
    "source_unnumbered_part_headings", "source_schedule_row_openers",
    "source_schedule_form_group", "source_unlabelled_schedule_openers",
    "source_quoted_table_row_blocks", "source_printed_headings", "source_order_suffix_labels",
    # profile rule `named_schedule_row` (docs 1078, 1121; owner decisions 2026-10-07)
    "source_named_schedule_rows",
    # profile rule `reviewed_contents_alignment` (doc 1368; owner decision 2026-10-07)
    "source_contents_row_links",
    # profile rule `schedule_group_caption` (doc 1106; owner decision 2026-10-07 q3)
    "source_schedule_group_captions",
    # profile rule `owner_cited_label` (doc 1225; owner decision 2026-10-08 export -f q1)
    "source_owner_cited_labels",
    # profile rules `substituted_schedule_items`, `not_running_header_blocks`,
    # `level_cell_blocks` (doc 1431; owner decision 2026-10-08 export -f q2)
    "source_substituted_schedule_items", "source_not_running_header_blocks",
    "source_level_cell_blocks",
    # profile rule `half_paren_clause_label` (doc 1626; owner decision 2026-10-08 export -h q3)
    "source_half_paren_clause_blocks",
    # rules `contents_marker_block`, `heading_scan_section_only` (stage 3, agent DB, owner 11 Oct)
    "source_contents_marker_blocks", "source_heading_scan_section_only",
    # rules `reviewed_decimal_cut`, `reviewed_table_row_blocks`, `reviewed_division_continues`,
    # `reviewed_marked_label_cut` (stage 3, agent DF, owner 11-12 Oct)
    "source_decimal_cut_blocks", "source_table_row_blocks",
    "source_division_continues_blocks", "source_marked_label_cut_blocks",
    # rule `reviewed_marker_run_cut` (stage 3, agent DF, doc 4451)
    "source_marker_run_cut_blocks",
    # rule `reviewed_half_paren_items` (stage 3, agent DF, doc 4347 E6)
    "source_half_paren_item_blocks",
    # rule `leading_margin_heading_unit` for reviewed blocks (stage 3, agent DB, doc 252)
    "source_leading_margin_heading_blocks",
    # rules `reviewed_inline_table_blocks`, `reviewed_group_heading_blocks` (stage 3, agent DF, 4347 split)
    "source_inline_table_blocks", "source_group_heading_blocks",
    # rule `decoded_underscore_dash` (stage 3, agent DE; owner 12 Oct Q1)
    "source_decoded_underscore_dash",
    # rule `reviewed_long_suffix_section` (stage 3, agent DE; owner 12 Oct chat)
    "source_contents_region",   # rule `reviewed_contents_region` (agent JE, docs 4400/4137)
    "source_long_suffix_section_openers",
    # rule `reviewed_figure_subsections` (agent JE, doc 4521; owner export j q1)
    "source_figure_subsections",
    # rule `reviewed_margin_note_pieces` (agent JE, doc 4426)
    "source_margin_note_pieces",
    # export j ports (13 Oct 2026, builder BZ): agents JB (D flag, F, G, H, I) and JA (C, E, F, G, H)
    "source_statute_row_headings",
    "source_explanation_of_heading",
    "source_no_cut_blocks",
    "source_margin_heading_owners",
    "source_root_reparent_blocks",
    "source_chapter_over_part",
    "source_contents_schedule_rows",
    "source_form_text_blocks",
    "source_lettered_part_blocks",
    "source_unheaded_section_blocks",
    # rules `reviewed_list_item_text`, `reviewed_decimal_item_cut` (agent JE, docs 4408/4409/4416)
    "source_list_text_sections", "source_decimal_item_cut_blocks", "source_text_units",
    # rules `reviewed_quoted_definition_cut`, `reviewed_division_opener`, `reviewed_division_caption` (agent JE, doc 4426)
    "source_quoted_definition_cut_blocks", "source_division_openers", "source_division_captions",
    # rule `reviewed_chapter_resumes_body` (agent JE, doc 4400)
    "source_chapter_resumes_body_blocks",
    # export j group 5 ports (14 Oct 2026, builder BZ): agent JD
    "source_chapter_line_blocks",
    "source_marked_dash_section_blocks",
    "source_subsection_line_cut_blocks",
    "source_contents_named_divisions",
    # export j group 6 ports (agent JD): rule reviewed_division_line
    "source_division_line_blocks",
    # export j group 7 ports (agent JD): rules reviewed_dotted_letter_item, schedule_paragraph_printed_heading
    "source_dotted_letter_item_blocks", "source_schedule_paragraph_headings",
    # export j/l group 8 ports (agent JD): rule owner_supplied_schedule_part
    "source_owner_schedule_parts",
    # agent K1 (16 Oct): rule reviewed_marked_rule_label (a DF block key)
    "source_marked_rule_blocks",
    # group 14 (16 Oct): agent JD rule reviewed_clause_repeal_stub
    "source_clause_repeal_stub_blocks",
    # group 15 (16 Oct): agent K2 rule3 reviewed_table_close
    "source_table_close_blocks",
    # group 17 (16 Oct): agent K4 G-M
    "source_half_paren_roman_blocks",
    "source_bare_half_paren_subrule_blocks",
    "source_inserted_row_blocks",
    "source_bare_serial_row_blocks",
    "source_form_code_openers",
    # group 18 (16 Oct): agent K2 rule4 reviewed_bound_note
    "source_bound_notes",
    # group 38 (19 Oct): agent K6 reviewed_bracketed_rule
    "source_bracketed_rules",
    # group 37 (18 Oct): agent K6 reviewed_lettered_head
    "source_lettered_head_blocks",
    # group 33 (18 Oct): agent K6 reviewed_block_order, section_group_caption
    "source_block_order_moves",
    "source_section_group_captions",
    # group 32 (18 Oct): agent K6 reviewed_division_series
    "source_division_series_blocks",
    # group 29 (17 Oct): agent JF E
    "source_decoded_quote_cut_blocks",
    # group 28 (17 Oct): agent K6 H
    "source_inline_margin_notes",
    # group 27 (17 Oct): agent JF D
    "source_schedule_row_cells",
    # group 26 (17 Oct): agent JF A
    "source_long_romanette_cut_blocks",
    # group 24 (17 Oct): agent K6 F
    "source_hyphen_first_subsection_blocks",
    # group 23 (17 Oct): agent K6 E
    "source_digit_led_clause_labels",
    # group 22 (16 Oct): agent K6 D
    "source_fused_margin_tails",
    # group 19-20 (16 Oct): agent K4 Q, U, V; agent K6 C
    "source_part_line_blocks",
    "source_dotted_serial_row_blocks",
    "source_division_unit_openers",
    "source_division_note_blocks",
    # group 11 ports (16 Oct): agent K2
    "source_quoted_insertion_spans",
    "source_label_moves",
    "source_half_paren_subrule_blocks",
    "source_contents_page_column",
    "source_unstopped_contents_rows",
    # group 10 ports (16 Oct): agents K4, K5, K3
    "source_heading_line_stub_blocks",
    "source_quote_span_end_blocks",
    "source_percent_clause_blocks",
    "source_marked_subsection_cut_blocks",
    "source_chapter_opener_blocks",
    "source_section_word_part_blocks",
    "source_dash_label_section_blocks",
    "source_paired_repeal_stubs",
    "source_quoted_appendix_labels",
    "source_note_owner_blocks",
    "source_heading_lines"})
READING_KEYS = STRUCTURAL_KEYS | {
    "document_id", "page_no", "match_text", "before_text", "after_text", "observed",
    "defect", "fixes", "render", "render_sha256", "additional_render",
    "additional_render_sha256", "extracted_number", "printed_number", "all_observations", "exact_block_locator", "source_block_id",
    # informational: the owner's decision a text reading carries out (doc 1028),
    # kept verbatim in the evidence
    "owner_decision",
    # try-harness copies: `evidence` may only repeat the reading's own
    # structural keys; `id` is a harness label
    "evidence", "id"}


# Structural keys recorded by the generic branch: rules whose parser check is fail-closed on content, so the recorder
# checks only that every block id the entry names is a block of the document (keys ported 13 Oct 2026; each key here
# must ALSO be in STRUCTURAL_KEYS). A structural key with no recording branch is refused (see `dropped` below).
GENERIC_STRUCTURAL_KEYS = frozenset({
    "source_unit_moves", "source_reviewed_grid_rows",
    # rule `reviewed_hyphen_rule_numbers` (agent JE, doc 4498)
    "source_hyphen_rule_numbers",
    # rule `reviewed_printed_rule_opener` (agent JE, doc 4431)
    "source_printed_rule_openers", "source_set_aside_units",
    # rules `reviewed_figure_subsections` (doc 4521) and `reviewed_margin_note_pieces` (doc 4426) -- agent JE
    "source_figure_subsections", "source_margin_note_pieces",
    # export j ports (13 Oct 2026, builder BZ): data-gated keys whose parser check is fail-closed
    "source_statute_row_headings",
    "source_explanation_of_heading",
    "source_no_cut_blocks",
    "source_root_reparent_blocks",
    "source_chapter_over_part",
    "source_contents_schedule_rows",
    "source_form_text_blocks",
    "source_lettered_part_blocks",
    "source_unheaded_section_blocks",
    "source_list_text_sections",
    "source_text_units",
    "source_division_openers",
    "source_division_captions",
    # rule `reviewed_contents_region` (agent JE, docs 4400, 4137): its *_block_id fields are checked against the document
    "source_contents_region",
    # export j group 5 ports (agent JD): checked fail-closed by the segmenter
    "source_chapter_line_blocks",
    "source_marked_dash_section_blocks",
    "source_subsection_line_cut_blocks",
    "source_contents_named_divisions",
    "source_division_line_blocks",
    # export j group 7 ports (agent JD); J's citation is also checked against the export (below)
    "source_dotted_letter_item_blocks", "source_schedule_paragraph_headings",
    # export j/l group 8 ports (agent JD); O's citation is also checked against the export (below)
    "source_owner_schedule_parts",
    # group 14 (16 Oct): agent JD rule reviewed_clause_repeal_stub
    "source_clause_repeal_stub_blocks",
    # group 15 (16 Oct): agent K2 rule3 reviewed_table_close
    "source_table_close_blocks",
    # group 17 (16 Oct): agent K4 G-M
    "source_half_paren_roman_blocks",
    "source_bare_half_paren_subrule_blocks",
    "source_inserted_row_blocks",
    "source_bare_serial_row_blocks",
    "source_form_code_openers",
    # group 18 (16 Oct): agent K2 rule4 reviewed_bound_note
    "source_bound_notes",
    # group 38 (19 Oct): agent K6 reviewed_bracketed_rule
    "source_bracketed_rules",
    # group 37 (18 Oct): agent K6 reviewed_lettered_head
    "source_lettered_head_blocks",
    # group 33 (18 Oct): agent K6 reviewed_block_order, section_group_caption
    "source_block_order_moves",
    "source_section_group_captions",
    # group 32 (18 Oct): agent K6 reviewed_division_series
    "source_division_series_blocks",
    # group 29 (17 Oct): agent JF E
    "source_decoded_quote_cut_blocks",
    # group 28 (17 Oct): agent K6 H
    "source_inline_margin_notes",
    # group 27 (17 Oct): agent JF D
    "source_schedule_row_cells",
    # group 26 (17 Oct): agent JF A
    "source_long_romanette_cut_blocks",
    # group 24 (17 Oct): agent K6 F
    "source_hyphen_first_subsection_blocks",
    # group 23 (17 Oct): agent K6 E
    "source_digit_led_clause_labels",
    # group 22 (16 Oct): agent K6 D
    "source_fused_margin_tails",
    # group 19-20 (16 Oct): agent K4 Q, U, V; agent K6 C
    "source_part_line_blocks",
    "source_dotted_serial_row_blocks",
    "source_division_unit_openers",
    "source_division_note_blocks",
    # group 11 ports (16 Oct): agent K2
    "source_quoted_insertion_spans",
    "source_label_moves",
    "source_half_paren_subrule_blocks",
    "source_contents_page_column",
    "source_unstopped_contents_rows",
    # group 10 ports (16 Oct): agents K4, K5, K3; keyed entries carrying an owner_decision are checked below
    "source_heading_line_stub_blocks",
    "source_quote_span_end_blocks",
    "source_percent_clause_blocks",
    "source_marked_subsection_cut_blocks",
    "source_chapter_opener_blocks",
    "source_section_word_part_blocks",
    "source_dash_label_section_blocks",
    "source_paired_repeal_stubs",
    "source_quoted_appendix_labels",
    "source_note_owner_blocks",
    "source_heading_lines"})


def named_block_ids(value, key: str = "") -> set[int]:
    """Every int a structural entry names under a *_block, *_blocks, *_block_id or *_block_ids key (or as a list
    member of such a key)."""
    found: set[int] = set()
    if isinstance(value, dict):
        for inner_key, inner in value.items():
            found |= named_block_ids(inner, inner_key)
    elif isinstance(value, list):
        for inner in value:
            found |= named_block_ids(inner, key)
    elif type(value) is int and (key == "cells" or key.endswith(("_block", "_blocks", "_block_id", "_block_ids"))):
        found.add(value)
    return found


def reading_key_problem(reading: dict) -> str | None:
    """Why the recorder must refuse this reading's keys, or None.

    A key the recorder does not know is refused rather than dropped, and a
    harness `evidence.structural_overrides` copy must repeat the reading's own
    top-level structural keys (the recorder records only those)."""
    unknown = sorted(set(reading) - READING_KEYS)
    if unknown:
        return f"unknown reading key(s) {unknown}: the recorder would drop them"
    harness = reading.get("evidence") or {}
    harness = (harness.get("structural_overrides") or {}) if isinstance(harness, dict) else None
    if not isinstance(harness, dict) or any(
            key not in STRUCTURAL_KEYS or reading.get(key) != value
            for key, value in harness.items()):
        return "evidence.structural_overrides must repeat the reading's own structural keys"
    return None


def order_suffix_groups_ok(order_suffixes) -> bool:
    """A reading's `source_order_suffix_labels`: a non-empty list of well-shaped
    groups, distinct by the prints they name rather than by (kind, label) --
    two sections may each print a duplicate sub-section (2) (doc 1034) -- and
    no block in two groups."""
    # A block may be named twice WITHIN one group (profile rule `order_suffix_one_block`, doc 1626 r.4:
    # both prints of 'c)' in one block), never by two groups.
    return (isinstance(order_suffixes, list) and bool(order_suffixes)
            and all(order_suffix_label_shape_ok(v) for v in order_suffixes)
            and len({block_id for v in order_suffixes for block_id in v["source_block_ids"]})
            == sum(len(set(v["source_block_ids"])) for v in order_suffixes))


def unlabelled_opener_decision_check(openers: list[dict], document_id: int) -> None:
    """Raise unless every `source_unlabelled_schedule_openers` entry carries a
    label the segmenter can open ('SCHEDULE', or 'APPENDIX' under profile rule
    `unlabelled_appendix_opener`) and, for 'APPENDIX', cites an answer whose
    choice asks for the table to be held as the Appendix with its rows (doc
    1491 q1 'appendix-rows-by-serial')."""
    for v in openers:
        if v["label"] not in UNLABELLED_OPENER_LABELS:
            raise ValueError(f"source_unlabelled_schedule_openers label {v['label']!r} is not one of "
                             f"{sorted(UNLABELLED_OPENER_LABELS)}")
        if v["label"] == "APPENDIX":
            choice = owner_decision_answer(v["owner_decision"], document_id).get("choice")
            if choice not in APPENDIX_OPENER_CHOICES:
                raise ValueError(f"source_unlabelled_schedule_openers 'APPENDIX' cites "
                                 f"{v['owner_decision']['question_id']} choice {choice!r}, not one asking "
                                 "for appendix rows")


def order_suffix_decision_check(groups: list[dict], document_id: int) -> None:
    """Raise unless every `source_order_suffix_labels` group cites an answer
    whose choice keeps both prints, cited by order ('keep-both'; profile rule
    `order_suffix_label`, sections, sub-sections and -- doc 1457 s.20 --
    clauses)."""
    for v in groups:
        choice = owner_decision_answer(v["owner_decision"], document_id).get("choice")
        if choice not in ORDER_SUFFIX_CHOICES:
            raise ValueError(f"source_order_suffix_labels cites {v['owner_decision']['question_id']} "
                             f"choice {choice!r}, not 'keep-both'")


def substituted_schedule_decision_check(spans: list[dict], document_id: int) -> None:
    """Raise unless every `source_substituted_schedule_items` span cites an
    answer the export holds whose choice is 's2-text' (profile rule
    `substituted_schedule_items`, doc 1431 q2)."""
    for v in spans:
        choice = owner_decision_answer(v["owner_decision"], document_id).get("choice")
        if choice not in SUBSTITUTED_SCHEDULE_CHOICES:
            raise ValueError(f"source_substituted_schedule_items cites "
                             f"{v['owner_decision']['question_id']} choice {choice!r}, not 's2-text'")


def doc1431_block_problem(substituted, not_running, level_cells, position: dict, on_page: dict,
                          anchor_id: int, anchor_text: str) -> str | None:
    """Why the blocks named by the doc-1431 keys do not match the document
    and the reading's page, or None.

    `source_not_running_header_blocks` and `source_level_cell_blocks` name
    blocks on the reading's page (a level cell and its row are printed side
    by side). A `source_substituted_schedule_items` span opens at a block on
    the reading's page whose text (after the reading) is `source_text`; its
    owner section's first block and the block where the walk resumes may be
    on other pages, so they must be blocks of the document, in reading order
    owner < schedule < resume."""
    texts = {block_id: b["text"] for block_id, b in on_page.items()}
    texts[anchor_id] = anchor_text
    stray = sorted(set(not_running or []) - set(on_page))
    if stray:
        return f"source_not_running_header_blocks not on the reading's page: {stray}"
    stray = sorted({v[k] for v in level_cells or [] for k in ("cell_block_id", "row_block_id")} - set(on_page))
    if stray:
        return f"source_level_cell_blocks not on the reading's page: {stray}"
    for v in substituted or []:
        if v["schedule_block_id"] not in on_page:
            return "source_substituted_schedule_items schedule block is not on the reading's page"
        if _norm(texts[v["schedule_block_id"]]) != _norm(v["source_text"]):
            return "source_substituted_schedule_items source_text is not the schedule block's text"
        if any(v[k] not in position for k in ("owner_block_id", "resume_block_id")):
            return "source_substituted_schedule_items names a block outside the document"
        if not (position[v["owner_block_id"]] < position[v["schedule_block_id"]]
                < position[v["resume_block_id"]]):
            return "source_substituted_schedule_items blocks are not in reading order owner < schedule < resume"
    return None


def reading_cited_pages(reading: dict, document_id: int, page: int) -> set[int]:
    """The pages a reading cites: its own page, plus the page of its
    `additional_render` when that render is named by the project's render
    convention `docN-pP.png` for this document (its sha256 is verified with the
    reading). Used where a reviewed key may name blocks on a second page the
    reader rendered (an order-suffix group whose prints span two pages)."""
    pages = {page}
    extras = reading.get("additional_render") or []
    # one render, or a list of them (doc 4400's contents-region reading cites pp8-11; 14 Oct 2026)
    for extra in ([extras] if isinstance(extras, str) else list(extras)):
        found = re.fullmatch(rf"doc{document_id}-p(\d+)\.png", pathlib.Path(extra or "").name)
        if found:
            pages.add(int(found.group(1)))
    return pages


def repeated_locators(readings: list[dict]) -> set[int]:
    """Indices of readings whose (document, page, match_text, before_text)
    repeats an earlier reading in the same file. segmentation_curation_patch
    holds one patch per locator, so the second would fail at --apply after the
    dry run had passed (doc 1431 p29, 8 Oct 2026); refuse it at the dry run."""
    seen: set[tuple] = set()
    out: set[int] = set()
    for index, r in enumerate(readings):
        key = (r.get("document_id"), r.get("page_no"), r.get("match_text"), r.get("before_text"))
        if key in seen:
            out.add(index)
        seen.add(key)
    return out


def owner_cited_decision_check(owner_cited: list[dict], document_id: int) -> None:
    """Raise unless every `source_owner_cited_labels` entry cites an answer the
    export holds whose choice is one an owner-cited label carries out
    (OWNER_CITED_LABEL_CHOICES: doc 1225 q1 'contents', doc 1457 q3
    'open-at-p3'; profile rule `owner_cited_label`)."""
    for v in owner_cited:
        choice = owner_decision_answer(v["owner_decision"], document_id).get("choice")
        if choice not in OWNER_CITED_LABEL_CHOICES:
            raise ValueError(f"source_owner_cited_labels cites "
                             f"{v['owner_decision']['question_id']} choice {choice!r}, not one of "
                             f"{sorted(OWNER_CITED_LABEL_CHOICES)}")


def owner_cited_block_problem(item: dict, page_texts: dict) -> str | None:
    """Why one `source_owner_cited_labels` entry does not match its page, or
    None: the block must be on the reading's page; an opener's
    `source_prefix` must occur in it exactly once; a relabelled print's number
    must be printed in it as 'N.'."""
    text = page_texts.get(item["source_block_id"])
    if text is None:
        return f"block {item['source_block_id']} not on the reading's page"
    # agJB rule E `owner_cited_clause_label` (doc 3240): a clause entry's printed letter is printed '(x)' in its block.
    if item.get("kind") == "clause":
        return (None if re.search(r"\(\s*" + re.escape(item["printed_label"]) + r"\s*\)", text)
                else f"clause print ({item['printed_label']}) not printed in block {item['source_block_id']}")
    if item["printed_label"] is None:
        return (None if text.count(item["source_prefix"]) == 1
                else f"source_prefix not exactly once in block {item['source_block_id']}")
    if item.get("printed_bracketed") is True:
        # profile rule `owner_cited_label`, bracketed print (doc 1666): the unit's number is printed '(N)'
        return (None if re.search(rf"\(\s*{re.escape(item['printed_label'])}\s*\)", text)
                else f"bracketed print ({item['printed_label']}) not printed in block {item['source_block_id']}")
    # Exact owner-cited Roman section labels (4089): '(i)/(ii)' are the
    # printed top-level labels, not missing dotted numeric labels. Require
    # the print at the beginning of its source block, never a later reference.
    if item.get("kind") == "section" and re.fullmatch(r"[ivxlc]+", item["printed_label"]):
        return (None if re.match(r"\s*\(\s*" + re.escape(item["printed_label"]) + r"\s*\)", text)
                else f"Roman section print ({item['printed_label']}) not at start of block {item['source_block_id']}")
    # rule `owner_cited_compound_label` (agent JE): a compound print ('27-14 Legal Branch', '1.32.') needs no
    # closing dot, but may not sit inside a longer number ('1.32' in '1.132').
    # extension `owner_cited_lettered_compound_label` (agent JE): a lettered compound print too ('10-71A')
    if re.fullmatch(r"[0-9]{1,4}[.\-][0-9]{1,4}(?:[.\-]?[A-Z])?", item["printed_label"]):
        return (None if re.search(rf"(?<![0-9A-Za-z.\-]){re.escape(item['printed_label'])}(?![0-9])", text)
                else f"printed label {item['printed_label']!r} not printed in block {item['source_block_id']}")
    return (None if re.search(rf"(?<![0-9A-Za-z]){re.escape(item['printed_label'])}\s*\.", text)
            else f"printed label {item['printed_label']!r} not printed in block {item['source_block_id']}")


def _label_without_stop(label: str) -> str:
    """A named row's label as the recorder looks for it in the row: the
    printed post name without one closing stop (lead decision 8 Oct, doc 1106)."""
    value = _norm(label)
    return value[:-1].rstrip() if value.endswith(".") else value


def group_caption_decision_check(group_captions: list[dict], document_id: int) -> None:
    """Raise unless every `source_schedule_group_captions` entry cites an
    answer the export holds whose choice asks for rows held under their
    printed group captions (profile rule `schedule_group_caption`)."""
    for v in group_captions:
        choice = owner_decision_answer(v["owner_decision"], document_id).get("choice")
        if choice not in SCHEDULE_GROUP_CAPTION_CHOICES:
            raise ValueError(f"source_schedule_group_captions cites "
                             f"{v['owner_decision']['question_id']} choice "
                             f"{choice!r}, not one asking for rows by group caption")


def named_row_decision_check(named_rows: list[dict], document_id: int) -> None:
    """Raise unless every `source_named_schedule_rows` entry cites an answer
    the export holds whose choice asks for rows held by their printed post
    name (profile rule `named_schedule_row`): a named row carries out that
    answer, not merely any answer for the document."""
    for v in named_rows:
        choice = owner_decision_answer(v["owner_decision"], document_id).get("choice")
        if choice not in NAMED_SCHEDULE_ROW_CHOICES:
            raise ValueError(f"source_named_schedule_rows cites "
                             f"{v['owner_decision']['question_id']} choice "
                             f"{choice!r}, not one asking for rows by post name")


def patch_observations(rows: list[tuple[int, str | None]], all_observations: bool) -> tuple[list[int], str | None]:
    """The observations a reading is recorded on, or a refusal.

    rows: (source_observation_id, blob sha256) behind EVERY active instrument of the document, an exact duplicate
    included (doc 4419 obs 132, 12 Oct: a reading recorded only on the canonical observation let the replay rebuild
    the duplicate without it, so it stopped being a duplicate and entered the release). Several observations of
    one blob carry the same pages, so the reading is recorded on each; observations of different blobs still need
    `all_observations` (doc 4501)."""
    observations = sorted({obs for obs, _sha in rows})
    if not observations:
        return [], "0 active observations"
    blobs = {sha for _obs, sha in rows}
    if len(observations) > 1 and not all_observations and (len(blobs) != 1 or None in blobs):
        return [], (f"{len(observations)} active observations of different blobs"
                    " (set all_observations to patch each)")
    return observations, None


def observations_still_missing(observations: list[int], carrying: set[int]) -> tuple[list[int], list[int], str | None]:
    """(observations to record on, observations skipped because they already carry the identical patch, refusal).
    Refused only when every observation already carries it."""
    if carrying >= set(observations):
        return [], sorted(carrying), f"an identical patch is already recorded on every observation {sorted(carrying)}"
    return [obs for obs in observations if obs not in carrying], sorted(carrying & set(observations)), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readings", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--created-by", default=CREATED_BY,
                    help="reviewer identifier stored with newly accepted readings")
    a = ap.parse_args()
    readings = json.loads(pathlib.Path(a.readings).read_text(encoding="utf-8"))
    if isinstance(readings, dict):
        readings = [readings]

    planned, refused = [], []
    repeated = repeated_locators(readings)
    with connect() as conn, conn.cursor() as cur:
        for index, r in enumerate(readings):
            doc = r.get("document_id")
            where = f"doc {doc} p{r.get('page_no')} {r.get('before_text')!r}"
            if index in repeated:
                refused.append((where, "another reading in this file has the same page, match_text and "
                                       "before_text: one patch per locator (merge their structural keys)"))
                continue
            observed = (r.get("observed") or "").strip()
            if len(observed) < 40:
                refused.append((where, "no observation: say what the page shows"))
                continue
            problem = reading_key_problem(r)
            if problem:
                refused.append((where, problem))
                continue
            unlabelled_schedules = r.get("source_unlabelled_schedule_openers")
            quoted_rows = r.get("source_quoted_table_row_blocks")
            printed_headings = r.get("source_printed_headings")
            order_suffixes = r.get("source_order_suffix_labels")
            named_rows = r.get("source_named_schedule_rows")
            row_links = r.get("source_contents_row_links")
            group_captions = r.get("source_schedule_group_captions")
            owner_cited = r.get("source_owner_cited_labels")
            substituted = r.get("source_substituted_schedule_items")
            not_running = r.get("source_not_running_header_blocks")
            db_markers = r.get("source_contents_marker_blocks")   # rule contents_marker_block (agent DB)
            db_section_only = r.get("source_heading_scan_section_only")   # rule heading_scan_section_only (agent DB)
            df_keys = {k: r.get(k) for k in DF_BLOCK_KEYS if r.get(k) is not None}   # agent DF rules
            level_cells = r.get("source_level_cell_blocks")
            half_paren = r.get("source_half_paren_clause_blocks")
            if half_paren is not None and not quoted_table_row_blocks_shape_ok(half_paren):
                refused.append((where, "source_half_paren_clause_blocks must be a non-empty list of "
                                       "unique block ids"))
                continue
            if substituted is not None and not (
                    isinstance(substituted, list) and len(substituted) == 1
                    and substituted_schedule_items_shape_ok(substituted[0])):
                refused.append((where, "source_substituted_schedule_items must be one span {owner_block_id, "
                                       "schedule_block_id, source_text, resume_block_id, owner_decision}"))
                continue
            if not_running is not None and not block_id_list_ok(not_running):
                refused.append((where, "source_not_running_header_blocks must be a non-empty list of "
                                       "unique block ids"))
                continue
            if level_cells is not None and not (
                    isinstance(level_cells, list) and level_cells
                    and all(level_cell_block_shape_ok(v) for v in level_cells)
                    and len({v["cell_block_id"] for v in level_cells}) == len(level_cells)):
                refused.append((where, "source_level_cell_blocks must name distinct cells, each with "
                                       "the row it is printed level with"))
                continue
            if owner_cited is not None and not (
                    isinstance(owner_cited, list) and owner_cited
                    and all(owner_cited_label_shape_ok(v) for v in owner_cited)
                    # one entry per print -- the same key the worker merges on (agent JE: rule10's
                    # source_occurrence, rule13's source_prefix; doc 4498 holds several unnumbered openers per block)
                    and len({(v["source_block_id"], v["printed_label"], v["kind"], v.get("source_occurrence", 1),
                              v.get("source_prefix")) for v in owner_cited})
                    == len(owner_cited)):
                refused.append((where, "source_owner_cited_labels must name distinct prints "
                                       "{kind, printed_label|null + source_prefix, cited_label, "
                                       "source_block_id, owner_decision}"))
                continue
            if group_captions is not None and not (
                    isinstance(group_captions, list) and group_captions
                    and all(schedule_group_caption_shape_ok(v) for v in group_captions)
                    # one entry per (block, caption) -- the worker's merge key since agent K4's rule R
                    and len({(v["source_block_id"], " ".join((v.get("caption") or "").split()))
                             for v in group_captions}) == len(group_captions)):
                refused.append((where, "source_schedule_group_captions must name distinct blocks, "
                                       "the printed caption, level 1|2 and owner_decision"))
                continue
            if row_links is not None and not contents_row_links_ok(row_links):
                refused.append((where, "source_contents_row_links must name distinct contents rows "
                                       "{ordinal, printed_label, unit_label|null, owner_decision}, "
                                       "no unit twice"))
                continue
            if named_rows is not None and not (
                    isinstance(named_rows, list) and named_rows
                    and all(named_schedule_row_shape_ok(v) for v in named_rows)
                    and len({v["source_block_id"] for v in named_rows}) == len(named_rows)
                    and len({" ".join(v["label"].split()) for v in named_rows}) == len(named_rows)):
                refused.append((where, "source_named_schedule_rows must name distinct row blocks "
                                       "and labels, their schedule, source_text and owner_decision"))
                continue
            if order_suffixes is not None and not order_suffix_groups_ok(order_suffixes):
                refused.append((where, "source_order_suffix_labels must name groups of two or more "
                                       "distinct prints (no block in two groups) and owner_decision"))
                continue
            if unlabelled_schedules is not None and not (
                    isinstance(unlabelled_schedules, list) and unlabelled_schedules
                    and all(unlabelled_schedule_opener_shape_ok(v) for v in unlabelled_schedules)
                    and len({v["source_block_id"] for v in unlabelled_schedules})
                    == len(unlabelled_schedules)):
                refused.append((where, "source_unlabelled_schedule_openers must name distinct "
                                       "blocks, label, source_text and owner_decision"))
                continue
            if quoted_rows is not None and not quoted_table_row_blocks_shape_ok(quoted_rows):
                refused.append((where, "source_quoted_table_row_blocks must be a "
                                       "non-empty list of unique block ids"))
                continue
            if printed_headings is not None and not (
                    isinstance(printed_headings, list) and printed_headings
                    and all(printed_heading_shape_ok(v) for v in printed_headings)
                    and len({v["label"] for v in printed_headings}) == len(printed_headings)):
                refused.append((where, "source_printed_headings must name distinct labels, "
                                       "a source block, the printed words, use "
                                       "heading|marginal_note and owner_decision"))
                continue
            # Both rules carry out an owner's decision; the export must hold it.
            try:
                for v in ((unlabelled_schedules or []) + (printed_headings or [])
                          + (order_suffixes or []) + (row_links or [])):
                    owner_decision_answer(v["owner_decision"], doc)
                named_row_decision_check(named_rows or [], doc)
                group_caption_decision_check(group_captions or [], doc)
                owner_cited_decision_check(owner_cited or [], doc)
                substituted_schedule_decision_check(substituted or [], doc)
                order_suffix_decision_check(order_suffixes or [], doc)
                unlabelled_opener_decision_check(unlabelled_schedules or [], doc)
            except ValueError as error:
                refused.append((where, str(error)))
                continue
            match, before, after = (r.get("match_text") or "", r.get("before_text") or "",
                                    r.get("after_text") or "")
            body_start = r.get("source_body_start_block")
            apparatus = r.get("source_apparatus_blocks")
            reparents = r.get("source_reparent_blocks")
            continuations = r.get("source_continuation_parent_blocks")
            unnumbered_openers = r.get("source_unnumbered_section_openers")
            unnumbered_parts = r.get("source_unnumbered_part_headings")
            schedule_rows = r.get("source_schedule_row_openers")
            form_group = r.get("source_schedule_form_group")
            if reparents is not None and not (
                    isinstance(reparents, list) and reparents
                    and all(isinstance(v, dict)
                            and type(v.get("source_block_id")) is int
                            and type(v.get("parent_block_id")) is int
                            and (v.get("kind") in (
                                "clause", "subsection", "explanation", "proviso")
                                 # rule `reviewed_schedule_chapter_reparent` (stage 3, agent DG, doc 4236)
                                 or (v.get("kind") == "chapter" and v.get("source_kind") == "chapter"
                                     and v.get("parent_kind") == "schedule")
                                 # rule `reviewed_clause_section_reparent` (agent JE, doc 4441)
                                 or (v.get("kind") == "section" and v.get("source_kind") == "clause"
                                     and isinstance(v.get("source_label"), str)
                                     and v.get("parent_kind") in ("chapter", "part"))
                                 # rule `reviewed_annexure_appendix_reparent` (agent JE, doc 4400)
                                 or (v.get("kind") == "annexure" and v.get("source_kind") == "annexure"
                                     and v.get("parent_kind") == "appendix"))
                            and (v["source_block_id"] != v["parent_block_id"]
                                 or (v.get("source_label") is not None
                                     and v.get("parent_label") is not None))
                            for v in reparents)):
                refused.append((where, "source_reparent_blocks must be a list of "
                                       "{source_block_id, parent_block_id, kind "
                                       "clause|subsection|explanation|proviso, or chapter with "
                                       "source_kind chapter and parent_kind schedule, or section with "
                                       "source_kind clause, source_label and parent_kind chapter|part} objects"))
                continue
            if continuations is not None and not (
                    isinstance(continuations, list) and continuations
                    and all(isinstance(v, dict)
                            and set(v) == {"source_block_id", "parent_block_id"}
                            and type(v["source_block_id"]) is int
                            and type(v["parent_block_id"]) is int
                            and v["source_block_id"] != v["parent_block_id"]
                            for v in continuations)
                    and len({v["source_block_id"] for v in continuations})
                    == len(continuations)):
                refused.append((where, "source_continuation_parent_blocks must "
                                       "name distinct source and parent block ids"))
                continue
            if unnumbered_openers is not None and not (
                    isinstance(unnumbered_openers, list) and unnumbered_openers
                    and all(unnumbered_opener_shape_ok(v) for v in unnumbered_openers)
                    and len({v["source_block_id"] for v in unnumbered_openers})
                    == len(unnumbered_openers)):
                refused.append((where, "source_unnumbered_section_openers must "
                                       "name distinct blocks and source-backed labels/headings"))
                continue
            # An opener that numbers an unnumbered paragraph cites the owner's
            # decision; the export must hold that answer (profile rule
            # `unnumbered_root_provision`).
            try:
                for v in unnumbered_openers or []:
                    if "owner_decision" in v:
                        owner_decision_answer(v["owner_decision"], doc)
            except ValueError as error:
                refused.append((where, str(error)))
                continue
            if unnumbered_parts is not None and not (
                    isinstance(unnumbered_parts, list) and unnumbered_parts
                    and all(isinstance(v, dict)
                            and set(v) == {"source_block_id", "heading"}
                            and type(v["source_block_id"]) is int
                            and isinstance(v["heading"], str) and v["heading"].strip()
                            for v in unnumbered_parts)
                    and len({v["source_block_id"] for v in unnumbered_parts})
                    == len(unnumbered_parts)):
                refused.append((where, "source_unnumbered_part_headings must "
                                       "name distinct source blocks and printed headings"))
                continue
            if schedule_rows is not None and not (
                    isinstance(schedule_rows, list) and schedule_rows
                    and all(isinstance(v, dict)
                            and set(v) == {"source_block_id", "schedule_block_id",
                                           "label", "source_text"}
                            and type(v["source_block_id"]) is int
                            and type(v["schedule_block_id"]) is int
                            and v["source_block_id"] > 0
                            and v["schedule_block_id"] > 0
                            and v["source_block_id"] != v["schedule_block_id"]
                            and isinstance(v["label"], str) and v["label"].strip()
                            and isinstance(v["source_text"], str)
                            and v["source_text"].strip()
                            for v in schedule_rows)
                    and len({v["source_block_id"] for v in schedule_rows})
                    == len(schedule_rows)):
                refused.append((where, "source_schedule_row_openers must name "
                                       "distinct grid blocks, their schedule and printed labels"))
                continue
            if apparatus is not None and not (
                    isinstance(apparatus, list) and apparatus
                    and all(type(v) is int and v > 0 for v in apparatus)
                    and len(set(apparatus)) == len(apparatus)):
                refused.append((where, "source_apparatus_blocks must be a "
                                       "non-empty list of unique block ids"))
                continue
            if form_group is not None and not (
                    isinstance(form_group, dict)
                    and set(form_group) == {
                        "schedule_block_id", "schedule_label",
                        "first_form_block_id", "first_form_label",
                        "second_form_block_id", "second_form_label"}
                    and all(type(form_group[key]) is int and form_group[key] > 0
                            for key in ("schedule_block_id",
                                        "first_form_block_id",
                                        "second_form_block_id"))
                    and len({form_group["schedule_block_id"],
                             form_group["first_form_block_id"],
                             form_group["second_form_block_id"]}) == 3
                    and all(isinstance(form_group[key], str)
                            and form_group[key].strip()
                            for key in ("schedule_label", "first_form_label",
                                        "second_form_label"))):
                refused.append((where, "source_schedule_form_group must name "
                                       "three distinct source blocks and labels"))
                continue
            # An identity patch (before == after) changes no text; it exists only
            # to carry a reviewed body boundary, as Codex's doc 157 record does,
            # or page-read apparatus blocks where no S7 collision exists to
            # carry them (owner's authorisation, 26 Sep 2026).
            identity = before == after
            if len(match) < 12 or not before or not after or (
                    identity and not isinstance(body_start, int)
                    and apparatus is None and reparents is None
                    and continuations is None
                    and unnumbered_openers is None
                    and unnumbered_parts is None
                    and schedule_rows is None
                    and form_group is None
                    and unlabelled_schedules is None
                    and quoted_rows is None
                    and printed_headings is None
                    and order_suffixes is None
                    and named_rows is None
                    and row_links is None
                    and group_captions is None
                    and owner_cited is None
                    and substituted is None
                    and not_running is None
                    and level_cells is None
                    and half_paren is None and db_markers is None and db_section_only is None
                    and r.get("source_schedule_heading_blocks") is None
                    and r.get("source_repeal_stub_cut_blocks") is None and not df_keys
                    and r.get("source_decoded_underscore_dash") is None
                    and r.get("source_long_suffix_section_openers") is None
                    # export j ports (14 Oct 2026): a structure-only reading carrying a generic key or margin-heading
                    # owners is an identity patch like the others (agent JB's prototype admitted F/H/I the same way)
                    and not any(r.get(k) is not None for k in GENERIC_STRUCTURAL_KEYS)
                    and r.get("source_margin_heading_owners") is None):
                refused.append((where, "match_text >= 12 chars and a real "
                                       "before/after change (or an identity "
                                       "patch carrying source_body_start_block "
                                       "or source_apparatus_blocks) are required"))
                continue
            render = pathlib.Path(r.get("render") or "")
            if not render.is_file():
                refused.append((where, f"render not on disk: {render}"))
                continue
            digest = hashlib.sha256(render.read_bytes()).hexdigest()
            if r.get("render_sha256") and r["render_sha256"] != digest:
                refused.append((where, "render_sha256 does not match the file"))
                continue
            additional_render = r.get("additional_render")
            additional_digest = None
            if additional_render:
                # one render with its sha256, or a list of renders with a list of shas in the same order
                many = isinstance(additional_render, list)
                paths = list(additional_render) if many else [additional_render]
                shas = r.get("additional_render_sha256")
                shas = (list(shas) if isinstance(shas, list) else [None] * len(paths)) if many else [shas]
                if len(shas) != len(paths) or not all(isinstance(x, str) and x for x in paths):
                    refused.append((where, "additional_render and additional_render_sha256 must pair one sha256 "
                                           "per render"))
                    continue
                digests, bad = [], None
                for one, want in zip(paths, shas):
                    one_path = pathlib.Path(one)
                    if not one_path.is_file():
                        bad = f"additional render not on disk: {one_path}"
                        break
                    got = hashlib.sha256(one_path.read_bytes()).hexdigest()
                    if want != got:
                        bad = "additional_render_sha256 does not match the file"
                        break
                    digests.append(got)
                if bad:
                    refused.append((where, bad))
                    continue
                additional_digest = digests if many else digests[0]
            cur.execute("""SELECT DISTINCT i.source_observation_id, o.sha256 FROM instrument i
                             JOIN source_observation o ON o.id=i.source_observation_id
                            WHERE i.document_id=%s AND i.is_active""",
                        (doc,))
            # Every observation behind an active instrument, exact duplicates included; one blob -> each of them
            # (patch_observations).
            observations, why = patch_observations([tuple(row) for row in cur.fetchall()],
                                                   bool(r.get("all_observations")))
            if why:
                refused.append((where, why))
                continue
            page = int(r["page_no"])
            blocks = [b for b in legal_write.blocks_for(doc)
                      if b.get("page_no") == page
                      and match.casefold() in b["text"].casefold()]
            if "exact_block_locator" in r:
                if r["exact_block_locator"] is not True or type(r.get("source_block_id")) is not int or match != before:
                    refused.append((where, "exact-block locator requires true, a block id and full before-text locator"))
                    continue
                blocks = [b for b in blocks if b["id"] == r["source_block_id"] and b["text"] == before]
            if len(blocks) != 1:
                refused.append((where, f"locator matched {len(blocks)} blocks"))
                continue
            block = blocks[0]
            if block["text"].count(before) != 1:
                refused.append((where, "before_text is not exactly once in the block"))
                continue
            # Per observation: one that already carries this patch is skipped, the rest are recorded; refused
            # only when every observation carries it.
            cur.execute("""SELECT DISTINCT source_observation_id FROM segmentation_curation_patch
                            WHERE source_observation_id=ANY(%s) AND page_no=%s
                              AND match_text=%s AND before_text=%s""",
                        (observations, page, match, before))
            observations, skipped, why = observations_still_missing(
                observations, {row[0] for row in cur.fetchall()})
            if why:
                refused.append((where, why))
                continue
            evidence = {
                "defect": r.get("defect") or "printed number misread in the source text layer",
                "observed": observed, "document_id": doc,
                "render_artifact": str(render).replace("\\", "/"),
                "render_sha256": digest, "source_block_id": block["id"],
                "extracted_number": r.get("extracted_number"),
                "printed_number": r.get("printed_number"),
                "reviewer_type": "assistant", "assistant_page_review": True,
                "human_page_review": False,
                "tool": "tools/record_curation_patch.py",
            }
            if r.get("exact_block_locator") is True:
                evidence["exact_block_locator"] = True
            if additional_render:
                evidence["additional_render_artifact"] = (
                    [str(x).replace("\\", "/") for x in additional_render] if isinstance(additional_render, list)
                    else str(additional_render).replace("\\", "/"))
                evidence["additional_render_sha256"] = additional_digest
            if r.get("fixes"):
                evidence["fixes"] = r["fixes"]
            if isinstance(body_start, int):
                if body_start not in {b["id"] for b in legal_write.blocks_for(doc)}:
                    refused.append((where, "source_body_start_block is not a "
                                           "block of this document"))
                    continue
                evidence["structural_overrides"] = {"source_body_start_block": body_start}
                evidence["identity_text_patch"] = identity
            if apparatus is not None:
                # Every named block must be printed on the page the patch
                # anchors to and read there: one page, one reading.
                # agJB rule G: apparatus blocks may stand on the reading's cited pages (its page and its
                # verified additional render's page), as order-suffix groups already may.
                _jb_pages = reading_cited_pages(r, doc, page)
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") in _jb_pages}
                stray = sorted(set(apparatus) - on_page)
                if stray:
                    refused.append((where, "source_apparatus_blocks not on page "
                                           f"{page}: {stray}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_apparatus_blocks"] = apparatus
                evidence["identity_text_patch"] = identity
            for dc_key in ("source_schedule_heading_blocks", "source_repeal_stub_cut_blocks"):
                dc_heads = r.get(dc_key)   # rules reviewed_schedule_heading / reviewed_repeal_stub_cut (agent DC)
                if dc_heads is None:
                    continue
                on_page = {b["id"] for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                if not block_id_list_ok(dc_heads) or set(dc_heads) - on_page:
                    refused.append((where, f"{dc_key} must be block ids on the reading's page"))
                    dc_bad = True
                    break
                evidence.setdefault("structural_overrides", {})[dc_key] = dc_heads
                evidence["identity_text_patch"] = identity
            else:
                dc_bad = False
            if dc_bad:
                continue
            if db_markers is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                if not block_id_list_ok(db_markers) or set(db_markers) - on_page:
                    refused.append((where, "source_contents_marker_blocks must be block ids on the reading's page"))
                    continue
                evidence.setdefault("structural_overrides", {})["source_contents_marker_blocks"] = db_markers
                evidence["identity_text_patch"] = identity
            ls_open = r.get("source_long_suffix_section_openers")
            if ls_open is not None:
                doc_blocks = {b["id"] for b in legal_write.blocks_for(doc)}
                if not long_suffix_openers_ok(ls_open) or {v["block_id"] for v in ls_open} - doc_blocks:
                    refused.append((where, "source_long_suffix_section_openers must name blocks of this document "
                                           "and labels of digits and 4-8 capitals"))
                    continue
                evidence.setdefault("structural_overrides", {})["source_long_suffix_section_openers"] = ls_open
                evidence["identity_text_patch"] = identity
            agde_decl = r.get("source_decoded_underscore_dash")
            if agde_decl is not None:
                if not decoded_underscore_dash_ok(agde_decl):
                    refused.append((where, "source_decoded_underscore_dash must declare the glyph "
                                           "(decoded|typed) with its ink counts and 1-3 measured runs"))
                    continue
                evidence.setdefault("structural_overrides", {})["source_decoded_underscore_dash"] = agde_decl
                evidence["identity_text_patch"] = identity
            if db_section_only is not None:
                if db_section_only is not True:
                    refused.append((where, "source_heading_scan_section_only must be true"))
                    continue
                evidence.setdefault("structural_overrides", {})["source_heading_scan_section_only"] = True
                evidence["identity_text_patch"] = identity
            if df_keys:
                on_page = {b["id"] for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                bad = sorted(k for k, v in df_keys.items() if not block_id_list_ok(v) or set(v) - on_page)
                if bad:
                    refused.append((where, f"{bad} must be distinct block ids on the reading's page"))
                    continue
                for k, v in df_keys.items():
                    evidence.setdefault("structural_overrides", {})[k] = v
                evidence["identity_text_patch"] = identity
            if reparents is not None:
                # An exact source-block reparent where no S7 case exists; the
                # worker already honours it from a verified patch, and the
                # segmenter fails closed if an address is absent or ambiguous.
                document_blocks = {b["id"] for b in legal_write.blocks_for(doc)}
                stray = sorted({v[k] for v in reparents
                                for k in ("source_block_id", "parent_block_id")}
                               - document_blocks)
                if stray:
                    refused.append((where, f"source_reparent_blocks outside this "
                                           f"document: {stray}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_reparent_blocks"] = reparents
                evidence["identity_text_patch"] = identity
            if continuations is not None:
                document_blocks = {b["id"] for b in legal_write.blocks_for(doc)}
                page_blocks = {b["id"] for b in legal_write.blocks_for(doc)
                               if b.get("page_no") == page}
                sources = {v["source_block_id"] for v in continuations}
                parents = {v["parent_block_id"] for v in continuations}
                if sources - page_blocks or parents - document_blocks:
                    refused.append((where, "source continuation or parent "
                                           "block is outside the reviewed page/document"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_continuation_parent_blocks"] = continuations
                evidence["identity_text_patch"] = identity
            if unnumbered_openers is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                if {v["source_block_id"] for v in unnumbered_openers} - on_page:
                    refused.append((where, "unnumbered section opener is outside "
                                           "the reviewed page"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_unnumbered_section_openers"] = unnumbered_openers
                evidence["identity_text_patch"] = identity
            if unnumbered_parts is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                if {v["source_block_id"] for v in unnumbered_parts} - on_page:
                    refused.append((where, "unnumbered part heading is outside "
                                           "the reviewed page"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_unnumbered_part_headings"] = unnumbered_parts
                evidence["identity_text_patch"] = identity
            if schedule_rows is not None:
                on_page = {b["id"]: b for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                if (any(v["source_block_id"] not in on_page
                        or v["schedule_block_id"] not in on_page
                        or " ".join(on_page[v["source_block_id"]]["text"].split())
                           != " ".join(v["source_text"].split())
                        for v in schedule_rows)):
                    refused.append((where, "source schedule row or schedule "
                                           "is outside the reviewed page or text changed"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_schedule_row_openers"] = schedule_rows
                evidence["identity_text_patch"] = identity
            if form_group is not None:
                on_page = {b["id"] for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                named = {form_group[key] for key in (
                    "schedule_block_id", "first_form_block_id",
                    "second_form_block_id")}
                if named - on_page:
                    refused.append((where, "source_schedule_form_group has "
                                           f"blocks outside page {page}: "
                                           f"{sorted(named - on_page)}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_schedule_form_group"] = form_group
                evidence["identity_text_patch"] = identity
            if (unlabelled_schedules is not None or printed_headings is not None
                    or quoted_rows is not None or order_suffixes is not None):
                # One page, one reading: every named block is printed on the
                # page the patch anchors to, and its words are there.
                on_page = {b["id"]: b for b in legal_write.blocks_for(doc)
                           if b.get("page_no") == page}
                named = ({v["source_block_id"] for v in (unlabelled_schedules or [])
                          + (printed_headings or [])} | set(quoted_rows or []))
                stray = sorted(named - set(on_page))
                if stray:
                    refused.append((where, f"blocks outside page {page}: {stray}"))
                    continue
                # An order-suffix group names every print of one label, and the
                # prints may stand on two pages (doc 1457 s.20: (i), (ii) on p11,
                # again on p12). Its blocks must be on the pages the reading
                # cites: its own page and its verified additional render's page.
                cited_pages = reading_cited_pages(r, doc, page)
                suffix_blocks = {block_id for v in order_suffixes or [] for block_id in v["source_block_ids"]}
                cited_blocks = {b["id"] for b in legal_write.blocks_for(doc) if b.get("page_no") in cited_pages}
                stray = sorted(suffix_blocks - cited_blocks)
                if stray:
                    refused.append((where, f"source_order_suffix_labels blocks outside the cited pages "
                                           f"{sorted(cited_pages)}: {stray}"))
                    continue
                # The words are checked as the parser will read them: the
                # anchor block with this reading's own replacement applied
                # (doc 691's column heads are that reading's after_text).
                texts = {block_id: b["text"] for block_id, b in on_page.items()}
                texts[block["id"]] = block["text"].replace(before, after, 1)
                if any(_norm(texts[v["source_block_id"]]) != _norm(v["source_text"])
                       for v in unlabelled_schedules or []):
                    refused.append((where, "source_unlabelled_schedule_openers source_text "
                                           "is not the block's text"))
                    continue
                if any(_norm(v["heading"]) not in _norm(texts[v["source_block_id"]])
                       for v in printed_headings or []):
                    refused.append((where, "source_printed_headings words are not printed "
                                           "in the named block"))
                    continue
                for key, value in (("source_unlabelled_schedule_openers", unlabelled_schedules),
                                   ("source_quoted_table_row_blocks", quoted_rows),
                                   ("source_printed_headings", printed_headings),
                                   ("source_order_suffix_labels", order_suffixes)):
                    if value is not None:
                        evidence.setdefault("structural_overrides", {})[key] = value
                evidence["identity_text_patch"] = identity
            if named_rows is not None:
                # One page, one reading: each row block is printed on the page
                # the patch anchors to; its schedule's first block may be on an
                # earlier page (doc 1078's p4 rows under the p3 caption) but is
                # a block of this document.
                document_blocks = {b["id"]: b for b in legal_write.blocks_for(doc)}
                on_page = {block_id: b for block_id, b in document_blocks.items()
                           if b.get("page_no") == page}
                stray = sorted({v["source_block_id"] for v in named_rows} - set(on_page))
                if stray or any(v["schedule_block_id"] not in document_blocks for v in named_rows):
                    refused.append((where, f"source_named_schedule_rows blocks outside page {page} "
                                           f"{stray} or schedule outside the document"))
                    continue
                # The row text is checked as the parser will read it: the
                # anchor block with this reading's replacement applied (the
                # row line is usually the reading's own after_text), and the
                # printed post name must be in it exactly once. The label drops
                # the cell's closing stop ('Superintendent' for 'Superintendent .',
                # doc 1106; lead decision 8 Oct), as printed numbers drop theirs;
                # one trailing stop on the label itself is ignored too.
                texts = {block_id: b["text"] for block_id, b in on_page.items()}
                texts[block["id"]] = block["text"].replace(before, after, 1)
                if any(_norm(texts[v["source_block_id"]]) != _norm(v["source_text"])
                       or _norm(v["source_text"]).count(_label_without_stop(v["label"])) != 1
                       for v in named_rows):
                    refused.append((where, "source_named_schedule_rows source_text is not the "
                                           "block's text or does not print the label once"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_named_schedule_rows"] = named_rows
                evidence["identity_text_patch"] = identity
            if half_paren is not None:
                # One page, one reading: each named block is printed on the reading's page.
                on_page_ids = {b["id"] for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                stray = sorted(set(half_paren) - on_page_ids)
                if stray:
                    refused.append((where, f"source_half_paren_clause_blocks not on page {page}: {stray}"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_half_paren_clause_blocks"] = half_paren
                evidence["identity_text_patch"] = identity
            if substituted is not None or not_running is not None or level_cells is not None:
                document_blocks = legal_write.blocks_for(doc)
                position = {b["id"]: index for index, b in enumerate(document_blocks)}
                on_page = {b["id"]: b for b in document_blocks if b.get("page_no") == page}
                problem = doc1431_block_problem(substituted, not_running, level_cells, position, on_page,
                                                block["id"], block["text"].replace(before, after, 1))
                if problem:
                    refused.append((where, problem))
                    continue
                for key, value in (("source_substituted_schedule_items", substituted),
                                   ("source_not_running_header_blocks", not_running),
                                   ("source_level_cell_blocks", level_cells)):
                    if value is not None:
                        evidence.setdefault("structural_overrides", {})[key] = value
                evidence["identity_text_patch"] = identity
            if owner_cited is not None:
                try:
                    for observation in observations:
                        legal_write.validate_owner_cited_source_gaps(
                            doc, observation, {"source_owner_cited_labels": owner_cited})
                except ValueError as exc:
                    refused.append((where, str(exc)))
                    continue
                # One page, one reading: each block is printed on the reading's
                # page, after the reading is applied; an opener's printed words
                # occur there once, a relabelled section's printed number is
                # printed there ('3.'). The segmenter checks the rest.
                on_page = {b["id"]: b for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                texts = {block_id: b["text"] for block_id, b in on_page.items()}
                texts[block["id"]] = block["text"].replace(before, after, 1)
                problems = [owner_cited_block_problem(v, texts) for v in owner_cited]
                if any(problems):
                    refused.append((where, "source_owner_cited_labels: "
                                           + "; ".join(x for x in problems if x)))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_owner_cited_labels"] = owner_cited
                evidence["identity_text_patch"] = identity
            if group_captions is not None:
                # One page, one reading: each caption block is printed on the
                # reading's page and prints the caption (after the reading is
                # applied); the segmenter checks the unit's text exactly.
                on_page = {b["id"]: b for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                texts = {block_id: b["text"] for block_id, b in on_page.items()}
                texts[block["id"]] = block["text"].replace(before, after, 1)
                if any(v["source_block_id"] not in texts
                       or _norm(v["caption"]) not in _norm(texts[v["source_block_id"]])
                       for v in group_captions):
                    refused.append((where, f"source_schedule_group_captions block outside page {page} "
                                           "or caption not printed in it"))
                    continue
                evidence.setdefault("structural_overrides", {})[
                    "source_schedule_group_captions"] = group_captions
                evidence["identity_text_patch"] = identity
            if row_links is not None:
                # The contents rows are checked by the segmenter at replay
                # (printed label at that ordinal; each linked row ends on its
                # unit); the reading anchors to the contents page it was read on.
                evidence.setdefault("structural_overrides", {})[
                    "source_contents_row_links"] = row_links
                evidence["identity_text_patch"] = identity
            jb_mho = r.get("source_margin_heading_owners")   # agJB rule H
            if jb_mho is not None:
                _jb_on = {b["id"] for b in legal_write.blocks_for(doc) if b.get("page_no") == page}
                _jb_all = {b["id"] for b in legal_write.blocks_for(doc)}
                if not (isinstance(jb_mho, list) and jb_mho and all(_bz_margin_heading_owner_ok(v) for v in jb_mho)
                        and all(v["heading_block_id"] in _jb_on and v["owner_block_id"] in _jb_all for v in jb_mho)):
                    refused.append((where, "source_margin_heading_owners must name heading blocks on this page and "
                                           "owner blocks of the document"))
                    continue
                evidence.setdefault("structural_overrides", {})["source_margin_heading_owners"] = jb_mho
                evidence["identity_text_patch"] = identity
            jd_sph = r.get("source_schedule_paragraph_headings")   # agent JD rule J: an owner-cited heading
            if jd_sph is not None:
                try:
                    if not (isinstance(jd_sph, list) and jd_sph
                            and all(_bz_schedule_paragraph_heading_ok(v) for v in jd_sph)):
                        raise ValueError("source_schedule_paragraph_headings entries must be {label, source_block_id, heading, owner_decision}")
                    for v in jd_sph:
                        owner_decision_answer(v["owner_decision"], doc)
                except ValueError as error:
                    refused.append((where, str(error)))
                    continue
            jd_osp = r.get("source_owner_schedule_parts")   # agent JD rule O: an owner-supplied schedule Part
            if jd_osp is not None:
                try:
                    if not (isinstance(jd_osp, list) and jd_osp and all(_bz_owner_schedule_part_ok(v) for v in jd_osp)):
                        raise ValueError("source_owner_schedule_parts entries must be {first_block_id, label, evidence_block_id, "
                                         "owner_decision}")
                    for v in jd_osp:
                        owner_decision_answer(v["owner_decision"], doc)
                except ValueError as error:
                    refused.append((where, str(error)))
                    continue
            # agent K6 (group 33, doc 4640): reviewed_block_order and section_group_caption entries -- shape, and a
            # section caption must cite an answer asking for the section's own caption divisions
            k6_bo, k6_sgc = r.get("source_block_order_moves"), r.get("source_section_group_captions")
            try:
                if k6_bo is not None and not (isinstance(k6_bo, list) and k6_bo
                                              and all(_bz_block_order_move_ok(v) for v in k6_bo)
                                              and len({v["first_block_id"] for v in k6_bo}) == len(k6_bo)):
                    raise ValueError("source_block_order_moves entries must be distinct {first_block_id, last_block_id, after_block_id}")
                if k6_sgc is not None:
                    if not (isinstance(k6_sgc, list) and k6_sgc and all(_bz_section_group_caption_ok(v) for v in k6_sgc)
                            and len({v["source_block_id"] for v in k6_sgc}) == len(k6_sgc)):
                        raise ValueError("source_section_group_captions entries must be {source_block_id, caption, label, heading, "
                                         "level 1|2, owner_decision} on distinct blocks")
                    for v in k6_sgc:
                        choice = owner_decision_answer(v["owner_decision"], doc).get("choice")
                        if choice not in SECTION_GROUP_CAPTION_CHOICES:
                            raise ValueError(f"source_section_group_captions cites {v['owner_decision']['question_id']} choice "
                                             f"{choice!r}, not one asking for the section's caption divisions")
            except ValueError as error:
                refused.append((where, str(error)))
                continue
            bz_owned = [v for k in ("source_paired_repeal_stubs", "source_quoted_appendix_labels",   # group 10
                                    "source_heading_lines")
                        for v in (r.get(k) or []) if isinstance(v, dict) and v.get("owner_decision") is not None]
            try:
                for v in bz_owned:
                    owner_decision_answer(v["owner_decision"], doc)
            except ValueError as error:
                refused.append((where, str(error)))
                continue
            generic = {k: r.get(k) for k in sorted(GENERIC_STRUCTURAL_KEYS) if r.get(k) is not None}
            if generic:
                if "source_reviewed_grid_rows" in generic:
                    from nizam.corpus.segment import reviewed_grid_row_shape_ok
                    grid = generic["source_reviewed_grid_rows"]
                    db = {b['id']: b for b in legal_write.blocks_for(doc)}
                    cited_pages = reading_cited_pages(r, doc, page)
                    if not (isinstance(grid, list) and grid and all(reviewed_grid_row_shape_ok(v) for v in grid)
                            and all(v['source_block_id'] in db and db[v['source_block_id']]['page_no'] == page
                                    and all(bid in db and db[bid]['page_no'] in cited_pages for col in v['cells'] for bid in col)
                                    for v in grid)):
                        refused.append((where, 'reviewed grid needs exact well-shaped rows and images for all cell pages'))
                        continue
                stray = sorted(named_block_ids(generic) - {b["id"] for b in legal_write.blocks_for(doc)})
                if stray:
                    refused.append((where, f"{sorted(generic)} name blocks outside the document: {stray}"))
                    continue
                for k, v in generic.items():
                    evidence.setdefault("structural_overrides", {})[k] = v
                evidence["identity_text_patch"] = identity
            # Fail closed (lead 13 Oct 2026): every structural key the reading names must have reached the recorded
            # evidence. A key with no recording branch was dropped silently (doc 4521's source_figure_subsections);
            # it is refused instead, and named.
            dropped = sorted(k for k in STRUCTURAL_KEYS if r.get(k) is not None
                             and k not in (evidence.get("structural_overrides") or {}))
            if dropped:
                refused.append((where, f"structural key(s) {dropped} would not be recorded; refused rather than "
                                       "dropped"))
                continue
            if r.get("owner_decision") is not None:
                evidence["owner_decision"] = r["owner_decision"]
            planned.append({"where": where, "obs": observations, "skipped": skipped, "page": page,
                            "match": match, "before": before, "after": after,
                            "evidence": evidence,
                            "preview": block["text"].replace(before, after, 1)[:140]})

        print(f"readings          : {len(readings)}")
        print(f"  will record     : {len(planned)}")
        print(f"  refused         : {len(refused)}")
        for where, why in refused:
            print(f"    {where}: {why}")
        for p in planned:
            print(f"    {p['where']} -> {p['after']!r}\n        block now reads: "
                  f"{' '.join(p['preview'].split())}")
            print(f"        observations {p['obs']}"
                  + (f"; already carried by {p['skipped']} (skipped)" if p["skipped"] else ""))
        if not a.apply:
            print("\ndry run -- pass --apply to record these patches")
            return 0 if not refused else 1
        written = 0
        for p in planned:
            for observation in p["obs"]:
                cur.execute("""
                    INSERT INTO segmentation_curation_patch
                        (source_observation_id, page_no, match_text, before_text,
                         after_text, evidence, review_state, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,'source_verified',%s)
                """, (observation, p["page"], p["match"], p["before"], p["after"],
                      json.dumps(p["evidence"], ensure_ascii=False), a.created_by))
                written += 1
        conn.commit()
        print(f"\nrecorded {written} source-verified patch(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
