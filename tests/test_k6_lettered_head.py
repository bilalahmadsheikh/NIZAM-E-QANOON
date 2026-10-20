"""Agent K6's `reviewed_lettered_head` (segmenter group 37, 18 Oct 2026; doc 4591, owner
decision-review-2026-10-18-4591.json q3 'open-heads'; from claude/agK6/work/test_k6_rule_g_DRAFT.py 739d2159,
K6's draft letter not used): a reviewed `source_lettered_head_blocks` entry opens a printed '(E) CAPS ...:' head
as its Part, labelled as printed. Pure: segment() over blocks; plus the key wiring."""

import pytest

RULE_LH = "reviewed_lettered_head"
KEY_LH = "source_lettered_head_blocks"


import nizam.corpus.segment as SEG  # noqa: E402


def _b(i, text, y):
    return {"id": i, "page_no": 1, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


DOC = [
    _b(1, "8. Health and safety at workplaces.- The employer shall observe the following:", 80),
    _b(2, "(D) FLOOR, STAIRS, MEANS OF ACCESS, PROPER WORKING SPACE.", 110),
    _b(3, "(1) The particulars of each room shall be entered in Form C.", 140),
    _b(4, "(2) Every floor shall be of sound construction.", 170),
    _b(5, "(E) DRINKING WATER AND CONSERVANCY:", 200),
    _b(6, "(1) In every factory there shall be provided free of charge wholesome drinking water.", 230),
    _b(7, "(2) Where drinking water is obtained from a well, the well shall be covered.", 260),
]
HEADS = {"source_lettered_head_blocks": [{"source_block_id": 5, "label": "E", "source_prefix": "(E) DRINKING WATER"}]}


def _paths(seg):
    return {p: n for n, p in SEG.assign_paths(seg, "t")}


def _parts(paths):
    return sorted((p, n.label) for p, n in paths.items() if n.kind == "part")


def test_lettered_head_opens_the_reviewed_head_as_its_part():
    paths = _paths(SEG.segment(DOC, profile="unreleased-v4", structural_overrides=HEADS))
    labels = [lab for _p, lab in _parts(paths)]
    assert "E" in labels, _parts(paths)
    e = [p for p, n in paths.items() if n.kind == "part" and n.label == "E"][0]
    assert any(p.startswith(e + ".") for p in paths), sorted(paths)        # its sub-rules (1), (2) are under it


def test_lettered_head_is_inert_without_the_key():
    on = _paths(SEG.segment(DOC, profile="unreleased-v4"))
    prof = SEG.SEGMENTATION_PROFILES["unreleased-v4"]
    SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof - {RULE_LH}
    try:
        off = _paths(SEG.segment(DOC, profile="unreleased-v4"))
    finally:
        SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof
    assert sorted(on) == sorted(off)


def test_lettered_head_needs_its_profile_rule():
    with pytest.raises(ValueError, match="malformed"):
        SEG.segment(DOC, profile="default", structural_overrides=HEADS)


@pytest.mark.parametrize("bad, why", [
    ({"source_block_id": 5, "label": "e", "source_prefix": "(E) DRINKING WATER"}, "malformed"),        # lower case
    ({"source_block_id": 5, "label": "E", "source_prefix": "DRINKING WATER AND"}, "malformed"),        # no '(E)'
    ({"source_block_id": 5, "label": "F", "source_prefix": "(F) DRINKING WATER"}, "not reached"),      # not printed
    ({"source_block_id": 6, "label": "E", "source_prefix": "(E) DRINKING WATER"}, "not reached"),      # wrong block
])
def test_lettered_head_fails_closed(bad, why):
    with pytest.raises(ValueError, match=why):
        SEG.segment(DOC, profile="unreleased-v4", structural_overrides={"source_lettered_head_blocks": [bad]})


def test_lettered_head_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, READING_KEYS, STRUCTURAL_KEYS
    assert KEY_LH in STRUCTURAL_KEYS and KEY_LH in READING_KEYS and KEY_LH in GENERIC_STRUCTURAL_KEYS
    assert KEY_LH in STRUCTURAL_PATCH_KEYS
    ok, ident = W._BZ_KEYED_LIST_KEYS[KEY_LH]
    good = {"source_block_id": 5, "label": "E", "source_prefix": "(E) DRINKING WATER"}
    assert ident == "source_block_id" and ok(good)
    for bad in (dict(good, label="e"), dict(good, label="EE"), dict(good, source_prefix="(E) DR"),
                dict(good, source_block_id=0), {k: v for k, v in good.items() if k != "label"}):
        assert not ok(bad), bad
    merged = W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {KEY_LH: [good]}}},
                                                  {"evidence": {"structural_overrides": {KEY_LH: [good]}}}])
    assert merged[KEY_LH] == [good]
