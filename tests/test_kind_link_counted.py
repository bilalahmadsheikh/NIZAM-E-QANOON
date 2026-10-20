"""Rule W `kind_link_counted` (docs 3926, 3933, 4142): a contents row linked
by a reviewed kind link (rule `reviewed_link_unit_kind`) and resolved to its schedule is represented in the run's label
arithmetic, not reported missing.

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_kind_link_counted_DRAFT.py, against the live module. Full released A/B
of W+M: 4,508 / 4,508 identical (scratchpad agJD-ab-MWfull2.summary).
"""
from nizam.corpus import segment as S

CITE = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 3933,
        "question_id": "q1"}


def _blocks():
    texts = [("CONTENTS", 1), ("1. Short title and commencement.", 1), ("2. Definitions.", 1), ("3. Schedule.", 1),
             ("1. Short title and commencement. This Act may be called the Test Act, 2001.", 2),
             ("2. Definitions. In this Act, unless the context otherwise requires, words have their meaning.", 2),
             ("SCHEDULE", 3), ("1. The first item of the Schedule.", 3), ("2. The second item of the Schedule.", 3)]
    return [{"id": 100 + i, "text": t + " \n", "page_no": p, "y0": 100.0 + 30 * i, "page_height": 842.0,
             "x0": 72.0, "x1": 480.0} for i, (t, p) in enumerate(texts)]


def _links():
    return {"source_contents_row_links": [{"ordinal": 2, "printed_label": "3", "unit_kind": "schedule",
                                           "unit_label": "SCHEDULE", "owner_decision": CITE}]}


def _row(seg, ordinal):
    return [e for e in seg.toc_entries if e["ordinal"] == ordinal][0]


def test_W_kind_linked_row_is_linked_and_not_missing():
    seg = S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_links())
    node = _row(seg, 2)["node"]
    assert node is not None and (node.kind, node.label) == ("schedule", "SCHEDULE")
    assert "3" not in seg.missing


def test_W_off_reports_the_resolved_row_missing():
    # the defect W repairs: without it the same build names the linked row '3' in detail->missing
    profiles = S.SEGMENTATION_PROFILES
    saved = profiles["unreleased-v4"]
    profiles["unreleased-v4"] = saved - {"kind_link_counted"}
    try:
        seg = S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_links())
    finally:
        profiles["unreleased-v4"] = saved
    assert _row(seg, 2)["node"] is not None
    assert "3" in seg.missing


def test_W_inert_without_a_kind_link():
    on = S.segment(_blocks(), profile="unreleased-v4")
    profiles = S.SEGMENTATION_PROFILES
    saved = profiles["unreleased-v4"]
    profiles["unreleased-v4"] = saved - {"kind_link_counted"}
    try:
        off = S.segment(_blocks(), profile="unreleased-v4")
    finally:
        profiles["unreleased-v4"] = saved
    assert on.missing == off.missing and on.matched == off.matched
