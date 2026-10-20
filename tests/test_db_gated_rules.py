"""Agent DB's data-gated rules (stage 3, owner 11 Oct 2026; docs/SEGMENTATION-PROFILES.md).

The 23 Sep parser-drift repair (`.patch_drift.py`) ported ungated moved 168 released expressions outside its group,
so only a gated form is admitted. Each rule is inert without a reviewed reading on the observation:

  contents_marker_block      `source_contents_marker_blocks` [block ids]: in exactly those blocks a bare contents
                             column word SET OFF as a header is the contents marker (doc 1119 p1 'C O N T E N T'
                             fused with its first entry); fails closed if a named block is missing or not set off.
  heading_scan_section_only  `source_heading_scan_section_only: true`: the marginal-heading scan's own-block skip
                             only for a section label (docs 1139, 2034, 3255 ...).
  not_running_header_blocks  the reviewed blocks are honoured in every profile (doc 3255 pp80-83 '15%').
"""
import pytest

from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


def test_the_worker_merges_the_two_keys():
    merged = reviewed_structural_overrides([], [
        _patch(source_contents_marker_blocks=[12, 10]), _patch(source_contents_marker_blocks=[11]),
        _patch(source_heading_scan_section_only=True), _patch(source_heading_scan_section_only=True)])
    assert merged["source_contents_marker_blocks"] == [10, 11, 12]
    assert merged["source_heading_scan_section_only"] is True
    with pytest.raises(ValueError, match="source_heading_scan_section_only"):
        reviewed_structural_overrides([], [_patch(source_heading_scan_section_only=False)])
    with pytest.raises(ValueError, match="source_contents_marker_blocks"):
        reviewed_structural_overrides([], [_patch(source_contents_marker_blocks=["x"])])
    assert "source_contents_marker_blocks" not in reviewed_structural_overrides([], [])


def test_a_set_off_column_word_counts_only_in_a_reviewed_block():
    fused = "C O N T E N T\n01. Short title and commencement.\n02. Definitions."
    prose = "In these rules the following Sections\nSections\n1. Short title."
    assert not S._has_contents_marker(fused)                      # inert without a reading
    token = S._REVIEWED_CONTENTS_MARKERS.set((frozenset({fused, prose}), set()))
    try:
        assert S._has_contents_marker(fused)                      # set off: heads the first entry
        assert not S._has_contents_marker(prose)                  # sentence text above it: not a header
    finally:
        S._REVIEWED_CONTENTS_MARKERS.reset(token)
    assert S._column_word_is_set_off(["C O N T E N T", "01. Short title."], 0)
    assert not S._column_word_is_set_off(["the following Sections", "Sections", "1. Short title."], 1)


def _blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100.0 + 20 * i, "page_height": 792.0,
             "x0": 72.0, "x1": 480.0} for i, t in enumerate(texts)]


def test_a_named_marker_block_fails_closed():
    blocks = _blocks("1. Short title. This Act may be called the Test Act.", "2. Definitions. In this Act.")
    with pytest.raises(ValueError, match="source contents marker block not in the document"):
        S.segment(blocks, structural_overrides={"source_contents_marker_blocks": [999]})
    with pytest.raises(ValueError, match="lacks a set-off contents header"):
        S.segment(blocks, structural_overrides={"source_contents_marker_blocks": [100]})


def test_the_rules_are_inert_without_readings():
    blocks = _blocks("C O N T E N T\n1. Short title.\n2. Definitions.",
                     "1. Short title. This Act may be called the Test Act.",
                     "2. Definitions. In this Act, unless the context otherwise requires.")
    plain = S.segment(blocks)
    again = S.segment(blocks, structural_overrides={})
    assert [(n.kind, n.label, n.heading, n.text) for n in plain.flatten()] == \
        [(n.kind, n.label, n.heading, n.text) for n in again.flatten()]
