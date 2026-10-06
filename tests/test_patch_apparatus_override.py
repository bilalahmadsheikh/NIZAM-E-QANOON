"""A verified curation patch may name page-read apparatus blocks.

Where the parser reads a footnote or an endnote as law but raises no S7
collision, there is no candidate for an S7 reading to carry
`source_apparatus_blocks` (doc 2803's closing amendment notes, absorbed into
rule 30(3)). An identity patch anchored to the page carries them instead
(owner's authorisation, 26 Sep 2026). Patches anchor to one page each, so
their lists are united; S7 readings keep their own rule of agreement.
"""
import pytest

from nizam.corpus import segment as corpus_segment
from nizam.workers.segment import reviewed_structural_overrides


def _patch(blocks):
    return {"evidence": {"structural_overrides": {"source_apparatus_blocks": blocks}}}


def _reading(blocks):
    return {"evidence": {"structural_overrides": {"source_apparatus_blocks": blocks}}}


def test_patch_apparatus_lists_are_united():
    merged = reviewed_structural_overrides([], [_patch([30, 10]), _patch([20])])
    assert merged == {"source_apparatus_blocks": [10, 20, 30]}


def test_patch_apparatus_joins_s7_apparatus():
    merged = reviewed_structural_overrides([_reading([5, 6])], [_patch([7])])
    assert merged == {"source_apparatus_blocks": [5, 6, 7]}


def test_s7_readings_must_still_agree():
    with pytest.raises(ValueError, match="conflicting"):
        reviewed_structural_overrides([_reading([5]), _reading([6])], [])


@pytest.mark.parametrize("bad", [[], ["12"], [0], "12", None])
def test_malformed_patch_apparatus_is_refused(bad):
    with pytest.raises(ValueError, match="unsupported"):
        reviewed_structural_overrides([], [_patch(bad)])


def test_no_patch_apparatus_changes_nothing():
    assert reviewed_structural_overrides([_reading([5])], []) == {
        "source_apparatus_blocks": [5]}


def test_exact_continuation_parent_is_source_block_scoped():
    blocks = [
        {"id": 1, "page_no": 1, "text": "8. Penalties. If the Manager of a Bank:",
         "y0": 200.0, "x0": 72.0, "x1": 500.0, "page_height": 800.0},
        {"id": 2, "page_no": 1, "text": "(a) fails to comply with an order; or",
         "y0": 240.0, "x0": 144.0, "x1": 500.0, "page_height": 800.0},
        {"id": 3, "page_no": 1, "text": "(b) refuses to allow an inspection;",
         "y0": 280.0, "x0": 144.0, "x1": 500.0, "page_height": 800.0},
        {"id": 4, "page_no": 1,
         "text": "he shall be punishable with imprisonment or with fine or with both.",
         "y0": 320.0, "x0": 72.0, "x1": 500.0, "page_height": 800.0},
        {"id": 5, "page_no": 1, "text": "9. Other provisions. This section follows.",
         "y0": 360.0, "x0": 72.0, "x1": 500.0, "page_height": 800.0},
    ]
    plain = corpus_segment.segment(blocks, profile="unreleased-v4")
    assert "punishable" in next(n for n in plain.flatten()
                                if n.kind == "clause" and n.label == "b").text
    corrected = corpus_segment.segment(
        blocks, profile="unreleased-v4",
        structural_overrides={"source_continuation_parent_blocks": [
            {"source_block_id": 4, "parent_block_id": 1}]})
    section = next(n for n in corrected.flatten()
                   if n.kind == "section" and n.label == "8")
    clause = next(n for n in corrected.flatten()
                  if n.kind == "clause" and n.label == "b")
    assert 4 in section.blocks and "punishable" in section.text
    assert 4 not in clause.blocks and "punishable" not in clause.text
    assert corrected.block_roles[4][1] is section


def test_exact_continuation_override_fails_closed_on_wrong_parent():
    blocks = [{"id": 1, "page_no": 1,
               "text": "8. Penalties. These are penalties.",
               "y0": 200.0, "x0": 72.0, "x1": 500.0, "page_height": 800.0},
              {"id": 2, "page_no": 1, "text": "Further unnumbered words.",
               "y0": 240.0, "x0": 72.0, "x1": 500.0, "page_height": 800.0}]
    with pytest.raises(ValueError, match="no open parent block"):
        corpus_segment.segment(blocks, profile="unreleased-v4",
                               structural_overrides={"source_continuation_parent_blocks": [
                                   {"source_block_id": 2, "parent_block_id": 999}]})


def test_patch_continuation_conflict_is_rejected():
    a = {"evidence": {"structural_overrides": {
        "source_continuation_parent_blocks": [
            {"source_block_id": 4, "parent_block_id": 1}]}}}
    b = {"evidence": {"structural_overrides": {
        "source_continuation_parent_blocks": [
            {"source_block_id": 4, "parent_block_id": 2}]}}}
    with pytest.raises(ValueError, match="conflicting"):
        reviewed_structural_overrides([], [a, b])


def test_2145_first_subsection_survives_source_reviewed_heading_split():
    # Official page 2 prints section 1(1)-(3); the extraction fuses (1) to
    # the heading with "___", so a page-anchored parser-input split is needed.
    blocks = [
        {"id": 162512, "page_no": 2, "y0": 380.0, "x0": 72.0,
         "x1": 550.0, "page_height": 800.0,
         "text": "1. Short title, extent and commencement.___(1) This Ordinance may be called the Pakistan Banking Ordinance, 1947."},
        {"id": 162513, "page_no": 2, "y0": 410.0, "x0": 72.0,
         "x1": 550.0, "page_height": 800.0,
         "text": "(2) It extends to the whole of Pakistan."},
        {"id": 162514, "page_no": 2, "y0": 440.0, "x0": 72.0,
         "x1": 550.0, "page_height": 800.0,
         "text": "(3) It shall come into force at once."},
    ]
    patch = {"page_no": 2, "match_text": "Short title, extent and commencement",
             "before_text": "commencement.___(1)",
             "after_text": "commencement.___\n(1)"}
    parsed = corpus_segment.segment(blocks, profile="unreleased-v4",
                                    curation_patches=[patch])
    section = next(n for n in parsed.flatten()
                   if n.kind == "section" and n.label == "1")
    assert [child.label for child in section.children] == ["1", "2", "3"]
    assert section.children[0].first_block == 162512


def test_2140_repeal_heading_opens_only_reviewed_section(monkeypatch):
    monkeypatch.setattr(corpus_segment, "parse_contents", lambda _blocks: (
        {"8": "Power to make rules.", "9": "Repeal."}, 1, True))
    blocks = [
        {"id": 1, "page_no": 1, "text": "CONTENTS 8. Power to make rules. 9. Repeal.",
         "y0": 50.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
        {"id": 2, "page_no": 2,
         "text": "8. Power to make rules. Government may make rules.",
         "y0": 200.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
        {"id": 3, "page_no": 3,
         "text": "Repeal.— The former Ordinance is hereby repealed.",
         "y0": 200.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
    ]
    override = {"source_unnumbered_section_openers": [{
        "source_block_id": 3, "label": "9", "heading": "Repeal",
        "source_prefix": "Repeal.—", "after_section_label": "8"}]}
    parsed = corpus_segment.segment(blocks, profile="unreleased-v4",
                                    structural_overrides=override)
    sections = [n for n in parsed.flatten() if n.kind == "section"]
    assert [(n.label, n.first_block) for n in sections] == [("8", 2), ("9", 3)]
    assert sections[1].text == "The former Ordinance is hereby repealed."
    assert 3 not in sections[0].blocks
    assert parsed.block_roles[3][1] is sections[1]


def test_2140_repeal_override_rejects_wrong_source_or_parent(monkeypatch):
    monkeypatch.setattr(corpus_segment, "parse_contents", lambda _blocks: (
        {"8": "Power to make rules.", "9": "Repeal."}, 1, True))
    blocks = [
        {"id": 1, "page_no": 1, "text": "CONTENTS 8. Power to make rules. 9. Repeal.",
         "y0": 50.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
        {"id": 2, "page_no": 2,
         "text": "8. Power to make rules. Government may make rules.",
         "y0": 200.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
        {"id": 3, "page_no": 3,
         "text": "Repeal.— The former Ordinance is hereby repealed.",
         "y0": 200.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
    ]
    for bad in ({"source_block_id": 3, "label": "9", "heading": "Repeal",
                 "source_prefix": "Not printed.—", "after_section_label": "8"},
                {"source_block_id": 3, "label": "9", "heading": "Repeal",
                 "source_prefix": "Repeal.—", "after_section_label": "7"}):
        with pytest.raises(ValueError, match="lacks matching source"):
            corpus_segment.segment(blocks, profile="unreleased-v4",
                structural_overrides={"source_unnumbered_section_openers": [bad]})


def test_2140_ascii_quoted_definition_items_remain_distinct():
    text = "(a) ‘Chairman’ means the chairman;\n \n(b) 'Foundation' means the body;"
    blocks = [{"id": 1, "page_no": 1,
               "text": "2. Definitions. In this Act the terms mean as follows:",
               "y0": 200.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
              {"id": 2, "page_no": 1, "text": text,
               "y0": 240.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0}]
    parsed = corpus_segment.segment(blocks, profile="unreleased-v4")
    section = next(n for n in parsed.flatten()
                   if n.kind == "section" and n.label == "2")
    assert [(n.label, n.first_block) for n in section.children] == [
        ("a", 2), ("b", 2)]
    assert "Foundation" not in section.children[0].text
    assert "'Foundation'" in section.children[1].text


def test_3128_source_backed_opening_section_keeps_later_sections_peers(monkeypatch):
    monkeypatch.setattr(corpus_segment, "parse_contents", lambda _blocks: (
        {"1": "Short title Extent", "2": "Repeal of enactments"}, 5, True))
    texts = [
        "CONTENTS", "1. Short title Extent", "2. Repeal of enactments",
        "THE TREASURE-TROVE ACT, 1878", "Preamble. It is hereby enacted as follows:",
        "Short title. This Act may be called the Treasure-trove Act, 1878.",
        "Extent. It extends to the whole of Pakistan.",
        "2. [Repeal of enactments.] Rep. by the Amending Act, 1891.",
    ]
    blocks = [{"id": i, "page_no": 1 if i <= 3 else 2,
               "text": value, "y0": i * 50.0,
               "x0": 70.0, "x1": 500.0, "page_height": 800.0}
              for i, value in enumerate(texts, 1)]
    parsed = corpus_segment.segment(blocks, profile="unreleased-v4",
        structural_overrides={
            "source_body_start_block": 4,
            "source_unnumbered_section_openers": [{
                "source_block_id": 6, "label": "1",
                "heading": "Short title Extent", "source_prefix": "Short title.",
                "after_section_label": "__ROOT__"}]})
    first, second = [n for n in parsed.flatten() if n.kind == "section"]
    assert first.label == "1" and second.label == "2"
    assert first.parent is second.parent
    assert first.depth == second.depth
    assert first.first_block == 6 and 7 in first.blocks
    assert "Extent. It extends" in first.text
    assert "1. Short title" not in first.text


def test_2674_reviewed_body_start_accepts_only_exact_contents_ocr_typo(monkeypatch):
    """PDF p.1 prints CONTENTS; extraction has CONTETNS (block 232054)."""
    monkeypatch.setattr(corpus_segment, "parse_contents", lambda _blocks: (
        {"1": "Short title Local extent Commencement", "2": "[Repeal]",
         "3": "Killing and capture", "4": "Rights of Government"}, 11, True))
    texts = [
        "CONTETNS", "1. Short title Local extent Commencement",
        "2. [Repeal]", "3. Killing and capture", "4. Rights of Government",
        "THE ELEPHANTS' PRESERVATION ACT, 1879",
        "Preamble. It is hereby enacted as follows:",
        "Short title. This Act may be called the Elephants' Preservation Act, 1879.",
        "Local extent. It may be extended to any local area.",
        "Commencement. It shall come into force on the passing thereof.",
        "2. [Repeal.] Rep. by the Repealing and Amending Act, 1930.",
        "3. Killing and capture. No person shall kill a wild elephant.",
    ]
    blocks = [{"id": i, "page_no": 1 if i <= 5 else 2,
               "text": value, "y0": i * 40.0, "x0": 72.0,
               "x1": 500.0, "page_height": 800.0}
              for i, value in enumerate(texts, 1)]
    overrides = {"source_body_start_block": 6,
                 "source_unnumbered_section_openers": [{
                     "source_block_id": 8, "label": "1",
                     "heading": "Short title Local extent Commencement",
                     "source_prefix": "Short title.",
                     "after_section_label": "__ROOT__"}]}
    parsed = corpus_segment.segment(blocks, profile="unreleased-v4",
                                    structural_overrides=overrides)
    sections = [n for n in parsed.flatten() if n.kind == "section"]
    assert [n.label for n in sections[:3]] == ["1", "2", "3"]
    assert sections[0].blocks == [8, 9, 10]
    with pytest.raises(ValueError, match="override not reached"):
        corpus_segment.segment(blocks, structural_overrides=overrides)


def test_3128_opening_section_refuses_unmatched_contents(monkeypatch):
    monkeypatch.setattr(corpus_segment, "parse_contents", lambda _blocks: (
        {"1": "Different subject"}, 1, True))
    blocks = [{"id": 1, "page_no": 1, "text": "CONTENTS",
               "y0": 20.0, "x0": 70.0, "x1": 500.0, "page_height": 800.0},
              {"id": 2, "page_no": 2,
               "text": "Short title. This Act may be called Example Act.",
               "y0": 200.0, "x0": 70.0, "x1": 500.0,
               "page_height": 800.0}]
    with pytest.raises(ValueError, match="lacks matching source"):
        corpus_segment.segment(blocks, profile="unreleased-v4",
            structural_overrides={"source_unnumbered_section_openers": [{
                "source_block_id": 2, "label": "1",
                "heading": "Short title", "source_prefix": "Short title.",
                "after_section_label": "__ROOT__"}]})


def test_3128_second_proviso_reparented_under_section():
    root = corpus_segment.Node("instrument", "", depth=0)
    section = corpus_segment.Node("section", "12", depth=3,
                                  first_block=10, parent=root)
    clause = corpus_segment.Node("clause", "b", depth=5,
                                 first_block=11, parent=section)
    proviso = corpus_segment.Node("proviso", "Provided", depth=6,
                                  first_block=12, parent=clause)
    root.children.append(section)
    section.children.append(clause)
    clause.children.append(proviso)
    patch = {"evidence": {"structural_overrides": {
        "source_reparent_blocks": [{
            "source_block_id": 12, "parent_block_id": 10,
            "kind": "proviso", "source_kind": "proviso",
            "parent_kind": "section", "parent_label": "12"}]}}}
    overrides = reviewed_structural_overrides([], [patch])
    corpus_segment._apply_source_reparents(root,
        overrides["source_reparent_blocks"], [], {})
    assert proviso.parent is section and proviso in section.children
    assert proviso not in clause.children


def test_3128_exact_unnumbered_divisions_keep_sections_in_source_order():
    texts = ["PRELIMINARY", "1. Short title. This Act applies.",
             "PROCEDURE ON FINDING TREASURE",
             "4. Notice by finder. The finder shall give notice.",
             "PENALTIES", "20. Penalty. An offence is punishable."]
    blocks = [{"id": i, "page_no": 1, "text": value,
               "y0": i * 70.0, "x0": 70.0,
               "x1": 500.0, "page_height": 800.0}
              for i, value in enumerate(texts, 1)]
    overrides = {"source_unnumbered_part_headings": [
        {"source_block_id": 1, "heading": "PRELIMINARY"},
        {"source_block_id": 3, "heading": "PROCEDURE ON FINDING TREASURE"},
        {"source_block_id": 5, "heading": "PENALTIES"}]}
    parsed = corpus_segment.segment(blocks, profile="unreleased-v4",
                                    structural_overrides=overrides)
    parts = [n for n in parsed.root.children if n.kind == "part"]
    assert [n.label for n in parts] == [
        "PRELIMINARY", "PROCEDURE ON FINDING TREASURE", "PENALTIES"]
    assert [[child.label for child in part.children] for part in parts] == [
        ["1"], ["4"], ["20"]]
    assert all(parsed.block_roles[bid][0] == "heading" for bid in (1, 3, 5))


def test_3128_exact_division_refuses_changed_source_text():
    blocks = [{"id": 1, "page_no": 1, "text": "DIFFERENT HEADING",
               "y0": 200.0, "x0": 70.0,
               "x1": 500.0, "page_height": 800.0}]
    with pytest.raises(ValueError, match="lacks exact heading evidence"):
        corpus_segment.segment(blocks, profile="unreleased-v4",
            structural_overrides={"source_unnumbered_part_headings": [
                {"source_block_id": 1, "heading": "PRELIMINARY"}]})
