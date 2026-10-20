"""Agent K6's rules F `reviewed_hyphen_first_subsection` and G `reviewed_form_over_annex_part` (doc 4450, Sindh Civil
Servants Promotion (BPS-18 to BPS-21) Rules, 2022; F's variant for doc 4482 r.19: no stop or dash before "(1)").
Ported by builder BZ (group 24, 17 Oct 2026) from claude/agK6/test_k6_rules_fg_DRAFT.py. Pure: segment() over blocks."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, y=100.0, page=1):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


RULES = [
    _b(1, "1. Short title.- (1) These rules may be called the Test Rules, 2022.", 100),
    _b(2, "(2) They shall come into force at once.", 130),
    _b(3, "2. Definitions.-(1) In these rules, unless there is anything repugnant in the subject or context, the Act "
          "means the Test Act.", 160),
    _b(4, "(2) All other words shall have the meanings assigned to them in the Act.", 200),
    _b(5, "3. Panel of officers per vacancy.--(1) A panel of two officers per vacancy shall be submitted.", 240),
    _b(6, "(2) The panel shall include officers superseded before.", 280),
]


def _flat(seg):
    return {(n.kind, n.label, n.parent.label if n.parent is not None else None): n for n in seg.flatten()}


def test_f_opens_the_first_subsection_after_the_hyphen():
    seg = segment(RULES, structural_overrides={"source_hyphen_first_subsection_blocks": [3, 5]})
    nodes = _flat(seg)
    assert ("subsection", "1", "2") in nodes and ("subsection", "1", "3") in nodes
    assert nodes[("subsection", "1", "2")].text.startswith("In these rules")
    assert nodes[("subsection", "1", "3")].text.startswith("A panel of two officers")


def test_f_heading_without_stop_or_dash():
    blocks = [_b(21, "19. Establishment of Protection Committees (1) The Government shall establish Protection "
                     "Committees under Section 17 (1) of the Act.", 100),
              _b(22, "(2) The Members of the Protection Committee shall comprise of five members.", 140)]
    nodes = _flat(segment(blocks, structural_overrides={"source_hyphen_first_subsection_blocks": [21]}))
    assert ("subsection", "1", "19") in nodes
    assert nodes[("subsection", "1", "19")].text.startswith("The Government shall establish")


def test_f_inert_without_the_key():
    nodes = _flat(segment(RULES))
    assert ("subsection", "1", "2") not in nodes


def test_f_a_block_without_the_shape_fails_closed():
    with pytest.raises(ValueError):
        segment(RULES, structural_overrides={"source_hyphen_first_subsection_blocks": [2]})


def test_f_a_missing_block_fails_closed():
    with pytest.raises(ValueError):
        segment(RULES, structural_overrides={"source_hyphen_first_subsection_blocks": [99]})


SCHEDULE = [
    _b(11, "1. Short title.- (1) These rules may be called the Test Rules, 2022.", 100),
    _b(12, "SCHEDULE - VI", 200),
    _b(13, "[See rule 1]", 215),
    _b(14, "1) The departments shall submit their cases on the following forms, specimen of which are given at "
           "annexures :-", 240),
    _b(15, "(i)\nProposal form (CP-I)\nAnnexure-I\n(ii)\nPanel form (CP-II)\nAnnexure-II", 270),
    _b(16, "2) The departments shall ensure that the documents are complete.", 330),
]


def _parts(seg):
    return [n.label for n in seg.flatten() if n.kind == "part"]


def test_g_a_form_text_block_opens_no_annex_part():
    seg = segment(SCHEDULE, profile="unreleased-v4",
                  structural_overrides={"source_form_text_blocks": [15]})
    assert not any(str(p).startswith("Annexure") for p in _parts(seg))


def test_g_inert_without_the_key():
    seg = segment(SCHEDULE, profile="unreleased-v4")
    assert any(str(p).startswith("Annexure") for p in _parts(seg))


def test_f_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    key = "source_hyphen_first_subsection_blocks"
    assert key in STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS
    assert not any(name in rules for rules in SEGMENTATION_PROFILES.values()
                   for name in ("reviewed_hyphen_first_subsection", "reviewed_form_over_annex_part"))
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {key: [12, 10]}}},
        {"evidence": {"structural_overrides": {key: [11]}}}])
    assert sorted(merged[key]) == [10, 11, 12]
    with pytest.raises(ValueError, match=key):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: ["x"]}}}])
