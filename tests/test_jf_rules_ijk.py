"""Agent JF's rules for doc 4184 (Punjab Development Authorities Private
Housing Schemes Rules 2021), prototypes in claude/agJF/agJF-rule4184.py:
  I `reviewed_order_suffix_form` -- a reviewed source_order_suffix_labels group of kind 'form' (owner export m q1
    'keep-both': Form-B printed twice, pp34-35);
  J `form_code_opener_over_margin_heading` -- a block a reviewed source_form_code_openers entry names is never a
    margin heading (p56 'Form-H');
  K `reviewed_dash_first_subsection` -- agent K6's rule F admits an en / em dash before '(1)' (r.26 p20).
Pure: segment() over hand-made blocks shaped like doc 4184's pages. Ported as segmenter group 31
(17 Oct 2026; from claude/agJF/test_jf_rules_ijk_DRAFT.py 1993ede6)."""
import pytest

from nizam.corpus.segment import assign_paths, segment
from nizam.workers.segment import order_suffix_label_shape_ok

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-16-m.json", "document_id": 4184,
         "question_id": "q1"}


def _b(i, text, page=1, y=100.0, x=72.0, x1=560.0):
    return {"id": i, "page_no": page, "y0": y, "page_height": 842.0, "x0": x, "x1": x1, "text": text}


# ---------------------------------------------------------------- rule I
FORMS = [
    _b(1, "1. \nShort title.- These rules may be cited as the Test Housing Schemes Rules 2021. \n", y=80.0),
    _b(2, "2. \nForms.- The forms are as set out after these rules. \n", y=120.0),
    _b(10, "FORM A \n(rule 23) \nPUBLIC NOTICE \nThe public is hereby informed that ____ has applied. \n", page=2),
    _b(20, "FORM B \n(rule 24) \nTRANSFER DEED \nThis TRANSFER DEED made at ____ on the ____ day of ____. \n", page=3),
    _b(30, "FORM B \n(rule 24) \nTRANSFER DEED \nThis TRANSFER DEED made at ____ on the ____  day of ____. \n", page=4),
    _b(40, "FORM C \n(rule 24) \nMORTGAGE DEED \nTHIS MORTGAGE DEED is made at ____. \n", page=5),
]
SPEC = {"kind": "form", "label": "FORM B", "source_block_ids": [20, 30], "owner_decision": OWNER}


def _forms(seg):
    return [n for n in seg.flatten() if n.kind == "form"]


def test_rule_i_keeps_both_form_prints_cited_by_order():
    seg = segment(FORMS, structural_overrides={"source_order_suffix_labels": [SPEC]})
    b = [n for n in _forms(seg) if n.label.replace(" ", "") == "FORMB"]
    assert [n.first_block for n in b] == [20, 30]
    assert [n.print_occurrence for n in b] == [1, 2]
    paths = {n.first_block: p for n, p in assign_paths(seg, "x") if n.kind == "form"}
    assert paths[30].endswith("__o2") and not paths[20].endswith("__o2")
    assert paths[30][:-len("__o2")] == paths[20]


def test_rule_i_inert_without_a_form_group():
    seg = segment(FORMS)
    b = [n for n in _forms(seg) if n.label.replace(" ", "") == "FORMB"]
    assert len(b) == 2 and all(n.print_occurrence is None for n in b)


def test_rule_i_a_form_group_naming_other_prints_fails_closed():
    with pytest.raises(ValueError):
        segment(FORMS, structural_overrides={"source_order_suffix_labels": [dict(SPEC, source_block_ids=[20, 40])]})


def test_rule_i_a_form_group_without_owner_decision_fails_closed():
    with pytest.raises(ValueError):
        segment(FORMS, structural_overrides={"source_order_suffix_labels": [dict(SPEC, owner_decision={})]})


def test_rule_i_worker_admits_kind_form():
    assert order_suffix_label_shape_ok(SPEC)
    assert not order_suffix_label_shape_ok(dict(SPEC, kind="schedule"))


# ---------------------------------------------------------------- rule J
# A two-column check list: the page's long lines end at x1 300, so the boxed code at x0 472 lies beyond the text edge
# and repeats contents row 'Form-H' -- profile rule margin_heading_blocks (v2+) takes it for a margin heading.
HEADS = ["Short title", "Definitions", "Application", "Processing", "Public notice", "Forms"]
CONTENTS = ([_b(100, "THE TEST HOUSING SCHEMES RULES 2021 \n", y=40.0, x=90.0), _b(101, "CONTENTS \n", y=60.0, x=246.0)]
            + [_b(110 + k, f"{k + 1}. \n{h} \n", y=90.0 + 22 * k) for k, h in enumerate(HEADS)]
            + [_b(120, "FORMS \n", y=240.0, x=276.0), _b(121, "1. \nForm-G \n", y=262.0),
               _b(122, "2. \nForm-H \n", y=284.0)])
BODY = (
    [_b(1 + k, f"{k + 1}. \n{h}.- These rules provide for the {h.lower()} of a housing scheme under the Act. \n",
        page=2, y=80.0 + 40 * k) for k, h in enumerate(HEADS)]
    + [_b(10, "Form-G \n", page=3, y=73.0, x=383.0, x1=430.0),
       _b(11, "NUMBERING OF PLOTS AND ROADS \nA particular plot in a street shall be given a unique number. \n",
          page=3, y=100.0),
       _b(20, "Form-H \n", page=4, y=73.0, x=472.0, x1=520.0),
       _b(21, "CHECK LIST FOR SANCTION OF A SCHEME \n", page=4, y=130.0, x=168.0, x1=440.0),
       _b(22, "A-DOCUMENTS REQUIRED \nCertified copy of national Identity card of developer and of the sponsor; \n",
          page=4, y=158.0, x=65.0, x1=300.0),
       _b(23, "Certified title documents including a registry, mutation, fard malkiat, or any other document \n",
          page=4, y=224.0, x=65.0, x1=300.0),
       _b(24, "Khasra plan or aks-e-shajra certified by the revenue officer of the district concerned \n",
          page=4, y=270.0, x=65.0, x1=300.0)])
OPENERS = [{"source_block_id": 10, "label": "FORM G", "label_block_id": 10, "printed": "Form-G"},
           {"source_block_id": 20, "label": "FORM H", "label_block_id": 20, "printed": "Form-H"}]


def test_rule_j_a_reviewed_form_code_is_not_a_margin_heading():
    seg = segment(CONTENTS + BODY, structural_overrides={"source_form_code_openers": OPENERS},
                  profile="unreleased-v4")
    forms = {n.label: n for n in _forms(seg)}
    assert set(forms) >= {"FORM G", "FORM H"}
    assert forms["FORM H"].first_block == 20
    assert "CHECK LIST" not in " ".join(n.text or "" for n in [forms["FORM G"]] + list(forms["FORM G"].children))


def test_rule_j_without_a_reviewed_opener_the_margin_heading_stands():
    seg = segment(CONTENTS + BODY, profile="unreleased-v4")
    assert seg.block_roles.get(20, (None,))[0] == "heading"
    assert not any(n.first_block == 20 for n in _forms(seg))


# ---------------------------------------------------------------- rule K
R26 = [
    _b(1, "25. \nProcessing of services design.- The sponsor shall submit the designs. \n", y=60.0),
    _b(2, "26. \nPre-requisites for sanctioning a housing scheme.– (1) The Authority shall \nissue the letter of "
          "final approval within ten days from the date on which the sponsor: \n", y=100.0),
    _b(3, "(a) \ndeposit the approval fee; \n", y=150.0, x=144.0),
    _b(4, "(b) \ndeposit the land use conversion fee, if applicable. \n", y=170.0, x=144.0),
    _b(5, "(2) \nThe Authority shall ensure that the mortgage deed is executed. \n", y=200.0),
    _b(6, "(3) \nThe sponsor shall submit No Objection Certificate. \n", y=230.0),
]


def _s26(seg):
    return next(n for n in seg.flatten() if n.kind == "section" and n.label == "26")


def test_rule_k_en_dash_first_subsection_opens():
    s26 = _s26(segment(R26, structural_overrides={"source_hyphen_first_subsection_blocks": [2]}))
    subs = [c for c in s26.children if c.kind == "subsection"]
    assert [c.label for c in subs] == ["1", "2", "3"]
    assert (subs[0].text or "").startswith("The Authority shall")
    assert [c.label for c in subs[0].children if c.kind == "clause"] == ["a", "b"]


def test_rule_k_inert_without_the_key():
    s26 = _s26(segment(R26))
    assert "1" not in [c.label for c in s26.children if c.kind == "subsection"]


def test_rule_k_em_dash_too():
    blocks = [dict(b) for b in R26]
    blocks[1]["text"] = blocks[1]["text"].replace("–", "—")
    s26 = _s26(segment(blocks, structural_overrides={"source_hyphen_first_subsection_blocks": [2]}))
    assert [c.label for c in s26.children if c.kind == "subsection"][:1] == ["1"]


def test_rule_k_hyphen_unchanged():
    blocks = [dict(b) for b in R26]
    blocks[1]["text"] = blocks[1]["text"].replace("– ", "-")
    s26 = _s26(segment(blocks, structural_overrides={"source_hyphen_first_subsection_blocks": [2]}))
    assert [c.label for c in s26.children if c.kind == "subsection"][:1] == ["1"]
