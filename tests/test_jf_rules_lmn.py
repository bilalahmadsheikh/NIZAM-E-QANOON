"""Source-backed 3912 regressions: reviewed captions, form recitals, note-marked appendix.

Evidence: claude/agJF/doc-3912-DRAFT.json and patch-3912.json in the release
work artifacts. Source pages 2, 20, 21, 27, 43; owner export m q1 'body'.
Only named, source-reviewed blocks activate these rules.
"""
import pytest

from nizam.corpus.segment import segment


def b(i, text, page=2, y=100):
    return dict(id=i, text=text, page_no=page, y0=y, x0=72, x1=560, page_height=842)


@pytest.mark.parametrize("profile", ["default", "unreleased-v4"])
def test_reviewed_sentence_case_caption_parents_decimal_rules_and_ends_at_appendix(profile):
    blocks = [b(518181, "1.\nGeneral.–\n"),
              b(518182, "2.1 (a) These rules may be called the Punjab Contributory Provident Fund Rules, 1978.\n"),
              b(518199, "2.\nConstitution and Management of the Fund.\n", page=3),
              b(518200, "2.3 The Fund shall be administered by Government and shall be maintained in rupees in Pakistan.\n", page=3),
              b(518526, "APPENDIX-I\n", page=21)]
    overrides = {"source_group_heading_blocks": [518181, 518199]}
    seg = segment(blocks, profile=profile, structural_overrides=overrides)
    groups = {n.label: n for n in seg.flatten() if n.kind == "part"}
    assert set(groups) == {"1", "2"}
    rule = next(n for n in seg.flatten() if n.kind == "section" and n.label == "2.3")
    assert rule.parent is groups["2"]
    assert "rupees in Pakistan" in rule.text
    appendix = next(n for n in seg.flatten() if n.kind == "appendix")
    assert appendix.parent is groups["2"].parent
    assert rule.first_block == 518200


def test_sentence_case_caption_inert_without_review():
    blocks = [b(1, "1.\nGeneral.–\n"), b(2, "2.3 The Fund shall be administered by Government.\n")]
    assert not any(n.kind == "part" for n in segment(blocks).flatten())


def test_caption_review_does_not_swallow_operative_multiline_unit():
    blocks = [b(1, "1.\nGeneral.–\nThe Fund shall be administered by Government.\n")]
    seg = segment(blocks, structural_overrides={"source_group_heading_blocks": [1]})
    assert not any(n.kind == "part" for n in seg.flatten())
    assert "shall be administered" in " ".join(n.text or "" for n in seg.flatten())


@pytest.mark.parametrize("profile", ["default", "unreleased-v4"])
def test_reviewed_form_recital_is_preserved_in_form_not_instrument_preamble(profile):
    blocks = [b(1, "1. Short title.- These rules may be called the Provident Fund Rules.\n"),
              b(2, "FORM P.F.9\n", page=43),
              b(3, "WHEREAS the subscriber has applied to the Governor to grant him an advance of Rs.____ out of the sum standing to his credit.\n", page=43)]
    seg = segment(blocks, profile=profile, structural_overrides={"source_form_text_blocks": [3]})
    form = next(n for n in seg.flatten() if n.kind == "form")
    assert "WHEREAS the subscriber" in form.text
    assert not any(n.kind == "preamble" for n in seg.flatten())
    assert seg.block_roles[3][1] is form


@pytest.mark.parametrize("marker", ["*", "**", "***", ""])
def test_reviewed_note_marked_appendix_opens_distinct_division(marker):
    blocks = [b(1, "APPENDIX-III\n", page=26),
              b(2, "(See rule 1.14)\n", page=26),
              b(518599, marker + "APPENDIX-IV\n", page=27),
              b(4, "(See rule 1.31/2.26)\nExtent of delegation.\n", page=27)]
    seg = segment(blocks, structural_overrides={"source_division_openers": [
        {"source_block_id": 518599, "kind": "appendix", "label": "APPENDIX IV"}]})
    appendix = next(n for n in seg.flatten() if n.label == "APPENDIX IV")
    assert appendix.first_block == 518599
    assert "Extent of delegation" in appendix.text


def test_unreviewed_note_marker_is_not_automatically_promoted():
    seg = segment([b(1, "APPENDIX-III\n"), b(2, "*APPENDIX-IV\n")])
    assert not any(n.label == "APPENDIX IV" for n in seg.flatten())
