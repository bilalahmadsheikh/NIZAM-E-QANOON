"""Agent JF's rules B `bare_half_paren_subrule_reviewed_default` and C `form_code_opener_reviewed_default` (doc 3949, a
copy whose two released expressions keep it on the default profile). Ported by builder BZ (group 27, 17 Oct 2026) from
claude/agJF/test_jf_rules_bc_DRAFT.py. Pure: segment() over hand-made blocks shaped like doc 3949 pp16 and 31, under
the DEFAULT profile."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, page=1, y=100.0):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 72.0, "x1": 560.0, "text": text}


RULES = [
    _b(1, "1. \nShort title \n", y=60.0),
    _b(2, "These rules may be called the Service Rules 2006. \n", y=80.0),
    _b(3, "2. \nSeniority \n", y=100.0),
    _b(4, "1) \nSeniority of the employees shall be determined as per rules applicable to civil servants. \n", y=120.0),
    _b(5, "2) \nConduct of the employees shall be governed by the Conduct Rules. \n", y=140.0),
    _b(6, "3. \nTransfer \n", y=160.0),
    _b(7, "The Foundation can transfer its employees to any of its offices. \n", y=180.0),
]


def _subs(seg, section):
    sec = next(n for n in seg.flatten() if n.kind == "section" and n.label == section)
    return {c.label: c for c in sec.children if c.kind == "subsection"}


def test_rule_b_opens_bare_half_paren_subrules_in_the_default_profile():
    seg = segment(RULES, structural_overrides={"source_bare_half_paren_subrule_blocks": [4, 5]})
    subs = _subs(seg, "2")
    assert set(subs) == {"1", "2"}
    assert (subs["1"].text or "").startswith("Seniority of the employees")
    assert (subs["2"].text or "").startswith("Conduct of the employees")


def test_rule_b_inert_without_the_key():
    assert _subs(segment(RULES), "2") == {}


def test_rule_b_a_block_that_opens_no_subrule_fails_closed():
    with pytest.raises(ValueError):
        segment(RULES, structural_overrides={"source_bare_half_paren_subrule_blocks": [7]})


FORM = RULES + [
    _b(20, "SR-I (Expense Account) Punjab Education Foundation \n", page=2, y=60.0),
    _b(21, "EXPENSE ACCOUNT \n", page=2, y=80.0),
    _b(22, "Employee Name ........ Designation ........ Job No. \n", page=2, y=100.0),
]
SPEC = {"source_block_id": 20, "label": "SR-I", "label_block_id": 20,
        "printed": "SR-I (Expense Account) Punjab Education Foundation"}


def test_rule_c_opens_the_form_code_in_the_default_profile():
    seg = segment(FORM, structural_overrides={"source_form_code_openers": [SPEC]})
    forms = [n for n in seg.flatten() if n.kind == "form"]
    assert [f.label for f in forms] == ["SR-I"]
    assert "EXPENSE ACCOUNT" in (forms[0].text or "")
    assert "EXPENSE ACCOUNT" not in (next(n for n in seg.flatten() if n.kind == "section" and n.label == "3").text or "")


def test_rule_c_inert_without_the_key():
    assert not [n for n in segment(FORM).flatten() if n.kind == "form"]


def test_rule_c_a_label_the_block_does_not_print_fails_closed():
    with pytest.raises(ValueError):
        segment(FORM, structural_overrides={"source_form_code_openers": [dict(SPEC, printed="SR-II Leave")]})
