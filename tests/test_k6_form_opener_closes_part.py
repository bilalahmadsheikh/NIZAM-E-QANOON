"""Agent K6's `form_code_opener_closes_part` (segmenter group 35, 18 Oct 2026; doc 4631, owner card-4631-v3.json q5
'forms-at-root'; from claude/agK6/work/test_k6_rule_f_DRAFT.py 3a2feb67, K6's draft letter not used): a reviewed
form code opener (agent K4's reviewed_form_code_opener, source_form_code_openers) opens its form at the depth of the
shallowest open body Part -- or of a form an earlier reviewed opener opened that way -- so forms printed after the
last Part's rules are siblings of the Parts, not children of the last Part. Pure: segment() / assign_paths()."""

RULE_FCP = "form_code_opener_closes_part"


import nizam.corpus.segment as SEG  # noqa: E402


def _b(i, text, y, page=1):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


DOC = [
    _b(1, "PART I", 100),
    _b(2, "1. Short title.- These rules may be called the Registration Rules.", 130),
    _b(3, "PART II", 160),
    _b(4, "2. Forms.- The forms annexed to these rules shall be used.", 190),
    _b(5, "3. Repeal.- The earlier rules are repealed.", 220),
    _b(6, "FORM A", 100, 2),
    _b(7, "Application for registration of a birth. Name of the child ________", 130, 2),
    _b(8, "FORM B", 100, 3),
    _b(9, "Register of births. Serial number ________ Date of entry ________", 130, 3),
]
OPENERS = {"source_form_code_openers": [
    {"source_block_id": 6, "label": "A", "label_block_id": 6, "printed": "FORM A"},
    {"source_block_id": 8, "label": "B", "label_block_id": 8, "printed": "FORM B"}]}


def _paths(seg):
    return {p: n for n, p in SEG.assign_paths(seg, "t")}


def _forms(paths):
    return sorted(p for p, n in paths.items() if n.kind == "form")


def test_form_opener_closes_part_reviewed_forms_open_beside_the_parts():
    on = _paths(SEG.segment(DOC, profile="unreleased-v4", structural_overrides=OPENERS))
    forms = _forms(on)
    assert len(forms) == 2 and all(p.count(".") == 1 for p in forms), forms     # t.form_A, t.form_B: at the root
    assert not any(".pt_" in p for p in forms)
    parts = sorted(p for p, n in on.items() if n.kind == "part")
    assert len(parts) == 2, parts                                                   # both Parts stand, rules under them


def test_form_opener_closes_part_needs_its_profile_rule():
    off = _paths(SEG.segment(DOC, profile="default", structural_overrides=OPENERS))
    forms = _forms(off)
    assert forms and all(".pt_" in p for p in forms), forms                         # today: under the last Part


def test_form_opener_closes_part_is_inert_without_the_reviewed_openers():
    on = _paths(SEG.segment(DOC, profile="unreleased-v4"))
    assert RULE_FCP in SEG.SEGMENTATION_PROFILES["unreleased-v4"]
    prof = SEG.SEGMENTATION_PROFILES["unreleased-v4"]
    SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof - {RULE_FCP}
    try:
        off = _paths(SEG.segment(DOC, profile="unreleased-v4"))
    finally:
        SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof
    assert sorted(on) == sorted(off)


def test_form_opener_closes_part_is_inert_with_no_part_open():
    doc = [b for b in DOC if b["id"] not in (1, 3)]
    prof = SEG.SEGMENTATION_PROFILES["unreleased-v4"]
    on = _paths(SEG.segment(doc, profile="unreleased-v4", structural_overrides=OPENERS))
    SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof - {RULE_FCP}
    try:
        off = _paths(SEG.segment(doc, profile="unreleased-v4", structural_overrides=OPENERS))
    finally:
        SEG.SEGMENTATION_PROFILES["unreleased-v4"] = prof
    assert sorted(on) == sorted(off)
