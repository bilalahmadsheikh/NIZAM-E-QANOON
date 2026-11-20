"""D-108, the link rules (nizam.storage.linking): the phrase that makes a reference's edge kind (docs/03b), another
law as printed, and the words a parent law is named by. Pure: no database."""
from __future__ import annotations

from nizam.storage import linking as L


def _r(text):
    return [(r.kind, r.labels, r.edge, r.external, r.other_law) for r in L.references(text)]


def test_the_phrase_is_the_edge_kind():
    # docs/03b: notwithstanding and subject_to point at the same provision and mean opposite things
    assert _r("Notwithstanding anything contained in section 5, the Government may") == \
        [("unit", ("5",), "notwithstanding", False, None)]
    assert _r("Subject to the provisions of section 5, the Court may") == [("unit", ("5",), "subject_to", False, None)]
    assert _r("Save as provided in section 17, nothing in this Ordinance") == \
        [("unit", ("17",), "subject_to", False, None)]
    assert _r("Without prejudice to section 9, the Authority may") == [("unit", ("9",), "subject_to", False, None)]
    assert _r("on conclusion of the proceedings under section 4") == [("unit", ("4",), "refers_to", False, None)]
    # the phrase nearest the reference governs it
    assert _r("Subject to this Act and notwithstanding anything in section 12, a person") == \
        [("unit", ("12",), "notwithstanding", False, None)]


def test_another_law_is_kept_as_printed():
    assert _r("an offence under section 302 of the Pakistan Penal Code") == \
        [("unit", ("302",), "refers_to", True, "Pakistan Penal Code")]
    assert _r("the penalty provided by section 188 of the Pakistan Penal Code (XLV of 1860)") == \
        [("unit", ("188",), "refers_to", True, "Pakistan Penal Code")]
    assert _r("under section 7 of the Protection against Harassment of Women at the Workplace Act, 2010") == \
        [("unit", ("7",), "refers_to", True, "Protection against Harassment of Women at the Workplace Act, 2010")]
    assert _r("the powers conferred by section 25 of the Act") == [("unit", ("25",), "refers_to", True, "Act")]
    assert _r("under section 3 of the said Act") == [("unit", ("3",), "refers_to", True, "said Act")]
    # a law named earlier in the sentence; the title starts after its last 'the'
    assert _r("Nothing in this section shall be deemed to affect the Evidence Act, 1872 (I of 1872), sections 123 "
              "and 124") == [("unit", ("123", "124"), "refers_to", True, "Evidence Act, 1872")]
    assert _r("Rep. by the Lunacy Act, 1912 (IV of 1912), S.101 and Schedule II.") == \
        [("schedule", (2,), "refers_to", True, "Lunacy Act, 1912")]


def test_a_suffix_printed_apart_is_part_of_the_label():
    assert _r("committed by him under section 295 C of the Pakistan Penal Code, 1860") == \
        [("unit", ("295C",), "refers_to", True, "Pakistan Penal Code, 1860")]
    assert _r("sections 462 I and 462J apply") == [("unit", ("462I", "462J"), "refers_to", False, None)]
    # a capital that opens the next sentence is not a suffix
    assert _r("under section 5. A Magistrate may") == [("unit", ("5",), "refers_to", False, None)]


def test_the_word_printed_before_the_number_is_kept():
    # a Rules instrument numbers its own units as rules: 'section 121' there is the parent Act's (D-108)
    words = [(r.word, r.labels, r.of_these) for r in L.references(
        "an application under section 121, or under rule 15 and rules 3 to 5, or section 16 of these rules")]
    assert words == [("section", ("121",), False), ("rule", ("15",), False), ("rule", ("3", "4", "5"), False),
                     ("section", ("16",), True)]
    assert _r("REPORT OF ARREST (Under Section 62 Criminal Procedure Code)") == \
        [("unit", ("62",), "refers_to", True, "Criminal Procedure Code")]


def test_the_phrase_governs_only_what_it_names():
    # the non-obstante clause is about the Code; the Schedule is merely named
    assert [r.edge for r in L.references("Notwithstanding anything in the Code of Criminal Procedure, 1898 (Act V of "
                                         "1898), a Court trying any offence referred to in the Third Schedule")] == \
        ["refers_to"]
    # ... unless the law in between is the reference's own
    assert [(r.edge, r.other_law) for r in L.references(
        "Notwithstanding anything contained in the Code of Civil Procedure, 1908, section 9")] == \
        [("notwithstanding", "Code of Civil Procedure, 1908")]


def test_a_title_continues_past_its_keyword():
    assert _r("under section 9 of the Code of Civil Procedure and section 4") == \
        [("unit", ("9",), "refers_to", True, "Code of Civil Procedure"), ("unit", ("4",), "refers_to", False, None)]
    assert L.law_named("Code of Civil Procedure") == ("Code of Civil Procedure", None)


def test_a_run_of_references_shares_the_law_named_after_it():
    refs = L.references("Notwithstanding anything in the Code of Criminal Procedure, 1898 (Act V of 1898) in the case "
                        "of any offence punishable under section 161, section 164, section 165, of the Azad Kashmir "
                        "Penal Code or under section 5 of the Prevention of Corruption Act")
    assert [(r.labels, r.other_law) for r in refs] == [
        (("161",), "Azad Kashmir Penal Code"), (("164",), "Azad Kashmir Penal Code"),
        (("165",), "Azad Kashmir Penal Code"), (("5",), "Prevention of Corruption Act")]
    assert [r.labels for r in L.references("a male sentenced under Section 4-A")] == [("4A",)]


def test_a_sub_section_is_not_a_section():
    assert [r.labels for r in L.references("Subject to the requirements of sub-section 4 of section 372 of the Act")] \
        == [("372",)]
    assert [r.labels for r in L.references("under Sub-section (2) and sub section 3 of section 9")] == [("9",)]
    assert L.parent_word("Ordinance") == "ordinance" and L.parent_word("said Act") == "act"


def test_decimal_rule_numbers_and_footnote_markers():
    assert [r.labels for r in L.references("Except as provided in Rules 12.1 and 12.4, direct appointments")] == \
        [("12.1", "12.4")]
    assert _r("by the provisions of section 17 of the 2Guardian and Wards Act, 1890, and if") == \
        [("unit", ("17",), "refers_to", True, "Guardian and Wards Act, 1890")]


def test_a_phrase_stops_at_a_new_clause_and_any_dash_continues():
    # CrPC s.352(2): the non-obstante clause is about sub-section (1), not the PPC sections that follow it
    assert {r.edge for r in L.references("Notwithstanding anything contained in sub-section (1), the trial of "
                                         "offences under sections 354A, 376 and 377 of the Pakistan Penal Code")} == \
        {"refers_to"}
    assert L.continues("(g) “drug” includes ⎯") and L.definitions_in("(g) “drug” includes ⎯") == [("drug", True)]
    assert L.continues("“Government work” means a work made under the control of⸺")


def test_another_law_past_a_division_name():
    assert _r("under rule 40 & 40A of Chapter Miscellaneous of Sales Tax (Withholding) Rules, 2007") == \
        [("unit", ("40", "40A"), "refers_to", True, "Sales Tax (Withholding) Rules, 2007")]
    assert L.AMENDING_TITLE.search("West Pakistan Laws (Adaptation) Order, 1964")
    assert L.AMENDING_TITLE.search("Repealing and Amending Act, 1957")


def test_a_year_or_another_law_s_name_is_not_a_rule_number():
    assert L.references("under the Civil Servants (Appointment) Rules 1973") == []
    assert L.references("as required by Martial Law Regulation 115") == []
    assert [r.word for r in L.references("subject to regulation 7")] == ["regulation"]


def test_a_named_law_and_a_parent_law():
    assert L.law_named("Contract Act, 1872") == ("Contract Act", 1872)
    assert L.law_named("Pakistan Penal Code") == ("Pakistan Penal Code", None)
    assert L.law_named("Act") is None and L.law_named("said Act") is None and L.law_named("") is None
    assert L.parent_word("Act") and L.parent_word("said Act") and L.parent_word("Ordinance")
    assert not L.parent_word("Pakistan Penal Code")


def test_continuation_counts_the_sub_items():
    assert L.continuation(["the Government or any department of the Government; or",
                           "any court, tribunal or other judicial authority;",
                           "“infringing copy” means,__", "in relation to a literary work"]) == 2
    assert L.continuation([]) == 0
    assert L.continuation(["x" * 2000, "y" * 2000]) == 1                    # the character cap


def test_definition_keys_and_openings():
    assert L.term_key("  Revenue   Officer ") == "revenue officer"
    assert L.opening("In this Chapter, unless the context otherwise requires, “Court” means") == \
        "In this Chapter, unless the context otherwise requires, "
    assert L.opening("(a) no quotation here") == ""


# --- definitions ----------------------------------------------------------------------------------------------------
def test_a_definition_clause_names_its_words():
    assert L.defined_terms("“complainant” means a woman who files a complaint;") == ["complainant"]
    assert L.defined_terms('The words "public servant" denote a person falling under any of the descriptions') == \
        ["public servant"]
    assert L.defined_terms("“child” and “minor” mean a person under eighteen;") == ["child", "minor"]
    assert L.defined_terms("(b) “borrower” or “debtor” means a person to whom a loan is advanced;") == \
        ["borrower", "debtor"]
    assert L.defined_terms("In this section the word \"offence\" includes every act") == ["offence"]
    assert L.defined_terms("“Ombudsperson” shall have the same meaning as in the Act of 2010") == ["Ombudsperson"]


def test_a_quoted_word_without_a_defining_verb_is_not_a_definition():
    assert L.defined_terms('the notice called "Form A" shall be served on the tenant') == []
    assert L.defined_terms("a woman’s property may be restored") == []


def test_an_empty_definition_is_marked():
    # the segmenter left the sub-clauses of 'voter' outside this node (Elections Act 2017 s.2(xl), D-107)
    assert L.definitions_in("(xl) “validly nominated candidate” means a candidate whose nomination paper has been "
                            "accepted; and (xli) “voter” means—") == [("validly nominated candidate", False),
                                                                     ("voter", True)]


def test_a_flattened_definition_continues_into_its_following_siblings():
    # Copyright Ordinance 1962 s.2(m): its (i) and (ii) are the clause's siblings in the tree, not its children
    assert L.continues("“Government work” means a work which is made or published by or under the direction or "
                       "control of__")
    assert L.continues("“work” means any of the following works, namely:__")
    assert L.continues("(xli) “voter” means—")
    assert not L.continues("“property” includes any moveable and immoveable property; and")
    assert not L.continues("“rules” means the rules made under this Act.")
    assert L.continuation(["the Government or any department of the Government; or",
                           "any court, tribunal or other judicial authority;", "“infringing copy” means,__",
                           "in relation to a literary work"]) == 2            # stops at the next definition


def test_a_defined_word_is_used_as_a_whole_word_with_plain_plurals():
    assert L.term_use("employer", "every employer shall pay") == 6
    assert L.term_use("employer", "all employers shall pay") == 4
    assert L.term_use("rent", "the rented premises") is None
    assert L.term_use("Revenue Officer", "may apply to a Revenue  Officer for partition") is not None


def test_an_instrument_word_is_used_only_as_the_law_s_own_name():
    # '"Act" means the Punjab Alternate Dispute Resolution Act 2019' is not used by naming another Act's title
    assert L.term_use("Act", "under the Punjab Rented Premises Act, 2009 (VII of 2009)") is None
    assert L.term_use("Act", "a dispute under this Act or the rules") is not None
    assert L.term_use("Act", "the powers conferred by section 25 of the Act") is not None


def test_scope_is_read_from_the_opening_words():
    assert L.scope_word(["In this Chapter, unless there is anything repugnant"]) == "chapter"
    assert L.scope_word(["", "In this Act, unless the context otherwise requires"]) == "act"
    assert L.scope_word(["For the purposes of this section,"]) == "section"
    assert L.scope_word(["(a) “child” means"]) is None


def test_a_chapter_definition_reaches_its_chapter_and_a_missing_chapter_reaches_no_further_than_its_unit():
    chain = [("ch3", "chapter"), ("s10", "section"), ("cla", "clause")]
    assert L.definition_scope("chapter", chain, "s10", "act") == ("division", "ch3")
    # the tree has no Chapter above this unit: never the whole law (Constitution Art. 203B, D-107)
    assert L.definition_scope("chapter", chain[1:], "s10", "act") == ("unit", "s10")
    assert L.definition_scope(None, chain, "s10", "act") == ("law", None)
    assert L.definition_scope("section", chain, "s10", "act") == ("unit", "s10")
    assert L.definition_scope("act", chain, "s10", "act") == ("law", None)
    # 'In this Order' is a CPC-style Order the unit sits in, unless the law itself is an Order
    assert L.definition_scope("order", [("o21", "order"), ("r1", "section")], "r1", "act") == ("division", "o21")
    assert L.definition_scope("order", [("s3", "section")], "s3", "order") == ("law", None)


def test_an_amending_law_is_known_by_its_title():
    assert L.AMENDING_TITLE.search("Finance Act, 2006")
    assert L.AMENDING_TITLE.search("Criminal Laws (Amendment) Act, 2016")
    assert not L.AMENDING_TITLE.search("Financial Institutions (Recovery of Finances) Ordinance, 2001")
    assert not L.AMENDING_TITLE.search("Punjab Finance Commission Act")


# --- references -------------------------------------------------------------------------------------------------------
def _refs(text):
    return [(r.kind, r.labels, r.qualifies, r.external) for r in L.references(text)]


def test_references_to_the_same_law():
    assert _refs("subject to the provisions of section 11, become members") == [("unit", ("11",), True, False)]
    assert _refs("Notwithstanding anything contained in sections 4, 8, 9 and 12A, the Government may") == \
        [("unit", ("4", "8", "9", "12A"), True, False)]
    assert _refs("the rules contained in sections 10 to 12 apply") == [("unit", ("10", "11", "12"), False, False)]
    assert _refs("proceedings under section 4 of this Act") == [("unit", ("4",), False, False)]
    assert _refs("the offences in section 9 in Chapter III") == [("unit", ("9",), False, False)]
    assert _refs("as provided in Article 25(1)") == [("unit", ("25",), False, False)]


def test_references_to_another_law_are_marked():
    assert _refs("an offence under section 302 of the Pakistan Penal Code") == [("unit", ("302",), False, True)]
    assert _refs("the powers conferred by section 25 of the Act") == [("unit", ("25",), False, True)]
    assert _refs("In the Profession Tax Limitation Act, 1941 (XX of 1941), for section 2 the following") == \
        [("unit", ("2",), False, True)]


def test_schedule_references():
    assert _refs("the goods specified in the Second Schedule") == [("schedule", (2,), False, False)]
    assert _refs("as listed in Schedule II") == [("schedule", (2,), False, False)]
    assert _refs("the fees in the Schedule") == [("schedule", (), False, False)]
    assert _refs("the Schedule to the Pakistan Penal Code") == [("schedule", (), False, True)]
    assert L.schedule_number("FIRST SCHEDULE", None) == 1
    assert L.schedule_number("Schedule-i", None) == 1
    assert L.schedule_number("SCHEDULE 3", None) == 3
    assert L.schedule_number("Schedule", "THE NINTH SCHEDULE") == 9
    assert L.schedule_number("Schedule", None) is None
