"""Agent JF's rules E `reviewed_decoded_quote_cut` (key source_decoded_quote_cut_blocks; doc 4497 E4 p86) and F
`marked_schedule_heading_reviewed` (existing key source_schedule_heading_blocks; doc 4497 E10 p255, E28 p888).
Ported by builder BZ (group 29, 17 Oct 2026) from claude/agJF/test_jf_rules_ef_DRAFT.py (c15efae0). Pure: segment()
over hand-made blocks shaped like doc 4497's pages, under the DEFAULT profile."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, page=1, y=100.0, x=72.0):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": x, "x1": 560.0, "text": text}


DEFS = [
    _b(1, " \n1. \nShort Title and Commencement-(1) These rules may be called the Test Rules, 2003. \n", y=60.0),
    _b(2, " \n2. \nDefinitions- In these rules unless there is anything repugnant in the subject or context:— \n",
       y=90.0),
    _b(3, "(i) \n―Government‖ means the Federal Government in Establishment Division. \n(ii) \n"
          "―Commission‖ means the Federal Public Service Commission. \n(iii) ―Examination‖ means "
          "the Final Passing Out Examination. \n", y=120.0, x=162.0),
    _b(4, " \n3. \nThe Commission shall conduct the examination. \n", y=200.0),
]


def _clauses(seg, section):
    sec = next(n for n in seg.flatten() if n.kind == "section" and n.label == section)
    return {c.label: c for c in sec.children if c.kind == "clause"}


def test_rule_e_cuts_decoded_quote_definitions_in_the_default_profile():
    cl = _clauses(segment(DEFS, structural_overrides={"source_decoded_quote_cut_blocks": [3]}), "2")
    assert set(cl) == {"i", "ii", "iii"}
    assert (cl["ii"].text or "").startswith("―Commission‖ means")
    assert "Commission" not in (cl["i"].text or "")


def test_rule_e_inert_without_the_key():
    cl = _clauses(segment(DEFS), "2")
    assert "ii" not in cl and "Commission" in (cl["i"].text or "")


def test_rule_e_a_block_without_such_a_line_fails_closed():
    with pytest.raises(ValueError):
        segment(DEFS, structural_overrides={"source_decoded_quote_cut_blocks": [4]})


def test_rule_e_a_missing_block_fails_closed():
    with pytest.raises(ValueError):
        segment(DEFS, structural_overrides={"source_decoded_quote_cut_blocks": [999]})


ORD = [
    _b(10, " \n10. \nRules.—The Federal Government may make rules for carrying out the purposes of this Ordinance. \n",
       y=60.0),
    _b(11, " 11. \n [Repeal]. \n", y=100.0),
    _b(12, "[SCHEDULE] \n     (See Section 4A) \n", y=130.0, x=266.0),
    _b(13, " \nI, ____________ do solemnly swear that I will bear true faith and allegiance to Pakistan. \n", y=160.0),
]


def _schedules(seg):
    return [n for n in seg.flatten() if n.kind == "schedule"]


def test_rule_f_opens_a_marked_schedule_heading():
    seg = segment(ORD, structural_overrides={"source_schedule_heading_blocks": [12]})
    sch = _schedules(seg)
    assert len(sch) == 1 and sch[0].label == "SCHEDULE"
    assert "solemnly swear" in " ".join((n.text or "") for n in [sch[0]] + list(sch[0].children))
    s11 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "11")
    assert "swear" not in (s11.text or "")


def test_rule_f_digit_marker_and_decoded_quote():
    blocks = ORD[:2] + [_b(12, "4[―THE SCHEDULE] \n", y=130.0, x=259.0),
                        _b(14, "[See section 10(b)] \n", y=150.0, x=268.0)] + ORD[3:]
    sch = _schedules(segment(blocks, structural_overrides={"source_schedule_heading_blocks": [12]}))
    assert len(sch) == 1 and sch[0].label == "SCHEDULE"


def test_rule_f_inert_without_the_key():
    assert _schedules(segment(ORD)) == []


def test_rule_f_a_block_that_is_no_schedule_heading_still_fails_closed():
    with pytest.raises(ValueError):
        segment(ORD, structural_overrides={"source_schedule_heading_blocks": [13]})


def test_rule_e_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, STRUCTURAL_KEYS
    key = "source_decoded_quote_cut_blocks"
    assert key in STRUCTURAL_KEYS and key in GENERIC_STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
    assert key in W.DF_BLOCK_KEYS
    assert not any(name in rules for rules in SEGMENTATION_PROFILES.values()
                   for name in ("reviewed_decoded_quote_cut", "marked_schedule_heading_reviewed"))
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {key: [9]}}}, {"evidence": {"structural_overrides": {key: [3, 9]}}}])
    assert sorted(merged[key]) == [3, 9]
    with pytest.raises(ValueError):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: ["x"]}}}])
