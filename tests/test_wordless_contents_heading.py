"""Rule 8 `wordless_contents_heading` (doc 4149 contents p2 '1[18A.]': the
row's 'heading' is the closing bracket ']', which headed the materialised stub s.18A).

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_wordless_contents_heading_DRAFT.py, against the live module (export j/l group 14;
one combined full released A/B over the 16 Oct groups).
"""
import os

from nizam.corpus import segment as S


def _b(i, text, y0, page):
    return {"id": i, "text": text, "page_no": page, "x0": 86.0, "x1": 476.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "CONTENTS \n", 40.0, 1),
            _b(2, "1. \nShort title. \n", 60.0, 1),
            _b(3, "2. \nDefinitions. \n", 80.0, 1),
            _b(4, "1[2A.] \n", 100.0, 1),
            _b(5, "3. \nRepeal. \n", 120.0, 1),
            _b(10, "1. \nShort title.— These rules may be called the Test Rules. \n", 40.0, 2),
            _b(11, "2. \nDefinitions.— In these rules the Board means the Board of Revenue. \n", 80.0, 2),
            _b(12, "2A. \nThe Board may call for any information it requires. \n", 120.0, 2),
            _b(13, "3. \nRepeal.— The Test Rules, 1960 are repealed. \n", 160.0, 2)]


def _node(seg, label):
    return next((n for n in seg.flatten() if n.kind == "section" and n.label == label), None)


def _toc_heading(seg, label):
    return next((e.get("heading") for e in (seg.toc_entries or []) if e.get("label") == label), None)


def test_8_fixture_reads_the_bracket_as_the_row_heading():
    seg = S.segment(_blocks(), profile="unreleased-v4")
    assert _toc_heading(seg, "2A") == "]"


def test_8_a_wordless_row_heading_heads_nothing():
    seg = S.segment(_blocks(), profile="unreleased-v4")
    assert _node(seg, "2A") is not None and not _node(seg, "2A").heading


def test_8_worded_rows_still_head_their_units():
    seg = S.segment(_blocks(), profile="unreleased-v4")
    assert (_node(seg, "3").heading or "").startswith("Repeal")


def test_8_off_without_its_profile_rule():
    profiles = dict(S.SEGMENTATION_PROFILES)
    S.SEGMENTATION_PROFILES["agjd-no-8"] = profiles["unreleased-v4"] - {"wordless_contents_heading"}
    try:
        seg = S.segment(_blocks(), profile="agjd-no-8")
        assert _node(seg, "2A").heading == "]"
    finally:
        S.SEGMENTATION_PROFILES.pop("agjd-no-8", None)
