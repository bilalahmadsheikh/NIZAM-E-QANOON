from tools.second_parser_release import (
    TARGET_SQL,
    _released_target_replacements,
    _match_secondary,
    _matched_role,
    _overlap,
    _role,
    _s7_resolution,
)
from nizam.workers.segment import reviewed_structural_overrides
from nizam.corpus.segment import segment


def test_target_query_is_live_canonical_and_unreleased_only():
    compact = " ".join(TARGET_SQL.split()).lower()
    assert "i.is_active" in compact
    assert "i.duplicate_of is null" in compact
    assert "not exists (select 1 from v_release_instrument" in compact


def test_verify_accepts_only_an_exact_released_uuid_replacement():
    target = {
        "instrument_id": "old", "document_id": 1000,
        "source_observation_id": 2317, "expression_ordinal": 0,
        "source_sha256": "abc",
    }
    expected = {"old": target}
    release_rows = [{**target, "instrument_id": "new"}]
    already, replacements, accounted, release_ids = (
        _released_target_replacements(
            expected, {}, {"new": "fingerprint"}, release_rows))
    assert already == []
    assert replacements == [{
        "snapshot_instrument_id": "old",
        "released_instrument_id": "new",
        "document_id": 1000,
        "source_observation_id": 2317,
        "expression_ordinal": 0,
    }]
    assert accounted == {"old"}
    assert release_ids == {"new"}

    release_rows[0]["source_sha256"] = "different"
    _, replacements, accounted, release_ids = _released_target_replacements(
        expected, {}, {"new": "fingerprint"}, release_rows)
    assert replacements == []
    assert accounted == set()
    assert release_ids == set()


def test_overlap_uses_the_smaller_region_as_the_mapping_floor():
    assert _overlap([0, 0, 100, 100], [10, 10, 20, 20]) == 1.0
    assert _overlap([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0


def test_surya_role_can_reject_apparatus_but_ambiguity_stays_review():
    assert _role("Footnote") == "apparatus"
    assert _role("SectionHeader") == "body"
    assert _s7_resolution("apparatus", "body") == "reject_candidate"
    assert _s7_resolution("body", "apparatus") == "restore_citable"
    assert _s7_resolution("body", "contents") == "restore_citable"
    assert _s7_resolution("unknown", "body") == "review"


def test_mapping_needs_geometry_or_independent_text_agreement():
    source = {"x0": 10, "y0": 20, "x1": 110, "y1": 50,
              "text": "12. Appointment of inspectors"}
    candidates = [{"bbox": [10, 20, 110, 50],
                   "text": "12. Appointment of inspectors",
                   "label": "SectionHeader"}]
    match = _match_secondary(source, candidates)
    assert match is not None
    assert match["geometry"] == 1.0
    assert match["block"]["label"] == "SectionHeader"


def test_mapping_refuses_an_unrelated_region():
    source = {"x0": 10, "y0": 20, "x1": 110, "y1": 50,
              "text": "12. Appointment of inspectors"}
    candidates = [{"bbox": [300, 500, 400, 530],
                   "text": "Government notification",
                   "label": "Text"}]
    assert _match_secondary(source, candidates) is None


def test_text_below_a_contents_header_is_not_body_text():
    page = [
        {"reading_order": 0, "label": "SectionHeader", "text": "CONTENTS"},
        {"reading_order": 1, "label": "Text", "text": "12.1"},
    ]
    match = {"block": page[1], "score": 1.0, "geometry": 1.0,
             "text_similarity": 1.0}
    assert _matched_role(match, page) == "contents"


def test_reviewed_overrides_merge_and_conflicts_fail_closed():
    rows = [
        {"evidence": {"structural_overrides": {
            "source_body_start_block": 20}}},
        {"evidence": {"structural_overrides": {
            "source_body_start_block": 20}}},
    ]
    assert reviewed_structural_overrides(rows) == {
        "source_body_start_block": 20}
    rows[1]["evidence"]["structural_overrides"]["source_body_start_block"] = 21
    try:
        reviewed_structural_overrides(rows)
    except ValueError as exc:
        assert "conflicting reviewed structural override" in str(exc)
    else:
        raise AssertionError("conflicting reviewed overrides must fail closed")


def test_verified_curation_can_name_exact_body_boundary():
    patch = {"evidence": {"structural_overrides": {
        "source_body_start_block": 131636}}}
    assert reviewed_structural_overrides([], [patch]) == {
        "source_body_start_block": 131636}
    # A patch naming apparatus blocks is no longer unsupported: the project
    # owner authorised page-read apparatus on patches where no S7 collision
    # exists (26 Sep 2026; tests/test_patch_apparatus_override.py).
    for conflicting in (
        {"source_body_start_block": 131637},
        {"source_apparatus_blocks": []},
    ):
        try:
            reviewed_structural_overrides(
                [{"evidence": {"structural_overrides": {
                    "source_body_start_block": 131636}}}],
                [{"evidence": {"structural_overrides": conflicting}}],
            )
        except ValueError:
            pass
        else:
            raise AssertionError("unsupported/conflicting curation must fail")


def test_verified_curation_can_reparent_exact_source_blocks_without_s7_case():
    specification = [{
        "source_block_id": 28226, "parent_block_id": 28225,
        "kind": "clause"}, {
        "source_block_id": 28227, "parent_block_id": 28225,
        "kind": "clause"}]
    patch = {"evidence": {"structural_overrides": {
        "source_reparent_blocks": specification}}}
    assert reviewed_structural_overrides([], [patch]) == {
        "source_reparent_blocks": specification}
    for invalid in ([{"source_block_id": 0, "parent_block_id": 28225,
                     "kind": "clause"}],
                    [{"source_block_id": 28226, "parent_block_id": 28225,
                      "kind": "section"}], []):
        try:
            reviewed_structural_overrides([], [{"evidence": {
                "structural_overrides": {"source_reparent_blocks": invalid}}}])
        except ValueError:
            pass
        else:
            raise AssertionError("invalid reparent curation must fail closed")


def test_verified_curation_can_group_exact_schedule_form_blocks():
    spec = {"schedule_block_id": 301355, "schedule_label": "SECOND SCHEDULE",
            "first_form_block_id": 301354, "first_form_label": "FORM A",
            "second_form_block_id": 301375, "second_form_label": "FORM B"}
    patch = {"evidence": {"structural_overrides": {
        "source_schedule_form_group": spec}}}
    assert reviewed_structural_overrides([], [patch]) == {
        "source_schedule_form_group": spec}
    for invalid in ({**spec, "first_form_block_id": 0},
                    {**spec, "second_form_block_id": 301355},
                    {**spec, "unreviewed_field": True}):
        try:
            reviewed_structural_overrides([], [{"evidence": {
                "structural_overrides": {"source_schedule_form_group": invalid}}}])
        except ValueError:
            pass
        else:
            raise AssertionError("malformed schedule/form group must fail closed")


def test_disjoint_reviewed_reparents_merge_but_conflicts_fail_closed():
    first = {"source_block_id": 301244, "source_label": "i",
             "parent_block_id": 301243, "parent_label": "m", "kind": "clause"}
    second = {"source_block_id": 301310, "source_label": "Explanation",
              "source_kind": "explanation", "parent_block_id": 301302,
              "parent_label": "34", "kind": "explanation"}
    patch = lambda value: {"evidence": {"structural_overrides": {
        "source_reparent_blocks": [value]}}}
    assert reviewed_structural_overrides([], [patch(first), patch(second)]) == {
        "source_reparent_blocks": [first, second]}
    assert reviewed_structural_overrides([], [patch(first), patch(first)]) == {
        "source_reparent_blocks": [first]}
    try:
        reviewed_structural_overrides([], [
            patch(first), patch({**first, "parent_block_id": 301302})])
    except ValueError:
        pass
    else:
        raise AssertionError("contradictory source parentage must fail closed")


def test_source_body_start_keeps_a_one_row_contents_page_out_of_the_tree():
    texts = [
        "THE EXAMPLE ORDERS", "CONTENTS", "12.1", "TEXT",
        "12.1. The Government shall prohibit the specified substance.",
        "12.2. The Government may regulate its import.",
    ]
    blocks = [
        {"id": index, "text": text, "page_no": 1 if index < 4 else 2,
         "y0": index * 40.0, "page_height": 800.0,
         "x0": 70.0, "x1": 500.0}
        for index, text in enumerate(texts, 1)
    ]
    parsed = segment(blocks, structural_overrides={
        "source_body_start_block": 4})
    sections = [node for node in parsed.flatten() if node.kind == "section"]
    assert [(node.label, node.first_block) for node in sections] == [
        ("12.1", 5), ("12.2", 6)]
    assert parsed.toc_found
    assert parsed.missing == []
    assert parsed.block_roles[3][0] == "contents"


def test_source_reviewed_apparatus_block_cannot_open_fake_sections():
    blocks = [
        {"id": 1, "text": "CONTENTS", "page_no": 1, "y0": 50,
         "page_height": 800, "x0": 70, "x1": 500},
        {"id": 2, "text": "1. The only section", "page_no": 1,
         "y0": 100, "page_height": 800, "x0": 70, "x1": 500},
        {"id": 3, "text": "THE EXAMPLE ACT", "page_no": 2, "y0": 50,
         "page_height": 800, "x0": 70, "x1": 500},
        {"id": 4, "text": "1. The only section. It shall apply.",
         "page_no": 2, "y0": 150, "page_height": 800,
         "x0": 70, "x1": 500},
        {"id": 5, "text": "1Short title note, s. 3, p. 672.",
         "page_no": 2, "y0": 700, "page_height": 800,
         "x0": 70, "x1": 500},
    ]
    parsed = segment(blocks, structural_overrides={
        "source_body_start_block": 3,
        "source_apparatus_blocks": [5],
    })
    sections = [node for node in parsed.flatten() if node.kind == "section"]
    assert [(node.label, node.first_block) for node in sections] == [("1", 4)]
    assert parsed.block_roles[5][0] == "footnote"


def test_source_reviewed_reparent_moves_and_retypes_exact_node():
    blocks = [
        {"id": 1, "text": "1. Short title. This Act applies.",
         "page_no": 1, "y0": 50, "page_height": 800, "x0": 70, "x1": 500},
        {"id": 2, "text": "2. For section 2, the following is substituted:",
         "page_no": 1, "y0": 100, "page_height": 800, "x0": 70, "x1": 500},
        {"id": 3, "text": "2. Levy. Tax shall be charged.",
         "page_no": 1, "y0": 150, "page_height": 800, "x0": 70, "x1": 500},
    ]
    parsed = segment(blocks, structural_overrides={
        "source_reparent_blocks": [{
            "source_block_id": 3,
            "parent_block_id": 2,
            "kind": "clause",
        }],
    })
    outer = next(node for node in parsed.flatten()
                 if node.first_block == 2)
    embedded = next(node for node in parsed.flatten()
                    if node.first_block == 3)
    assert embedded.parent is outer
    assert embedded.kind == "clause"
    assert embedded in outer.children
    assert parsed.block_roles[3][0] == "body"
    assert parsed.repeated_label_decisions[0]["settled_by_review"] == "reparent"
    assert parsed.structural_reviews_enacted == [{
        "resolution": "reparent",
        "source_block_id": 3,
        "parent_block_id": 2,
        "kind": "clause",
    }]
