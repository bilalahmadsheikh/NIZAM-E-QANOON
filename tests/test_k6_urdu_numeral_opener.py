"""Agent K6's `reviewed_urdu_numeral_opener` (segmenter group 34, 18 Oct 2026; doc 4631, owner
decision-review-2026-10-18-4631.json q1 'urdu-rule-openers'; from claude/agK6/work/test_k6_rule_u_DRAFT.py
64517141, K6's draft letter not used): a reviewed `source_printed_rule_openers` entry may carry an Urdu-digit
label, printed as is, opening a rule (section) or sub-rule (subsection); the path key transliterates the digits
only in a parse that applied such an opener. Pure: segment() / assign_paths() over blocks."""

import pytest

RULE_URDU = "reviewed_urdu_numeral_opener"


import nizam.corpus.segment as SEG  # noqa: E402


def _b(i, text, y):
    return {"id": i, "page_no": 1, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


BYELAWS = [
    _b(1, "(۴) اندراج کو مؤثر بنانے کیلئے مقامی کونسل کے فرائض:-", 100),
    _b(2, "(۱) ہر مقامی کونسل اپنی حدود میں پیدائش و اموات کا اندراج کرے گی۔", 130),
    _b(3, "(۲) رجسٹرار رجسٹروں کو دفتر میں محفوظ رکھے گا۔", 160),
    _b(4, "(۵) پیدائش کی رپورٹ کرنے کی ذمہ داری اور اس کا طریقہ کار:", 190),
    _b(5, "(۱) ہسپتال کے سربراہ ماہانہ رپورٹ بھیجیں گے۔", 220),
    _b(6, "(۲) گھر کا رکن اعلیٰ اندراج کروائے گا۔", 250),
]
OPENERS = [{"source_block_id": 1, "label": "۴", "source_prefix": "(۴) اندراج کو مؤثر"},
           {"source_block_id": 4, "label": "۵", "source_prefix": "(۵) پیدائش کی رپورٹ"}]


def _paths(seg):
    return {p: n for n, p in SEG.assign_paths(seg, "t")}


def test_urdu_opener_opens_urdu_rules_printed_as_is():
    seg = SEG.segment(BYELAWS, profile="unreleased-v4", structural_overrides={"source_printed_rule_openers": OPENERS})
    paths = _paths(seg)
    for p in ("t.s_4", "t.s_4.ss_1", "t.s_4.ss_2", "t.s_5", "t.s_5.ss_1", "t.s_5.ss_2"):
        assert p in paths, (p, sorted(paths))
    assert paths["t.s_4"].kind == "section" and paths["t.s_4"].label == "۴"        # the printed label, not '4'
    assert paths["t.s_5.ss_2"].label == "۲"
    assert not any("_n" in p.rsplit(".", 1)[-1] or p.endswith("_x") for p in paths)


def test_urdu_opener_is_inert_without_the_reading():
    on = _paths(SEG.segment(BYELAWS, profile="unreleased-v4"))
    off = _paths(SEG.segment(BYELAWS, profile="default"))
    assert sorted(on) == sorted(off)
    assert not any(p.startswith("t.s_") for p in on)           # no rule opens: the flat sub-section run, as today


def test_urdu_opener_needs_its_profile_rule():
    with pytest.raises(ValueError, match="malformed"):
        SEG.segment(BYELAWS, profile="default", structural_overrides={"source_printed_rule_openers": OPENERS})


@pytest.mark.parametrize("bad, why", [
    ({"source_block_id": 1, "label": "۴", "source_prefix": "اندراج کو مؤثر بنانے"}, "malformed"),     # no '(۴)'
    ({"source_block_id": 1, "label": "۴۴۴۴", "source_prefix": "(۴) اندراج کو مؤثر"}, "malformed"),  # 4 digits
    ({"source_block_id": 1, "label": "۶", "source_prefix": "(۶) اندراج کو مؤثر"}, "not found once"),  # not printed
    ({"source_block_id": 2, "label": "۴", "source_prefix": "(۴) اندراج کو مؤثر"}, "not found once"),  # wrong block
])
def test_urdu_opener_fails_closed(bad, why):
    with pytest.raises(ValueError, match=why):
        SEG.segment(BYELAWS, profile="unreleased-v4",
                    structural_overrides={"source_printed_rule_openers": [bad, OPENERS[1]]})


def test_urdu_opener_leaves_ascii_labels_and_unmarked_urdu_trees_unchanged():
    ascii_blocks = [_b(1, "4. Duties of local councils.- (1) Every council shall register births.", 100),
                    _b(2, "(2) The registrar shall keep the registers.", 130)]
    ro = [{"source_block_id": 1, "label": "4", "source_prefix": "4. Duties of local councils"}]
    a = _paths(SEG.segment(ascii_blocks, profile="unreleased-v4", structural_overrides={"source_printed_rule_openers": ro}))
    assert "t.s_4" in a and "t.s_4.ss_2" in a
    # an Urdu tree parsed without any Urdu-digit opener keeps today's path keys (released 4616-4625 are untouched)
    plain = _paths(SEG.segment(BYELAWS, profile="unreleased-v4"))
    assert any(p.endswith("_x") or "_x_" in p for p in plain)


def test_urdu_opener_path_key_transliterates_arabic_script_labels():
    key = SEG._k6urdu_key
    assert key("۱۲") == "12" and key("٤") == "4"
    import re as _re
    slug = lambda t: _re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")  # noqa: E731
    assert slug(key("ب")) == "beh" and slug(key("الف")) == "alef_lam_feh"
    assert slug(key("الف۔ ۱")) == "alef_lam_feh_1" and slug(key("ب-1")) == "beh_1"
