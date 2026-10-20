"""Agent JF's rule A `reviewed_long_romanette_cut` (doc 3533 p31, s.80(2)(xxv); key source_long_romanette_cut_blocks).
Ported by builder BZ (group 26, 17 Oct 2026) from claude/agJF/test_jf_rule_a_DRAFT.py; key-gated only (needs the v4
rule long_romanettes). Pure: segment() over hand-made blocks shaped like doc 3533's s.80(2)."""
import pytest

from nizam.corpus.segment import segment

ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi",
         "xvii", "xviii", "xix", "xx", "xxi", "xxii", "xxiii"]


def _blocks():
    out = [{"id": 1, "page_no": 1, "y0": 60.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
            "text": "80. Power to make regulations.- (1) The Governing Body may make regulations.\n"},
           {"id": 2, "page_no": 1, "y0": 80.0, "page_height": 792.0, "x0": 70.0, "x1": 560.0,
            "text": "(2) In particular, such regulations may provide for all or any of the following matters, namely:-\n"}]
    y = 100.0
    for n, r in enumerate(ROMAN):
        out.append({"id": 10 + n, "page_no": 1, "y0": y, "page_height": 792.0, "x0": 110.0, "x1": 560.0,
                    "text": f"({r}) the matter numbered {r} in this list; \n"})
        y += 12.0
    out += [{"id": 50, "page_no": 2, "y0": 60.0, "page_height": 792.0, "x0": 110.0, "x1": 560.0,
             "text": "(xxiv) determination, for the purpose of repayment to the Institution, of the value of \n"},
            {"id": 51, "page_no": 2, "y0": 80.0, "page_height": 792.0, "x0": 110.0, "x1": 560.0,
             "text": "any benefit received otherwise than in cash; \n \n(xxv)   determination of the actuarial present "
                     "value of any periodical payment for \n"},
            {"id": 52, "page_no": 2, "y0": 100.0, "page_height": 792.0, "x0": 110.0, "x1": 560.0,
             "text": "which the Institution becomes liable; \n \n(xxvi) the manner in which disputes shall be decided.\n"}]
    return out


def _clauses(seg):
    return {n.label: n for n in seg.flatten() if n.kind == "clause"}


def test_reviewed_block_opens_xxv_as_its_own_clause():
    seg = segment(_blocks(), structural_overrides={"source_long_romanette_cut_blocks": [51]}, profile="unreleased-v4")
    cl = _clauses(seg)
    assert "xxv" in cl
    assert (cl["xxv"].text or "").startswith("determination of the actuarial present value")
    assert "actuarial" not in (cl["xxiv"].text or "")
    assert (cl["xxiv"].text or "").rstrip().endswith("otherwise than in cash;")
    assert cl["xxv"].parent is cl["xxiv"].parent


def test_inert_without_the_key():
    cl = _clauses(segment(_blocks(), profile="unreleased-v4"))
    assert "xxv" not in cl
    assert "(xxv)" in (cl["xxiv"].text or "")


def test_a_block_without_such_a_line_fails_closed():
    with pytest.raises(ValueError):
        segment(_blocks(), structural_overrides={"source_long_romanette_cut_blocks": [50]}, profile="unreleased-v4")


def test_a_missing_block_fails_closed():
    with pytest.raises(ValueError):
        segment(_blocks(), structural_overrides={"source_long_romanette_cut_blocks": [999]}, profile="unreleased-v4")


def test_needs_long_romanettes():
    with pytest.raises(ValueError):
        segment(_blocks(), structural_overrides={"source_long_romanette_cut_blocks": [51]})


def test_the_key_is_wired_through_worker_recorder_and_materializer():
    import pytest as _pt
    import nizam.workers.segment as W
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    key = "source_long_romanette_cut_blocks"
    assert key in STRUCTURAL_KEYS and key in STRUCTURAL_PATCH_KEYS and key in W.DF_BLOCK_KEYS
    assert not any("reviewed_long_romanette_cut" in rules for rules in SEGMENTATION_PROFILES.values())
    merged = W.reviewed_structural_overrides([], [
        {"evidence": {"structural_overrides": {key: [9]}}}, {"evidence": {"structural_overrides": {key: [3, 9]}}}])
    assert sorted(merged[key]) == [3, 9]
    with _pt.raises(ValueError):
        W.reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: ["x"]}}}])
