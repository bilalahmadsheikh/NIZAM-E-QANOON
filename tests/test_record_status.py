"""tools/record_status.py: 'in_force' only on established commencement and no known repeal (migration 0082)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import record_status as st  # noqa: E402
from record_statutory_repeals import norm  # noqa: E402


def _hits(*texts):
    return st.named_against([(f"r{i}", t) for i, t in enumerate(texts)])


def test_a_whole_repeal_anywhere_stops_the_claim_whatever_repeals_it():
    hits = _hits("The Foo Act, 1990 (V of 1990) is hereby repealed.")
    assert st.screen({norm("Foo Act")}, 1990, {"self"}, hits, "") == "named_in_a_repeal_or_cease_clause"
    # an Ordinance's clause, a territorial limit, a 'cease to have effect': all stop it
    for text in ("The Foo Act, 1990 is hereby repealed in its application to the Islamabad Capital Territory.",
                 "The Foo Act, 1990 shall cease to have effect."):
        assert st.screen({norm("Foo Act")}, 1990, {"self"}, _hits(text), "") is not None


def test_a_clause_about_a_provision_of_the_law_does_not_stop_it():
    for text in ("section 4 of the Foo Act, 1990 is hereby repealed.",
                 "In the Foo Act, 1990, in section 309, the words 'or both' are hereby omitted."):
        assert st.screen({norm("Foo Act")}, 1990, {"self"}, _hits(text), "") is None


def test_a_law_naming_itself_or_its_twin_is_not_a_repeal_of_it():
    hits = {(norm("Foo Act"), 1990): ["self", "twin"]}
    assert st.screen({norm("Foo Act")}, 1990, {"self", "twin"}, hits, "") is None
    assert st.screen({norm("Foo Act")}, 1991, {"self"}, _hits("The Foo Act, 1990 is hereby repealed."), "") is None


def test_a_shorter_or_longer_form_of_the_title_stops_it_too():
    hits = _hits("The General Sales Tax Act, 1948 is hereby repealed.")
    assert st.screen({norm("Pakistan General Sales Tax Act")}, 1948, {"self"}, hits, "") is not None
    # but two words are not enough to say it is the same law
    assert st.screen({norm("Pakistan Tax Act")}, 1948, {"self"}, _hits("The Tax Act, 1948 is hereby repealed."),
                     "") is None


def test_ocr_damaged_titles_and_savings_language_stop_it():
    # 9296 s.40(4): the repeal sentence is OCR-damaged; the savings clause still says the Act was repealed
    hits = _hits("The provisions of the Pakistan G Sales Tax Act, 1948, shall apply in respect of any arrears "
                 "unpaid at the date of the repeal of that Act.")
    assert st.screen({norm("Pakistan General Sales Tax Act")}, 1948, {"self"}, hits, "") is not None
    assert st.same_law(norm("Pakistan General Sales Tax Act"), norm("Pakistan G Sales Tax Act"))
    assert not st.same_law(norm("Pakistan General Sales Tax Act"), norm("Pakistan Customs Act"))


def test_the_portal_repeal_note_stops_the_claim():
    assert st.screen({norm("Foo Act")}, 1990, {"self"}, {}, "Foo Act, 1990 (Repealed by Act XIV of 2016)") == \
        "portal_repeal_note"


def test_only_acts_are_asserted():
    assert st.KINDS == {"act", "constitution"}
