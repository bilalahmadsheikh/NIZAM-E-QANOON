"""A reviewed schedule grid cell may fuse a functional unit and post number."""

import pytest

from nizam.corpus.segment import segment
from nizam.workers.segment import reviewed_structural_overrides


def _blocks(row_text="Architecture 1. Chief"):
    texts = [
        "1. Posts. The posts are set out in the Schedule annexed.",
        "SCHEDULE",
        "Name of the Post",
        row_text,
        "Architect. (BS-20)",
        "2. Director Architecture. (BS-19)",
    ]
    return [
        {"id": number, "page_no": 1 if number == 1 else 2,
         "text": value, "x0": 72.0, "x1": 500.0,
         "y0": number * 80.0, "y1": number * 80.0 + 30,
         "page_height": 800.0}
        for number, value in enumerate(texts, 1)
    ]


SPEC = {"source_block_id": 4, "schedule_block_id": 2,
        "label": "1", "source_text": "Architecture 1. Chief"}


def test_reviewed_grid_row_opens_under_schedule_with_provenance():
    parsed = segment(_blocks(), profile="unreleased-v4",
                     structural_overrides={"source_schedule_row_openers": [SPEC]})
    schedule = next(node for node in parsed.flatten() if node.kind == "schedule")
    row = next(node for node in schedule.children
               if node.kind == "clause" and node.label == "1")
    assert row.first_block == 4
    assert row.parent is schedule
    assert "Architecture Chief" in row.text
    assert 4 in row.blocks
    assert parsed.block_roles[4] == ("schedule_row", row)


def test_grid_override_fails_closed_on_source_or_schedule_change():
    with pytest.raises(ValueError, match="lacks exact grid evidence"):
        segment(_blocks("Architecture 1. Different"), profile="unreleased-v4",
                structural_overrides={"source_schedule_row_openers": [SPEC]})
    with pytest.raises(ValueError, match="lacks exact grid evidence"):
        segment(_blocks(), profile="unreleased-v4",
                structural_overrides={"source_schedule_row_openers": [
                    {**SPEC, "schedule_block_id": 99}]})


def test_reviewed_row_override_merges_only_valid_spec():
    patch = {"evidence": {"structural_overrides": {
        "source_schedule_row_openers": [SPEC]}}}
    assert reviewed_structural_overrides([], [patch]) == {
        "source_schedule_row_openers": [SPEC]}
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides([], [{"evidence": {
            "structural_overrides": {"source_schedule_row_openers": [
                {**SPEC, "label": ""}]}}}])
