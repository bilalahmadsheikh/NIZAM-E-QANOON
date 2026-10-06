"""Source-anchored regression for split Rules 4/5 and non-law signer blocks."""

import pytest

from nizam.corpus.segment import (
    _section_number_spans, _source_nonoperative_role, segment,
)


def _blocks():
    texts = [
        (2, "3. Custody of moneys.- The fund shall be kept in a bank.\n"
         "Head of Account and Withdrawal.-- Contributions shall be deducted."),
        (3, "Deposits shall be classified.\n\n5. \n \n \n"),
        (3, "Withdrawal.-- The budget provision shall be drawn monthly."),
        (3, "6. Grant.-- Assistance shall be drawn from the fund."),
    ]
    return [
        {"id": i, "page_no": page, "text": value,
         "x0": 72.0, "x1": 500.0, "y0": i * 60.0,
         "y1": i * 60.0 + 20, "page_height": 800.0}
        for i, (page, value) in enumerate(texts, 1)
    ]


PATCHES = [
    {"id": "rule-4", "page_no": 2,
     "match_text": "Head of Account and Withdrawal.--",
     "before_text": "Head of Account and Withdrawal.--",
     "after_text": "4. Head of Account and Withdrawal.--"},
    {"id": "rule-5-number", "page_no": 3,
     "match_text": "Deposits shall be classified.",
     "before_text": "Deposits shall be classified.\n\n5. \n \n \n",
     "after_text": "Deposits shall be classified.\n\n5. Withdrawal.-- \n"},
    {"id": "rule-5-heading", "page_no": 3,
     "match_text": "Withdrawal.-- The budget provision",
     "before_text": "Withdrawal.-- The budget provision",
     "after_text": "The budget provision"},
]


def test_split_rule_headings_preserve_both_operatives_and_source_blocks():
    source = _blocks()
    original = [block["text"] for block in source]
    parsed = segment(source, curation_patches=PATCHES, profile="unreleased-v4")
    sections = {node.label: node for node in parsed.flatten()
                if node.kind == "section"}
    assert [label for label in sections if label in {"3", "4", "5", "6"}] == [
        "3", "4", "5", "6"]
    assert sections["4"].first_block == 1
    assert sections["5"].first_block == 2
    assert "Contributions shall be deducted" in sections["4"].text
    assert "Deposits shall be classified" in sections["4"].text
    assert "budget provision shall be drawn" in sections["5"].text
    assert [block["text"] for block in source] == original


def test_split_reading_fails_closed_when_source_text_changes():
    source = _blocks()
    source[1]["text"] = source[1]["text"].replace("5.", "6.")
    with pytest.raises(ValueError, match="before_text is not unique"):
        segment(source, curation_patches=PATCHES, profile="unreleased-v4")


def test_exact_signatory_blocks_are_not_law():
    signatory = {
        "id": 350849, "page_no": 4,
        "text": "Speaker, \nProvincial Assembly find and Chairman \n",
    }
    stamp = {
        "id": 350850, "page_no": 4,
        "text": ("Of the Member Welfare Committee. \n \n \n \n \n \n \n"
                 "Jalil/*.* \n5-8-2015 \n \n \n \n \n \n \n"),
    }
    assert _source_nonoperative_role(signatory) == "preface"
    assert _source_nonoperative_role(stamp) == "preface"
    assert _source_nonoperative_role({**signatory, "text": signatory["text"] + " Act"}) is None


def test_compound_contents_rule_three_keeps_its_exact_source_anchor():
    block = {
        "id": 350823, "page_no": 1, "y0": 235.880,
        "text": (
            "1. Short title, commencement and application. \n"
            "2. Definitions. \n"
            "3. (1) Custody of moneys. (2) Investment of moneys. \n"
            "4. Head of Account and Withdrawal. \n"
            "5. Withdrawal. \n"
            "6. Grant. \n"
            "7. Power of Chairman. \n"
            "8. Auditing. \n"
            "9. Meetings. \n"
            "10. Agenda, notices and record of the proceedings of meetings. \n"
            "11. Quorum. \n"
            "12. Decision. \n"
            "13. Casting vote of the Chairman. \n"
            "14. Travelling and daily allowances. \n"
            "15.  General Supervision and control of the Chairman. \n"
            "16. Residuary Powers. \n"
        ),
    }
    rows = _section_number_spans([block])
    rule_three = [row for row in rows if row[2] == "3"]
    assert len(rule_three) == 1
    assert rule_three[0][3] == "(1) Custody of moneys. (2) Investment of moneys."
    changed = {**block, "text": block["text"].replace("Custody of moneys", "Custody")}
    assert not [row for row in _section_number_spans([changed])
                if row[2] == "3" and row[3]]
