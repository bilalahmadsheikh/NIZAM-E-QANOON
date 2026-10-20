"""Agent K6's rules `reviewed_division_series` (key `source_division_series_blocks`) and `appendix_group_caption`
(segmenter group 32, 18 Oct 2026; doc 4626, the Constitution and Regulation of the Sindh Councils Unified Grades
(Service) Rules, 2020; owner 4626 q3 'rows-by-group', decision-review-2026-10-18-4626b.json). From
claude/agK6/work/test_k6_rules_jk_DRAFT.py (K6's draft letters J/K are not used: agent JF's I/J/K are group 31).
Pure: segment() over blocks."""
import os

import pytest

RULE_DS = "reviewed_division_series"
RULE_AC = "appendix_group_caption"
KEY_DS = "source_division_series_blocks"


from nizam.corpus.segment import segment  # noqa: E402

OD = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-18-4626b.json", "document_id": 4626,
      "question_id": "q3"}


def _b(i, text, y=100.0, page=1):
    return {"id": i, "page_no": page, "y0": y, "page_height": 792.0, "x0": 70.0, "x1": 560.0, "text": text}


SERIES = [
    _b(1, "PART-I\nPRELIMINARY", 80),
    _b(2, "1. (1) These rules may be called the Test Rules, 2020.", 110),
    _b(3, "(2) They shall come into force at once.", 140),
    _b(4, "PART-II\nCOMPOSITION OF SERVICE", 170),
    _b(5, "2. The service shall consist of the following branches.", 200),
    _b(6, "CHAPTER-III\nAPPOINTMENT, PROMOTION AND TRANSFER", 230),
    _b(7, "3. No appointment to a post shall be made except in accordance with these rules.", 260),
    _b(8, "CHAPTER-IV\nMISCELLANEOUS", 290),
    _b(9, "4. Members of the service shall be paid their remuneration.", 320),
    _b(10, "PART-V\nFINANCIAL MATTERS", 350),
    _b(11, "5. A member of the service shall draw his pay from the Council.", 380),
    _b(12, "APPENDIX\n(See rule 3)", 420),
    _b(13, "S.No\nPost\nMethod of Recruitment\nI- ADMINISTRATIVE BRANCH\n1.\nSecretary (BPS-11).\nBy initial "
           "recruitment.\n2.\nTown Officer (BPS-16).\nBy promotion.", 450),
    _b(14, "II- ACCOUNTS BRANCH", 520),
    _b(15, "1.\nAccountant (BPS-14).\nBy initial recruitment.\n2.\nAccounts Officer (BPS-17).\nBy promotion.", 550),
]
OPENERS = [1, 4, 6, 8, 10, 12]
CAPTIONS = [{"source_block_id": 13, "caption": "I- ADMINISTRATIVE BRANCH", "level": 1, "owner_decision": OD},
            {"source_block_id": 14, "caption": "II- ACCOUNTS BRANCH", "level": 1, "owner_decision": OD}]


def _by(seg, kind, label):
    hits = [n for n in seg.flatten() if n.kind == kind and str(n.label) == label]
    assert len(hits) == 1, (kind, label, len(hits))
    return hits[0]


def _parent_kind(seg, kind, label):
    p = _by(seg, kind, label).parent
    return None if p is None or p.kind in ("root", "instrument") else (p.kind, str(p.label))


# ---- reviewed_division_series ----------------------------------------------------------------------------------------------------------
def test_division_series_opens_every_named_division_at_the_root():
    seg = segment(SERIES, profile="unreleased-v4", structural_overrides={KEY_DS: OPENERS})
    for kind, label in (("part", "I"), ("part", "II"), ("chapter", "III"), ("chapter", "IV"), ("part", "V"),
                        ("appendix", "APPENDIX")):
        assert _parent_kind(seg, kind, label) is None, (kind, label)
    assert _parent_kind(seg, "section", "3") == ("chapter", "III")
    assert _parent_kind(seg, "section", "5") == ("part", "V")


def test_division_series_inert_without_the_key():
    seg = segment(SERIES, profile="unreleased-v4")
    assert _parent_kind(seg, "chapter", "III") == ("part", "II")
    assert _parent_kind(seg, "appendix", "APPENDIX") == ("part", "V")


def test_division_series_a_block_that_opens_no_division_fails_closed():
    with pytest.raises(ValueError):
        segment(SERIES, profile="unreleased-v4", structural_overrides={KEY_DS: OPENERS + [7]})


def test_division_series_a_missing_block_fails_closed():
    with pytest.raises(ValueError):
        segment(SERIES, profile="unreleased-v4", structural_overrides={KEY_DS: OPENERS + [999]})


def test_division_series_needs_its_profile_rule():
    with pytest.raises(ValueError):
        segment(SERIES, profile="default", structural_overrides={KEY_DS: OPENERS})


# ---- appendix_group_caption ----------------------------------------------------------------------------------------------------------
def test_appendix_caption_captions_hold_their_rows_in_a_root_appendix():
    seg = segment(SERIES, profile="unreleased-v4",
                  structural_overrides={KEY_DS: OPENERS, "source_schedule_group_captions": CAPTIONS})
    caps = [n for n in seg.flatten() if n.kind == "part" and getattr(n, "group_caption", False)]
    assert [n.label for n in caps] == ["I- ADMINISTRATIVE BRANCH", "II- ACCOUNTS BRANCH"]
    assert all(n.parent.kind == "appendix" for n in caps)
    rows = {(str(n.parent.label), str(n.label)) for n in seg.flatten()
            if n.parent is not None and n.parent in caps}
    assert rows == {("I- ADMINISTRATIVE BRANCH", "1"), ("I- ADMINISTRATIVE BRANCH", "2"),
                    ("II- ACCOUNTS BRANCH", "1"), ("II- ACCOUNTS BRANCH", "2")}


def test_appendix_caption_inert_without_the_captions():
    seg = segment(SERIES, profile="unreleased-v4", structural_overrides={KEY_DS: OPENERS})
    assert not [n for n in seg.flatten() if getattr(n, "group_caption", False)]


def test_appendix_caption_a_caption_not_printed_fails_closed():
    bad = [dict(CAPTIONS[0], caption="III- MEDICAL BRANCH")]
    with pytest.raises(ValueError):
        segment(SERIES, profile="unreleased-v4", structural_overrides={KEY_DS: OPENERS,
                                                                       "source_schedule_group_captions": bad})


def test_appendix_caption_a_malformed_citation_fails_closed():
    bad = [dict(CAPTIONS[1], owner_decision={"export": "x.json", "document_id": 4626})]
    with pytest.raises(ValueError):
        segment(SERIES, profile="unreleased-v4", structural_overrides={KEY_DS: OPENERS,
                                                                       "source_schedule_group_captions": bad})


# ---- wiring ----------------------------------------------------------------------------------------------------------
def test_division_series_and_appendix_caption_rule_names_join_unreleased_v4():
    from nizam.corpus.segment import SEGMENTATION_PROFILES
    assert {RULE_DS, RULE_AC} <= set(SEGMENTATION_PROFILES["unreleased-v4"])
    assert not ({RULE_DS, RULE_AC} & set(SEGMENTATION_PROFILES["default"]))


def test_division_series_key_is_wired_through_worker_recorder_and_materializer():
    import nizam.workers.segment as W
    from tools.materialize_multi_instrument import STRUCTURAL_PATCH_KEYS
    from tools.record_curation_patch import STRUCTURAL_KEYS
    assert KEY_DS in W._BZ_BLOCK_LIST_KEYS
    assert KEY_DS in STRUCTURAL_KEYS and KEY_DS in STRUCTURAL_PATCH_KEYS

    def _patch(i, value):
        return {"id": f"p{i}", "page_no": i, "match_text": "x", "before_text": "x", "after_text": "x",
                "evidence": {"structural_overrides": {KEY_DS: value}}}
    merged = W.reviewed_structural_overrides(None, [_patch(1, [11, 12]), _patch(2, [12, 13])])
    assert merged[KEY_DS] == [11, 12, 13]
    for bad in ([], [0], ["7"], [5, 5]):
        with pytest.raises(ValueError, match="unsupported curation structural override"):
            W.reviewed_structural_overrides(None, [_patch(1, bad)])
