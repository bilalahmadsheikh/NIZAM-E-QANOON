"""Export j group 7 (15 Oct 2026, builder BZ): the reviewed keys of agent JD's rules T `reviewed_dotted_letter_item`
(source_dotted_letter_item_blocks) and J `schedule_paragraph_printed_heading` (source_schedule_paragraph_headings)
reach the segmenter through the worker merge, the recorder and the multi-instrument dry run. J's entries are keyed by
printed label and merged across readings (doc 3901 cites the key on five pages); two readings that disagree on one
label are refused, never resolved by order."""
import pytest

T, J = "source_dotted_letter_item_blocks", "source_schedule_paragraph_headings"
CITE = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 3901,
        "question_id": "q2"}


def _patch(i, **overrides):
    return {"id": f"p{i}", "page_no": i, "match_text": "x", "before_text": "x", "after_text": "x",
            "evidence": {"structural_overrides": overrides}}


def _heading(label, block, heading="Amendment of section 19."):
    return {"label": label, "source_block_id": block, "heading": heading, "owner_decision": CITE}


def test_both_keys_are_known_everywhere():
    from tools import materialize_multi_instrument as mat
    from tools import record_curation_patch as rcp
    for key in (T, J):
        assert key in rcp.STRUCTURAL_KEYS and key in rcp.GENERIC_STRUCTURAL_KEYS
        assert key in mat.STRUCTURAL_PATCH_KEYS
    assert set(mat.STRUCTURAL_PATCH_KEYS) == set(rcp.STRUCTURAL_KEYS)


def test_the_worker_merges_the_block_list_and_the_label_keyed_list():
    from nizam.workers.segment import reviewed_structural_overrides
    merged = reviewed_structural_overrides(None, [
        _patch(1, **{T: [11, 12]}), _patch(2, **{T: [12, 13]}),
        _patch(3, **{J: [_heading("8", 100)]}), _patch(4, **{J: [_heading("12", 101, "Further provision.")]})])
    assert merged[T] == [11, 12, 13]
    assert sorted(v["label"] for v in merged[J]) == ["12", "8"]


def test_the_worker_refuses_two_readings_that_disagree_on_one_label():
    from nizam.workers.segment import reviewed_structural_overrides
    with pytest.raises(ValueError, match="conflicting reviewed"):
        reviewed_structural_overrides(None, [_patch(1, **{J: [_heading("8", 100)]}),
                                             _patch(2, **{J: [_heading("8", 100, "Another heading.")]})])


@pytest.mark.parametrize("bad", [
    [{"label": "8", "source_block_id": 100, "heading": "H."}],                    # no owner decision
    [_heading("", 100)], [_heading("8", 0)], [_heading("8", 100, "  ")],
    [dict(_heading("8", 100), extra=1)], [], "8"])
def test_the_worker_refuses_a_malformed_heading_entry(bad):
    from nizam.workers.segment import reviewed_structural_overrides
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides(None, [_patch(1, **{J: bad})])


def test_the_recorder_checks_j_against_the_export():
    import pathlib
    from tools import record_curation_patch as rcp
    src = pathlib.Path(rcp.__file__).read_text(encoding="utf-8")
    branch = src[src.index('jd_sph = r.get("source_schedule_paragraph_headings")'):src.index("generic = {k: r.get(k)")]
    assert "owner_decision_answer(v[\"owner_decision\"], doc)" in branch and "refused.append" in branch


# --- export j/l group 8 (15 Oct 2026): agent JD's O `owner_supplied_schedule_part`, and the choice 'cite-115A' -------
OSP = "source_owner_schedule_parts"
CITE_4324 = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 4324,
             "question_id": "q2"}


def _part(first, label="ONE", evidence=677686):
    return {"first_block_id": first, "label": label, "evidence_block_id": evidence, "owner_decision": CITE_4324}


def test_group8_key_is_known_everywhere_and_merges_by_first_block():
    from nizam.workers.segment import reviewed_structural_overrides
    from tools import materialize_multi_instrument as mat
    from tools import record_curation_patch as rcp
    assert OSP in rcp.STRUCTURAL_KEYS and OSP in rcp.GENERIC_STRUCTURAL_KEYS and OSP in mat.STRUCTURAL_PATCH_KEYS
    merged = reviewed_structural_overrides(None, [_patch(1, **{OSP: [_part(677706)]}),
                                                 _patch(2, **{OSP: [_part(677723, "TWO", 677687)]})])
    assert [v["first_block_id"] for v in merged[OSP]] == [677706, 677723]
    with pytest.raises(ValueError, match="conflicting reviewed"):
        reviewed_structural_overrides(None, [_patch(1, **{OSP: [_part(677706)]}),
                                             _patch(2, **{OSP: [_part(677706, "TWO")]})])
    with pytest.raises(ValueError, match="unsupported curation structural override"):
        reviewed_structural_overrides(None, [_patch(1, **{OSP: [dict(_part(677706), heading="x")]})])


def test_group8_recorder_checks_o_against_the_export_and_cite_115a_is_admitted():
    import pathlib
    from nizam.workers.segment import OWNER_CITED_LABEL_CHOICES
    from tools import record_curation_patch as rcp
    src = pathlib.Path(rcp.__file__).read_text(encoding="utf-8")
    branch = src[src.index('jd_osp = r.get("source_owner_schedule_parts")'):src.index("generic = {k: r.get(k)")]
    assert "owner_decision_answer(v[\"owner_decision\"], doc)" in branch and "refused.append" in branch
    assert {"cite-47A", "cite-115A"} <= OWNER_CITED_LABEL_CHOICES
