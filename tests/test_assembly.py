"""D-107, evidence assembly (docs/04 §7): the pure rules -- what a clause defines and for where, what a unit names,
how a citation is rendered from records, and how the budget selector admits, skips and replaces. No database."""
from __future__ import annotations

from nizam.retrieval import assembly as A
from nizam.storage.evidence_read import Ancestor, Node


# --- definitions ----------------------------------------------------------------------------------------------------
def test_a_definition_clause_names_its_words():
    assert A.defined_terms("“complainant” means a woman who files a complaint;") == ["complainant"]
    assert A.defined_terms('The words "public servant" denote a person falling under any of the descriptions') == \
        ["public servant"]
    assert A.defined_terms("“child” and “minor” mean a person under eighteen;") == ["child", "minor"]
    assert A.defined_terms("(b) “borrower” or “debtor” means a person to whom a loan is advanced;") == \
        ["borrower", "debtor"]
    assert A.defined_terms("In this section the word \"offence\" includes every act") == ["offence"]
    assert A.defined_terms("“Ombudsperson” shall have the same meaning as in the Act of 2010") == ["Ombudsperson"]


def test_a_quoted_word_without_a_defining_verb_is_not_a_definition():
    assert A.defined_terms('the notice called "Form A" shall be served on the tenant') == []
    assert A.defined_terms("a woman’s property may be restored") == []


def test_an_empty_definition_is_marked():
    # the segmenter left the sub-clauses of 'voter' outside this node (Elections Act 2017 s.2(xl), D-107)
    assert A.definitions_in("(xl) “validly nominated candidate” means a candidate whose nomination paper has been "
                            "accepted; and (xli) “voter” means—") == [("validly nominated candidate", False),
                                                                     ("voter", True)]


def test_a_flattened_definition_continues_into_its_following_siblings():
    # Copyright Ordinance 1962 s.2(m): its (i) and (ii) are the clause's siblings in the tree, not its children
    assert A.continues("“Government work” means a work which is made or published by or under the direction or "
                       "control of__")
    assert A.continues("“work” means any of the following works, namely:__")
    assert A.continues("(xli) “voter” means—")
    assert not A.continues("“property” includes any moveable and immoveable property; and")
    assert not A.continues("“rules” means the rules made under this Act.")
    sibs = [_node("p.s_2.cl_i", "clause", "i", "the Government or any department of the Government; or"),
            _node("p.s_2.cl_ii", "clause", "ii", "any court, tribunal or other judicial authority;"),
            _node("p.s_2.cl_n", "clause", "n", "“infringing copy” means,__"),
            _node("p.s_2.cl_i2", "clause", "i", "in relation to a literary work")]
    assert [n.label for n in A.continuation(sibs)] == ["i", "ii"]          # stops at the next definition


def test_a_defined_word_is_used_as_a_whole_word_with_plain_plurals():
    assert A.term_use("employer", "every employer shall pay") == 6
    assert A.term_use("employer", "all employers shall pay") == 4
    assert A.term_use("rent", "the rented premises") is None
    assert A.term_use("Revenue Officer", "may apply to a Revenue  Officer for partition") is not None


def test_an_instrument_word_is_used_only_as_the_law_s_own_name():
    # '"Act" means the Punjab Alternate Dispute Resolution Act 2019' is not used by naming another Act's title
    assert A.term_use("Act", "under the Punjab Rented Premises Act, 2009 (VII of 2009)") is None
    assert A.term_use("Act", "a dispute under this Act or the rules") is not None
    assert A.term_use("Act", "the powers conferred by section 25 of the Act") is not None


def test_scope_is_read_from_the_opening_words():
    assert A.scope_word(["In this Chapter, unless there is anything repugnant"]) == "chapter"
    assert A.scope_word(["", "In this Act, unless the context otherwise requires"]) == "act"
    assert A.scope_word(["For the purposes of this section,"]) == "section"
    assert A.scope_word(["(a) “child” means"]) is None


def _anc(path, kind, label="x", depth=None):
    return Ancestor(path, path, kind, label, None, depth if depth is not None else path.count(".") + 1)


def test_a_chapter_definition_reaches_its_chapter_and_a_missing_chapter_reaches_no_further_than_its_unit():
    unit = _anc("fed.act.y_o1.ch_3.s_10", "section")
    chain = (_anc("fed.act.y_o1.ch_3", "chapter"), unit, _anc("fed.act.y_o1.ch_3.s_10.cl_a", "clause"))
    assert A._scope_path("chapter", chain, unit, None) == ("division", "fed.act.y_o1.ch_3")
    assert A._applies(("division", "fed.act.y_o1.ch_3"), "fed.act.y_o1.ch_3.s_12")
    assert not A._applies(("division", "fed.act.y_o1.ch_3"), "fed.act.y_o1.ch_4.s_20")
    # the tree has no Chapter above this unit: never the whole law (Constitution Art. 203B, D-107)
    bare = (unit, _anc("fed.act.y_o1.ch_3.s_10.cl_a", "clause"))
    assert A._scope_path("chapter", bare, unit, None) == ("unit", unit.path)
    assert A._scope_path(None, chain, unit, None) == ("law", None)
    assert A._scope_path("section", chain, unit, None) == ("unit", unit.path)


def test_a_chapter_definition_reaches_only_the_units_printed_after_it():
    # Constitution Art. 203B ('In this Chapter', the Federal Shariat Court) sits in the tree's Chapter 3 with the
    # High Courts' Articles 192-203 before it: its 'Court' must not reach them (D-107)
    scope = ("division", "c.pt_VII.ch_3", 500)
    assert A._applies(scope, "c.pt_VII.ch_3.s_203D", 510)
    assert not A._applies(scope, "c.pt_VII.ch_3.s_192", 300)
    assert A._applies(("law", None), "c.s_1", 1)            # a law-wide definition reaches back (Art. 260)


def test_an_amending_law_is_known_by_its_title():
    assert A.AMENDING_TITLE.search("Finance Act, 2006")
    assert A.AMENDING_TITLE.search("Criminal Laws (Amendment) Act, 2016")
    assert not A.AMENDING_TITLE.search("Financial Institutions (Recovery of Finances) Ordinance, 2001")
    assert not A.AMENDING_TITLE.search("Punjab Finance Commission Act")


# --- references -------------------------------------------------------------------------------------------------------
def _refs(text):
    return [(r.kind, r.labels, r.qualifies, r.external) for r in A.references(text)]


def test_references_to_the_same_law():
    assert _refs("subject to the provisions of section 11, become members") == [("unit", ("11",), True, False)]
    assert _refs("Notwithstanding anything contained in sections 4, 8, 9 and 12A, the Government may") == \
        [("unit", ("4", "8", "9", "12A"), True, False)]
    assert _refs("the rules contained in sections 10 to 12 apply") == [("unit", ("10", "11", "12"), False, False)]
    assert _refs("proceedings under section 4 of this Act") == [("unit", ("4",), False, False)]
    assert _refs("the offences in section 9 in Chapter III") == [("unit", ("9",), False, False)]
    assert _refs("as provided in Article 25(1)") == [("unit", ("25",), False, False)]


def test_references_to_another_law_are_not_followed():
    assert _refs("an offence under section 302 of the Pakistan Penal Code") == [("unit", ("302",), False, True)]
    assert _refs("the powers conferred by section 25 of the Act") == [("unit", ("25",), False, True)]
    assert _refs("In the Profession Tax Limitation Act, 1941 (XX of 1941), for section 2 the following") == \
        [("unit", ("2",), False, True)]


def test_schedule_references():
    assert _refs("the goods specified in the Second Schedule") == [("schedule", (2,), False, False)]
    assert _refs("as listed in Schedule II") == [("schedule", (2,), False, False)]
    assert _refs("the fees in the Schedule") == [("schedule", (), False, False)]
    assert _refs("the Schedule to the Pakistan Penal Code") == [("schedule", (), False, True)]
    assert A.schedule_number("FIRST SCHEDULE", None) == 1
    assert A.schedule_number("Schedule-i", None) == 1
    assert A.schedule_number("SCHEDULE 3", None) == 3
    assert A.schedule_number("Schedule", "THE NINTH SCHEDULE") == 9
    assert A.schedule_number("Schedule", None) is None


# --- citations: rendered from records, the server's form (D-070) -------------------------------------------------------
def test_citations_are_rendered_from_records():
    assert A.citation("section", "4", "Punjab Enforcement of Women’s Property Rights Act, 2021") == \
        "Punjab Enforcement of Women’s Property Rights Act, 2021, s. 4"
    assert A.citation("section", "2", "Punjab Act, 2021", chain=(("subsection", "1"), ("clause", "e"))) == \
        "Punjab Act, 2021, s. 2(1)(e)"
    assert A.citation("section", "25", "Constitution of the Islamic Republic of Pakistan", year=1973,
                      law_kind="constitution") == "Constitution of the Islamic Republic of Pakistan, 1973, Art. 25"
    assert A.citation("section", "4", "Code", chain=(("proviso", "Provided"),)) == "Code, s. 4, proviso"
    assert A.citation("schedule", "FIRST SCHEDULE", "Sales Tax Act, 1990") == "Sales Tax Act, 1990, First Schedule"
    assert A.citation("schedule", "19Schedule", "Sales Tax Act, 1990") == "Sales Tax Act, 1990, Schedule"
    assert A.citation("order", "ORDER XXI", "Code of Civil Procedure, 1908") == "Code of Civil Procedure, 1908, Order XXI"
    assert A.citation("section", "4", "") is None
    assert A.citation("section", "", "Some Act") is None


# --- rendering ----------------------------------------------------------------------------------------------------------
def _node(path, kind, label, text, heading=None, ordinal=0):
    return Node(path, path, path, kind, label, heading, None, text, "en", 1, 1, ordinal)


def test_render_keeps_labels_and_the_unit_heading():
    nodes = [_node("p.s_4", "section", "4", "– (1) Any woman may complain:", heading="Complaint"),
             _node("p.s_4.prov_P", "proviso", "Provided", "that the Ombudsperson may act."),
             _node("p.s_4.ss_2", "subsection", "2", "The Ombudsperson shall assess.")]
    assert A.render(nodes, "p.s_4") == ("4. Complaint – (1) Any woman may complain:\n"
                                       "  Provided that the Ombudsperson may act.\n"
                                       "  (2) The Ombudsperson shall assess.")
    # a section whose own node has no words still prints its label and heading
    words_below = [_node("p.s_5.ss_1", "subsection", "1", "No Tribunal shall take cognizance")]
    assert A.render(words_below, "p.s_5", "5. Cognizance").splitlines()[0] == "5. Cognizance"


# --- the budget selector -----------------------------------------------------------------------------------------------
def _cand(key, role, path, size, inst="I"):
    return A._Cand(key, key, inst, role, "r", (), path, size=size)


def test_select_skips_never_cuts_and_always_keeps_the_governing_rule():
    big = _cand("g1", "governing", "a.s_1", 900)
    out, omitted, used = A.select([big, _cand("g2", "governing", "a.s_2", 200)], budget=500, max_units=20)
    assert [c.key for c in out] == ["g1"] and used == 900                       # over budget, but the rule stays
    assert omitted == [{"provision": "g2", "role": "governing", "reason": "budget", "chars": 200}]
    out, omitted, _ = A.select([_cand("g1", "governing", "a.s_1", 100), _cand("g2", "governing", "a.s_2", 600),
                                _cand("g3", "governing", "a.s_3", 100)], budget=300, max_units=20)
    assert [c.key for c in out] == ["g1", "g3"]                                  # a later item that fits still fits


def test_select_does_not_repeat_what_an_admitted_unit_holds():
    out, omitted, used = A.select([_cand("s2", "governing", "a.s_2", 300), _cand("d", "definition", "a.s_2.cl_a", 40)],
                                  budget=1000, max_units=20)
    assert [c.key for c in out] == ["s2"] and omitted[0]["reason"] == "inside s2" and used == 300
    # a whole unit admitted after one of its own clauses replaces the clause, and pays only the difference
    out, omitted, used = A.select([_cand("g", "governing", "a.s_9", 100), _cand("d", "definition", "a.s_2.cl_a", 40),
                                   _cand("s2", "reference", "a.s_2", 300)], budget=1000, max_units=20)
    assert [c.key for c in out] == ["g", "s2"] and used == 400
    assert omitted == [{"provision": "d", "role": "definition", "reason": "inside s2"}]
    # the same path in another law is another provision
    out, _o, _u = A.select([_cand("x", "governing", "a.s_2", 10, inst="I1"), _cand("y", "governing", "a.s_2", 10, inst="I2")],
                           budget=100, max_units=20)
    assert len(out) == 2


def test_select_caps_whole_units_not_definitions():
    cands = [_cand(f"g{i}", "governing", f"a.s_{i}", 10) for i in range(5)] + [_cand("d", "definition", "b.s_2.cl_a", 5)]
    out, omitted, _ = A.select(cands, budget=1000, max_units=3)
    assert [c.key for c in out] == ["g0", "g1", "g2", "d"]
    assert {o["reason"] for o in omitted} == {"unit cap"}
