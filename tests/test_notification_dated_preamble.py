"""Rule B `notification_dated_preamble` (doc 4340 p4, owner export l q3
'as-named': contents row 2 'NOTIFICATION.' names the Authority's notification, held as the preamble).

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_notification_dated_preamble_DRAFT.py, against the live module (export j/l group 8;
one combined full released A/B over O+B).
"""
import os

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 4340,
         "question_id": "q3"}
NOTE = (" \nThe 21st May, 1990 \n \nNo.Admn/174/PA/DA&C/FDA. In exercise of the powers conferred by Section \n44 of "
        "the Test Cities Act, 1976, the Authority is pleased to make the following \nregulations, namely: - \n")


def _b(i, text, y0, page=1):
    return {"id": i, "text": text, "page_no": page, "x0": 108.0, "x1": 528.0, "y0": y0, "page_height": 842.0}


def _blocks(note=NOTE):
    return [_b(1, " \nCONTENTS \n", 40.0),
            _b(2, " \n1. TEST REGULATIONS, 1990. \n", 60.0),
            _b(3, "2. NOTIFICATION. \n", 80.0),
            _b(4, "3. PART-I-GENERAL. \n", 100.0),
            _b(10, " \nNOTIFICATION \n", 40.0, page=2),
            _b(11, note, 60.0, page=2),
            _b(12, "PART-I-GENERAL \n \n1. (1)  These Regulations may be called the Test Regulations, 1990.  \n", 160.0,
               page=2),
            _b(13, "2. DEFINITIONS: - In these Regulations the following expressions have these meanings: - \n", 220.0,
               page=2)]


LINKS = [{"ordinal": 0, "printed_label": "1", "unit_label": "1", "index_row": True, "owner_decision": OWNER},
         {"ordinal": 1, "printed_label": "2", "unit_label": None, "owner_decision": OWNER}]


def _pre(seg):
    return [n for n in seg.flatten() if n.kind == "preamble"]


def _seg(blocks, links=LINKS, profile="unreleased-v4"):
    return S.segment(blocks, profile=profile, structural_overrides={"source_contents_row_links": links,
                                                                    "source_body_start_block": 10})


def test_B_dated_notification_is_the_preamble():
    pre = _pre(_seg(_blocks()))
    assert len(pre) == 1 and pre[0].first_block == 11 and "In exercise of the powers conferred" in pre[0].text


def test_B_inert_without_a_notification_row_link():
    links = [LINKS[0], dict(LINKS[1], unit_label="2")]
    try:
        seg = _seg(_blocks(), links)
    except ValueError:
        return  # a link to a unit the body does not carry fails closed; either way no preamble is invented
    assert _pre(seg) == []


def test_B_needs_the_date_line_shape():
    pre = _pre(_seg(_blocks(NOTE.replace("The 21st May, 1990", "Dated Lahore"))))
    assert pre == []


def test_B_off_without_its_profile_rule():
    # v4 without B: the dated paragraph is not admitted by notification_preamble_row's 'No. ' shape
    import nizam.corpus.segment as real  # noqa: F401  (the installed copy carries B in unreleased-v4 only)
    profiles = dict(S.SEGMENTATION_PROFILES)
    S.SEGMENTATION_PROFILES["agjd-no-b"] = profiles["unreleased-v4"] - {"notification_dated_preamble"}
    try:
        assert _pre(_seg(_blocks(), profile="agjd-no-b")) == []
    finally:
        S.SEGMENTATION_PROFILES.pop("agjd-no-b", None)
