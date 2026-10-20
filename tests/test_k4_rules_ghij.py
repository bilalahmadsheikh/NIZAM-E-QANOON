"""Agent K4's prototype rules G-J (doc 4137, PESSI (Pension) Regulations, 2003).

G `chapter_colon_label`        -- 'CHAPTER: VII' opens Chapter VII (profile rule, no key).
H `reviewed_half_paren_roman`  -- key source_half_paren_roman_blocks: 'ii) / text' is clause ii.
I `reviewed_form_code_opener`  -- key source_form_code_openers: a form printing only its code ('SS-I(Pen)').
J `reviewed_bare_half_paren_subrule` -- key source_bare_half_paren_subrule_blocks: '3) / text', '6)The ...' is
  sub-section N and '(B) ...' clause B (agent K2's live `reviewed_half_paren_subrules` wants 'N) ' and text on the
  same line, and reads no capital group).

Ported by builder BZ (group 17 G-M, 16 Oct; group 20 O-V, 16 Oct 2026) from claude/agK4/tools/test_k4_rules_ghij_DRAFT.py.
"""
import pytest

from nizam.corpus import segment as S


def _b(i, text, y0, page=1, x0=72.0, x1=480.0):
    return {"id": i, "text": text, "page_no": page, "x0": x0, "x1": x1, "y0": y0, "page_height": 842.0}


def _kinds(seg):
    return [(n.kind, n.label) for n in seg.flatten()]


# ---- G ------------------------------------------------------------------------------------------------------------
def _chapters():
    return [_b(1, "CHAPTER-VI \n", 40.0), _b(2, "ANTICIPATORY PENSION \n", 60.0),
            _b(3, "6.1 \nWhen an employee is likely to retire, action shall be taken. \n", 80.0),
            _b(4, "CHAPTER: VII \n", 120.0), _b(5, "COMMUTATION OF PENSION \n", 140.0),
            _b(6, "7.1 \nAn employee may request for commutation of his pension. \n", 160.0),
            _b(7, "CHAPTER:VIII \n", 200.0), _b(8, "EXTRA-ORDINARY PENSION: \n", 220.0),
            _b(9, "8.1 \nWhere an employee is injured on duty, a pension may be granted. \n", 240.0)]


def test_G_colon_chapters_open():
    got = _kinds(S.segment(_chapters(), profile="unreleased-v4"))
    assert ("chapter", "VII") in got and ("chapter", "VIII") in got


def test_G_off_in_an_older_profile():
    got = _kinds(S.segment(_chapters(), profile="unreleased-v3"))
    assert ("chapter", "VII") not in got


def test_G_a_prose_reference_is_no_chapter():
    blocks = [_b(1, "1. \nThe provisions of CHAPTER: VII of the Act shall apply. \n", 40.0)]
    assert ("chapter", "VII") not in _kinds(S.segment(blocks, profile="unreleased-v4"))


# ---- H ------------------------------------------------------------------------------------------------------------
def _romans():
    return [_b(1, "1.4 \nDEFINITIONS: In these Regulations, \n", 40.0),
            _b(2, "e) \n'Emoluments' means pay and shall include: \n", 60.0, x0=126.0),
            _b(3, "i) \nBasic pay \n", 80.0, x0=162.0), _b(4, "ii) \nSenior post allowance \n", 100.0, x0=162.0),
            _b(5, "iii) \nSpecial pay of all types \n", 120.0, x0=162.0)]


def test_H_opens_half_paren_romanettes():
    seg = S.segment(_romans(), profile="unreleased-v4",
                    structural_overrides={"source_half_paren_clause_blocks": [2, 3],
                                          "source_half_paren_roman_blocks": [4, 5]})
    got = _kinds(seg)
    assert ("clause", "ii") in got and ("clause", "iii") in got
    ii = [n for n in seg.flatten() if n.kind == "clause" and n.label == "ii"][0]
    assert ii.text.startswith("Senior post allowance")


def test_H_inert_without_the_key():
    got = _kinds(S.segment(_romans(), profile="unreleased-v4",
                           structural_overrides={"source_half_paren_clause_blocks": [2, 3]}))
    assert ("clause", "ii") not in got


def test_H_refuses_a_block_without_a_romanette():
    with pytest.raises(ValueError):
        S.segment(_romans(), profile="unreleased-v4", structural_overrides={"source_half_paren_roman_blocks": [1]})


# ---- I ------------------------------------------------------------------------------------------------------------
def _forms():
    return [_b(1, "APPENDIX-D \n", 40.0), _b(2, "APPLICATION FOR COMMUTATION \nI, ______ desire to commute. \n", 60.0),
            _b(3, "Attested \n", 100.0),
            _b(4, "PUNJAB EMPLOYEES SOCIAL SECURITY INSTITUTION \n", 120.0),
            _b(5, "SS-I(Pen) \n", 140.0, x0=470.0), _b(6, "NO DEMAND CERTIFICATE \n", 160.0),
            _b(7, "This is certified that nothing is due against ______. \n", 180.0)]


def test_I_opens_the_coded_form_at_the_root():
    seg = S.segment(_forms(), profile="unreleased-v4",
                    structural_overrides={"source_form_code_openers": [
                        {"source_block_id": 4, "label": "SS-I(Pen)", "label_block_id": 5}]})
    form = [n for n in seg.flatten() if n.kind == "form" and n.label == "SS-I(Pen)"]
    assert form and form[0].depth == S.DEPTH["form"]


def test_I_refuses_a_label_the_block_does_not_print():
    with pytest.raises(ValueError):
        S.segment(_forms(), profile="unreleased-v4",
                  structural_overrides={"source_form_code_openers": [
                      {"source_block_id": 4, "label": "SS-II(Pen)", "label_block_id": 5}]})


def test_I_misprint_reading_names_the_printed_code():
    blocks = _forms()
    blocks[4] = _b(5, "S.S.1I(Pen) \n", 140.0, x0=470.0)
    seg = S.segment(blocks, profile="unreleased-v4",
                    structural_overrides={"source_form_code_openers": [
                        {"source_block_id": 4, "label": "S.S.II(Pen)", "label_block_id": 5, "printed": "S.S.1I(Pen)"}]})
    assert ("form", "S.S.II(Pen)") in _kinds(seg)


# ---- J ------------------------------------------------------------------------------------------------------------
def _subrules():
    return [_b(1, "4.6 \n(1) Family has the meaning in regulation 4.3. \n", 40.0),
            _b(2, "(2) A family pension shall be allowed as under: \n", 60.0, x0=126.0),
            _b(3, "(B) In the event of no pension being payable under clause (A), it may be granted; \n", 80.0,
               x0=126.0),
            _b(4, "3)  \nNo family pension shall be payable under this section. \n", 100.0, x0=90.0),
            _b(5, "6)The Institution has discretion to make modifications. \n", 120.0, x0=126.0)]


def test_J_opens_bare_half_paren_subrules_and_a_capital_group():
    seg = S.segment(_subrules(), profile="unreleased-v4",
                    structural_overrides={"source_bare_half_paren_subrule_blocks": [3, 4, 5]})
    got = _kinds(seg)
    assert ("subsection", "3") in got and ("subsection", "6") in got and ("clause", "B") in got


def test_J_inert_without_the_key():
    got = _kinds(S.segment(_subrules(), profile="unreleased-v4"))
    assert ("subsection", "6") not in got


def test_J_refuses_a_block_with_no_label():
    with pytest.raises(ValueError):
        S.segment(_subrules(), profile="unreleased-v4",
                  structural_overrides={"source_bare_half_paren_subrule_blocks": [1]})
