"""Rule O `owner_supplied_schedule_part` (doc 4324 pp103-104, owner
export l q2 'schedule-rows': Part One supplied from s.184(1), Part Two at its printed 'PART TWO' line).

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_owner_schedule_part_DRAFT.py, against the live module (export j/l group 8;
one combined full released A/B over O+B).
"""
import os
import pytest

from nizam.corpus import segment as S

OWNER = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-14-l.json", "document_id": 4324,
         "question_id": "q2"}


def _b(i, text, y0, page=1):
    return {"id": i, "text": text, "page_no": page, "x0": 120.0, "x1": 540.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "1. \nThis Act may be called the Test Land Act, 1967. \n", 40.0),
            _b(2, "2. (1) \nThe enactments mentioned in Part One of \nthe Schedule are hereby repealed. \n", 100.0),
            _b(3, " \n(2) \nThe enactments mentioned in Part Two of the \nSchedule shall stand repealed. \n", 160.0),
            _b(10, "1. \nThe Punjab Riverain Boundaries Act, 1899 (Punjab Act I of \n1899). \n", 60.0, page=2),
            _b(11, "2. \nThe Punjab Land Revenue (Amendment) Act, 1912 (Punjab Act II \nof 1912). \n", 100.0, page=2),
            _b(12, "PART TWO \n", 140.0, page=2),
            _b(13, "1. \nThe Sind Revenue Jurisdiction Act, 1876 (Sind Act X of 1876). \n", 60.0, page=3),
            _b(14, "2. \nThe Bombay Land Revenue Code, 1879 (Bombay Act V of 1879). \n", 100.0, page=3)]


def _opener():
    return [{"source_block_id": 10, "label": "SCHEDULE",
             "source_text": "1. The Punjab Riverain Boundaries Act, 1899 (Punjab Act I of 1899).",
             "owner_decision": OWNER}]


def _parts(one=True, two=True, **bad):
    out = []
    if one:
        out.append({"first_block_id": 10, "label": "ONE", "evidence_block_id": 2, "owner_decision": OWNER})
    if two:
        out.append({"first_block_id": 12, "label": "TWO", "evidence_block_id": 3, "owner_decision": OWNER})
    for item in out:
        item.update({k: v for k, v in bad.items() if item["label"] == bad.get("_for", item["label"])})
        item.pop("_for", None)
    return out


def _seg(parts, profile="unreleased-v4"):
    return S.segment(_blocks(), profile=profile,
                     structural_overrides={"source_unlabelled_schedule_openers": _opener(),
                                           "source_owner_schedule_parts": parts})


def _shape(seg):
    sch = next(n for n in seg.flatten() if n.kind == "schedule")
    return [(p.kind, p.label, [(c.kind, c.label) for c in p.children]) for p in sch.children]


def test_O_opens_supplied_and_printed_parts():
    got = _shape(_seg(_parts()))
    assert got == [("part", "ONE", [("clause", "1"), ("clause", "2")]),
                   ("part", "TWO", [("clause", "1"), ("clause", "2")])]


def test_O_printed_line_is_not_row_text():
    seg = _seg(_parts())
    row2 = [n for n in seg.flatten() if n.kind == "clause" and n.parent.label == "ONE" and n.label == "2"][0]
    assert "PART TWO" not in row2.text


def test_O_inert_without_the_key():
    seg = S.segment(_blocks(), profile="unreleased-v4",
                    structural_overrides={"source_unlabelled_schedule_openers": _opener()})
    assert not any(n.kind == "part" for n in seg.flatten())


def test_O_refuses_a_label_the_act_does_not_name():
    with pytest.raises(ValueError):
        _seg(_parts(two=False, label="THREE"))


def test_O_refuses_a_printed_spec_on_a_block_that_is_not_the_part_line():
    with pytest.raises(ValueError):
        _seg([_parts(two=False)[0], {"first_block_id": 11, "label": "TWO", "evidence_block_id": 3,
                                      "owner_decision": OWNER}])


def test_O_refuses_a_printed_part_before_any_part():
    with pytest.raises(ValueError):
        _seg(_parts(one=False))


def test_O_refuses_a_malformed_owner_citation():
    with pytest.raises(ValueError):
        _seg(_parts(two=False, owner_decision={"export": "x.json"}))


def test_O_needs_its_profile_rule():
    with pytest.raises(ValueError):
        _seg(_parts(), profile="unreleased-v3")
