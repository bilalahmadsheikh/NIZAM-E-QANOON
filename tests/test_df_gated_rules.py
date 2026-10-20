"""Agent DF's data-gated rules (stage 3, owner 11-12 Oct 2026; docs/SEGMENTATION-PROFILES.md).

Docs 4347 (Sindh Seed Corporation booklet) and 4451 (Customs Act) are released default-profile observations and
cannot be pinned, so each rule is honoured in every profile and is INERT unless a reviewed reading names the blocks:

  reviewed_decimal_cut         `source_decimal_cut_blocks`: a new line opening N.M[.K[.L]] before a capital, quote or
                               '(' starts a unit; so does a line 'N.' whose next line opens 'N.1'; a decimal unit of
                               such a block gets no first-sentence heading guess. Fails closed on a missing block.
  reviewed_table_row_blocks    `source_table_row_blocks`: a unit of the block read as a section is a row (clause).
  reviewed_division_continues  `source_division_continues_blocks`: the naming-formula exit ('1. These Rules may be
                               called ...') does not resume the body at the block.
  reviewed_marked_label_cut    `source_marked_label_cut_blocks`: a new line opening 'M[N. Mx[Capital' starts a unit.
"""
import pytest

from nizam.corpus.segment import segment
from nizam.workers.segment import DF_BLOCK_KEYS, reviewed_structural_overrides
from tests.test_annexure_instrument_body import NAMING, gazette_blocks


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1, "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


def units(B, overrides=None):
    return [(n.kind, n.label, n.heading or "", n.text or "")
            for n in segment(B, structural_overrides=overrides).flatten()]


DECIMAL = blocks("1. SHORT TITLE AND COMMENCEMENT.\n1.1 These Regulations shall be called the Test Regulations.\n"
                 "1.2 They shall apply to all employees.\n1.2.1 Officers on deputation.",
                 "2. DEFINITIONS.\n2.1 In these regulations the Board means the Board.\n"
                 "2.2 Joining time. The time allowed.")


def test_decimal_cut_only_in_reviewed_blocks():
    plain = units(DECIMAL)
    assert [label for _k, label, _h, _t in plain] == ["1", "2"]
    assert units(DECIMAL, {}) == plain
    cut = units(DECIMAL, {"source_decimal_cut_blocks": [100, 101]})
    assert [label for _k, label, _h, _t in cut] == ["1", "1.1", "1.2", "1.2.1", "2", "2.1", "2.2"]
    # a decimal sub-regulation of a reviewed block prints no heading: '2.2 Joining time.' is its text
    assert cut[-1] == ("section", "2.2", "", "Joining time. The time allowed.")
    with pytest.raises(ValueError, match="source_decimal_cut_blocks not found"):
        segment(DECIMAL, structural_overrides={"source_decimal_cut_blocks": [999]})


TABLE = blocks("3. CLASSIFICATION.\n3.1 The posts are classified as under:", "1. Senior Executives\n2. Junior Executives",
               "4. APPOINTMENT.\n4.1 Appointments shall be made by the Board.")


def test_table_rows_only_in_reviewed_blocks():
    assert [(k, label) for k, label, _h, _t in units(TABLE)] == [
        ("section", "3"), ("section", "1"), ("section", "2"), ("section", "4")]
    assert [(k, label) for k, label, _h, _t in units(TABLE, {"source_table_row_blocks": [101]})] == [
        ("section", "3"), ("clause", "1"), ("clause", "2"), ("section", "4")]


MARKED = blocks("24. Valuation rules. The Board may make rules.\n"
                "31[25. 31b[Value of imported and exported goods].- (1) Where a duty is chargeable.",
                "26. Power to require. The officer may.")


def test_marked_label_cut_only_in_reviewed_blocks():
    assert [label for _k, label, _h, _t in units(MARKED) if _k == "section"] == ["24", "26"]
    cut = units(MARKED, {"source_marked_label_cut_blocks": [100]})
    assert [label for k, label, _h, _t in cut if k == "section"] == ["24", "25", "26"]
    assert ("section", "24", "Valuation rules", "The Board may make rules.") in cut


def test_division_continues_only_at_reviewed_blocks():
    """The naming formula at label 1 resumes the body (doc 2754), except at a reviewed block (doc 4347 p64, the
    Provident Fund rules annexed to the deed stay in their annexure)."""
    source = gazette_blocks(NAMING)
    naming_block = next(b["id"] for b in source if b["text"] == NAMING)
    assert [n.label for n in segment(source).flatten() if n.kind == "section"] == ["1", "2", "3"]
    kept = segment(source, structural_overrides={"source_division_continues_blocks": [naming_block]})
    assert [n for n in kept.flatten() if n.kind == "section"] == []


def _patch(**overrides):
    return {"evidence": {"structural_overrides": overrides}}


@pytest.mark.parametrize("key", DF_BLOCK_KEYS)
def test_the_worker_unites_each_key_and_refuses_a_bad_list(key):
    merged = reviewed_structural_overrides([], [_patch(**{key: [12, 10]}), _patch(**{key: [11]})])
    assert merged[key] == [10, 11, 12]
    for bad in ([], ["x"], [3, 3], [0]):
        with pytest.raises(ValueError, match=key):
            reviewed_structural_overrides([], [_patch(**{key: bad})])
    assert key not in reviewed_structural_overrides([], [])


# ---- reviewed_marker_run_cut (doc 4451 pp38, 40; lead 12 Oct: text kept as printed, the cut only)
CUSTOMS = blocks("11. Power to declare warehousing stations.- The Board may declare places.\n"
                 "2,7[12.power to appoint or license public warehouses.-(1) At any warehousing station the "
                 "Collector may appoint.",
                 "15. Penalty.- Whoever contravenes shall be punished.")


def test_marker_run_cut_only_in_a_reviewed_block_text_kept_as_printed():
    plain = S_sections(CUSTOMS)
    assert ("12", "power to appoint or license public wareh") not in plain
    cut = S_sections(CUSTOMS, {"source_marker_run_cut_blocks": [100]})
    assert ("12", "power to appoint or license public wareh") in cut     # lower-case 'power' kept as printed
    assert S_sections(CUSTOMS, {}) == plain


def S_sections(b, overrides=None):
    return [(n.label, (n.text or "")[:40]) for n in segment(b, structural_overrides=overrides).flatten()
            if n.kind == "section"]


def test_the_marker_run_key_is_known_everywhere():
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    assert "source_marker_run_cut_blocks" in DF_BLOCK_KEYS
    assert "source_marker_run_cut_blocks" in STRUCTURAL_KEYS and "source_marker_run_cut_blocks" in STRUCTURAL_PATCH_KEYS


# ---- reviewed_half_paren_items (doc 4347 E6, PF Rules pp64-75; lead 12 Oct): data-gated port of the v4 rule
PF = blocks("15. ELIGIBILITY a) All employees shall be eligible to subscribe.\n"
            "b) i. The amount of subscription shall be fixed.\n"
            "ii. The balance shall be paid on retirement.\n"
            "c) No advance shall be paid.",
            "16. NOMINATION. Every subscriber shall make a nomination.")


def test_half_paren_items_only_in_a_reviewed_block():
    plain = [(n.kind, n.label) for n in segment(PF).flatten()]
    assert ("clause", "a") not in plain and ("clause", "ii") not in plain
    cut = [(n.kind, n.label) for n in segment(PF, structural_overrides={"source_half_paren_item_blocks": [100]}).flatten()]
    for unit in (("clause", "a"), ("clause", "b"), ("clause", "i"), ("clause", "ii"), ("clause", "c")):
        assert unit in cut, (unit, cut)
    assert ("section", "16") in cut
    assert [(n.kind, n.label) for n in segment(PF, structural_overrides={}).flatten()] == plain


def test_the_half_paren_key_is_known_everywhere():
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    assert "source_half_paren_item_blocks" in DF_BLOCK_KEYS
    assert "source_half_paren_item_blocks" in STRUCTURAL_KEYS and "source_half_paren_item_blocks" in STRUCTURAL_PATCH_KEYS


# ---- agent DF's 4347-split delta (v2): integer-serial table rows, group headings, inline tables (keys known)
def test_table_rows_are_integer_serials_only_and_group_headings_open_parts():
    rows = blocks("21. ENTITLEMENT.\n21.2.1 Officers shall be entitled as under:\n1. Senior Executives\n2. Junior Executives",
                  "22. LEAVE. Leave shall be granted.")
    cut = units(rows, {"source_table_row_blocks": [100], "source_decimal_cut_blocks": [100]})
    assert ("section", "21.2.1") in [(k, label) for k, label, _h, _t in cut]           # a decimal stays a section
    assert ("clause", "1") in [(k, label) for k, label, _h, _t in cut]
    groups = blocks("1. DELEGATION. The powers are delegated as under.",
                    "2. FINANCIAL POWERS.\n6. Sanction of expenditure up to Rs. 500.\n7. Write off of losses.",
                    "3. ADMINISTRATIVE POWERS.\n8. Grant of leave.")
    assert [(k, label) for k, label, _h, _t in units(groups)][1] == ("section", "2")
    on = [(k, label) for k, label, _h, _t in units(groups, {"source_group_heading_blocks": [101, 102]})]
    assert ("part", "2") in on and ("part", "3") in on and ("section", "6") in on


def test_the_split_keys_are_known_everywhere():
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    for key in ("source_inline_table_blocks", "source_group_heading_blocks"):
        assert key in DF_BLOCK_KEYS and key in STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
