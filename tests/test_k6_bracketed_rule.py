"""Agent K6's `reviewed_bracketed_rule` (segmenter group 38, 19 Oct 2026; doc 4479, owner export m q1
'part-scoped'; from claude/agK6/work/test_k6_rule_p_DRAFT.py 10b0efcc, K6's draft letter not used): a reviewed
`source_bracketed_rules` entry opens a printed '(N)' rule inside its Part with its margin heading; plus its two
data-gated extras and the key wiring. Pure: segment() over blocks."""

import pytest

RULE_BR = "reviewed_bracketed_rule"
KEY_BR = "source_bracketed_rules"


import nizam.corpus.segment as SEG  # noqa: E402


def _b(i, text, y, page=1):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


DOC = [
    _b(1, "1) Short title and commencement;\ni. These rules may be called the Test Rules, 2021;\nii They shall come "
          "into force at once.", 60),
    _b(2, "PART-I", 120),
    _b(3, "APPOINTMENTS & PROMOTIONS", 140),
    _b(4, "Appointment\n(1)\nNo person shall be appointed unless he/she is a citizen of Pakistan;\nMethod of Appointment\n"
          "(2)\n(a) Appointment to a post shall be made by appointment or promotion.\n(b) The method of appointment shall "
          "be as laid down in the Schedule.", 170),
    _b(5, "Deputation\t(6) (a)\tAn employee of Government may be posted on Deputation basis.\n(b)\tThe Foundation shall "
          "reserve the right to repatriate an employee.\nShort term appointment\t(7)\tNotwithstanding the provisions "
          "contained in rule (2) above the appointing authority may fill a post.", 260),
    _b(6, "Officiating Charge", 340),
    _b(7, "(12)", 340),
    _b(8, "The Managing Director may assign officiating charge of a post to any employee.", 340),
]
SPEC = {"source_bracketed_rules": [
    {"source_block_id": 4, "label": "1", "heading": "Appointment"},
    {"source_block_id": 4, "label": "2", "heading": "Method of Appointment"},
    {"source_block_id": 5, "label": "6", "heading": "Deputation"},
    {"source_block_id": 5, "label": "7", "heading": "Short term appointment"},
    {"source_block_id": 7, "label": "12", "heading": None},
],
    # a margin heading printed as a block of its own: the existing keys set it aside and join it to rule P's section
    "source_apparatus_blocks": [6],
    "source_margin_note_pieces": [{"source_block_ids": [6], "target_block_id": 7, "label": "12",
                                   "heading": "Officiating Charge"}],
}


def _paths(seg):
    return {p: n for n, p in SEG.assign_paths(seg, "t")}


def _sections(paths):
    return {n.label: (p, n) for p, n in paths.items() if n.kind == "section"}


def test_bracketed_rule_opens_the_bracketed_rules_inside_the_part_with_their_headings():
    secs = _sections(_paths(SEG.segment(DOC, profile="unreleased-v4", structural_overrides=SPEC)))
    for lab, head in (("1", "Appointment"), ("2", "Method of Appointment"), ("6", "Deputation"),
                      ("7", "Short term appointment"), ("12", "Officiating Charge")):
        assert lab in secs, sorted(secs)
        p, n = secs[lab]
        assert ".pt_" in p or p.split(".")[-2].startswith("pt_"), p      # inside Part I
        assert (n.heading or None) == head, (lab, n.heading)
    assert "Officiating" not in " ".join(secs["7"][1].text_parts)       # the heading block is not this rule's text
    assert "Short term appointment" not in " ".join(secs["6"][1].text_parts + [
        t for c in secs["6"][1].children for t in c.text_parts])
    assert any(p.startswith(secs["2"][0] + ".cl_a") for p in _paths(SEG.segment(
        DOC, profile="unreleased-v4", structural_overrides=SPEC)))         # (2)(a) stays a clause of rule 2


def test_bracketed_rule_is_inert_without_the_key():
    on = _paths(SEG.segment(DOC, profile="unreleased-v4"))
    prof = SEG.SEGMENTATION_PROFILES["unreleased-v4"]
    SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof - {RULE_BR}
    try:
        off = _paths(SEG.segment(DOC, profile="unreleased-v4"))
    finally:
        SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof
    assert sorted(on) == sorted(off)


def test_bracketed_rule_needs_its_profile_rule():
    with pytest.raises(ValueError, match="malformed"):
        SEG.segment(DOC, profile="default", structural_overrides=SPEC)


@pytest.mark.parametrize("bad, why", [
    ({"source_block_id": 4, "label": "x1", "heading": "Appointment"}, "malformed"),          # label not digits
    ({"source_block_id": 4, "label": "1", "heading": "Ap"}, "malformed"),                    # heading too short
    ({"source_block_id": 4, "label": "1", "heading": "Promotion"}, "matches 0 times"),       # heading not printed there
    ({"source_block_id": 4, "label": "3", "heading": None}, "not reached"),                  # '(3)' not printed in block 4
    ({"source_block_id": 5, "label": "1", "heading": None}, "not reached"),                  # wrong block
])
def test_bracketed_rule_fails_closed(bad, why):
    with pytest.raises(ValueError, match=why):
        SEG.segment(DOC, profile="unreleased-v4", structural_overrides={"source_bracketed_rules": [bad]})


DOC2 = DOC + [
    _b(9, "(SCHEDULE - I)", 400),
    _b(10, "See Rule 34", 420),
    _b(11, "S.No.\nPosts\nAuthority\n1.\nPay Group 1 to 11\nManaging Director\n2.\nPay Group 12 to 15\nChairman", 440),
]
SPEC2 = dict(SPEC, source_division_openers=[{"source_block_id": 9, "kind": "schedule", "label": "SCHEDULE - I"}])


def test_bracketed_rule_reads_a_bracketed_schedule_heading_and_closes_the_part():
    paths = _paths(SEG.segment(DOC2, profile="unreleased-v4", structural_overrides=SPEC2))
    sch = [p for p, n in paths.items() if n.kind == "schedule"]
    assert len(sch) == 1 and "pt_" not in sch[0], sch          # Schedule I at the root, not inside Part I
    assert not any(n.kind == "section" and n.label in ("1", "2") and p.startswith(sch[0]) for p, n in paths.items())


def test_bracketed_rule_bracketed_schedule_heading_needs_the_key():
    with pytest.raises(ValueError, match="does not print FORM/APPENDIX"):
        SEG.segment(DOC2, profile="unreleased-v4",
                    structural_overrides={"source_division_openers": SPEC2["source_division_openers"]})


def test_bracketed_rule_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, READING_KEYS, STRUCTURAL_KEYS
    assert KEY_BR in STRUCTURAL_KEYS and KEY_BR in READING_KEYS and KEY_BR in GENERIC_STRUCTURAL_KEYS
    assert KEY_BR in STRUCTURAL_PATCH_KEYS
    ok, ident = W._BZ_KEYED_LIST_KEYS[KEY_BR]
    good = {"source_block_id": 5, "label": "12", "heading": "Pay & Allowances"}
    assert ident == "label" and ok(good) and ok(dict(good, heading=None))
    for bad in (dict(good, label="1a"), dict(good, label="1234"), dict(good, heading="ab"),
                dict(good, source_block_id=0), {k: v for k, v in good.items() if k != "heading"}):
        assert not ok(bad), bad
