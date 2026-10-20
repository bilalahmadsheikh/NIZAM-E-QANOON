"""Rule I `owner_unnumbered_unheaded` (doc 4044 p1, owner export l q2
'provision', lead 15 Oct option (a): label = the printed words up to the first comma, heading empty).

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_owner_unnumbered_unheaded_DRAFT.py, against the live module (export j/l group 14;
one combined full released A/B over the 16 Oct groups).
"""
import os
import pytest

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 4044,
         "question_id": "q2"}
LABEL = "The Forest Department Forest Guard (Divisional) Service Rules"


def _b(i, text, y0):
    return {"id": i, "text": text, "page_no": 1, "x0": 72.0, "x1": 526.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "1. \nThese rules may be called the Test Recruitment Rules, 1979. \n", 40.0),
            _b(2, "2. \nThey shall come into force at once. \n", 80.0),
            _b(3, "3. \nThe method of recruitment shall be as given in the schedule annexed. \n", 120.0),
            _b(4, "1[The Forest Department Forest Guard (Divisional) Service Rules, 1962 are hereby \nrepealed] \n",
               200.0)]


def _opener(label=LABEL, heading="", owner=OWNER):
    return {"source_unnumbered_section_openers": [{"source_block_id": 4, "after_section_label": "3", "label": label,
                                                    "heading": heading, "source_prefix": "1[",
                                                    "owner_decision": owner}]}


def _tops(seg):
    return [(n.kind, n.label, n.heading) for n in seg.root.children]


def test_I_opens_the_unheaded_provision():
    tops = _tops(S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_opener()))
    assert tops[-1] == ("section", LABEL, None)
    assert [t[1] for t in tops[:3]] == ["1", "2", "3"]


def test_I_refuses_a_label_that_is_not_the_printed_words_to_the_comma():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_opener(label="Repeal"))
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4",
                  structural_overrides=_opener(label="The Forest Department Forest Guard"))


def test_I_refuses_a_heading():
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_opener(heading="Repeal."))


def test_I_off_without_its_profile_rule():
    profiles = dict(S.SEGMENTATION_PROFILES)
    S.SEGMENTATION_PROFILES["agjd-no-i"] = profiles["unreleased-v4"] - {"owner_unnumbered_unheaded"}
    try:
        with pytest.raises(ValueError):
            S.segment(_blocks(), profile="agjd-no-i", structural_overrides=_opener())
    finally:
        S.SEGMENTATION_PROFILES.pop("agjd-no-i", None)
