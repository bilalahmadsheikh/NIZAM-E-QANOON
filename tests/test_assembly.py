"""D-107, evidence assembly (docs/04 §7): the pure rules -- whether a definition's scope reaches a unit, how a
citation is rendered from records, and how the budget selector admits, skips and replaces. No database. What a
clause defines and names is nizam.storage.linking's (tests/test_linking.py)."""
from __future__ import annotations

from nizam.retrieval import assembly as A
from nizam.storage.evidence_read import Ancestor, Node


def _anc(path, kind, label="x", depth=None):
    return Ancestor(path, path, kind, label, None, depth if depth is not None else path.count(".") + 1)


# --- read-time scope: does a definition reach this unit? ----------------------------------------------------------
def test_a_chapter_definition_reaches_its_chapter_only():
    assert A._applies(("division", "fed.act.y_o1.ch_3"), "fed.act.y_o1.ch_3.s_12")
    assert not A._applies(("division", "fed.act.y_o1.ch_3"), "fed.act.y_o1.ch_4.s_20")
    assert A._applies(("unit", "fed.act.y_o1.ch_3.s_10"), "fed.act.y_o1.ch_3.s_10")
    assert not A._applies(("unit", "fed.act.y_o1.ch_3.s_10"), "fed.act.y_o1.ch_3.s_11")


def test_a_chapter_definition_reaches_only_the_units_printed_after_it():
    # Constitution Art. 203B ('In this Chapter', the Federal Shariat Court) sits in the tree's Chapter 3 with the
    # High Courts' Articles 192-203 before it: its 'Court' must not reach them (D-107)
    scope = ("division", "c.pt_VII.ch_3", 500)
    assert A._applies(scope, "c.pt_VII.ch_3.s_203D", 510)
    assert not A._applies(scope, "c.pt_VII.ch_3.s_192", 300)
    assert A._applies(("law", None), "c.s_1", 1)            # a law-wide definition reaches back (Art. 260)


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


def test_select_admits_in_priority_order_without_holding_room():
    # D-110: room held for later gated units was measured and rejected; an earlier addition keeps its place
    cands = [_cand("g1", "governing", "a.s_1", 100), _cand("d", "definition", "a.s_2.cl_a", 300),
             _cand("g2", "governing", "a.s_3", 200)]
    out, omitted, _u = A.select(cands, budget=400, max_units=20)
    assert [c.key for c in out] == ["g1", "d"]
    assert omitted == [{"provision": "g2", "role": "governing", "reason": "budget", "chars": 200}]


def test_select_caps_whole_units_not_definitions():
    cands = [_cand(f"g{i}", "governing", f"a.s_{i}", 10) for i in range(5)] + [_cand("d", "definition", "b.s_2.cl_a", 5)]
    out, omitted, _ = A.select(cands, budget=1000, max_units=3)
    assert [c.key for c in out] == ["g0", "g1", "g2", "d"]
    assert {o["reason"] for o in omitted} == {"unit cap"}


def test_sub_question_lexical_support_reads_each_asked_question_by_its_own_words():
    # D-110: a unit supports a sub-question lexically when it carries two of the asked sentence's content terms; the
    # shared context ('We divorced.') is left out, or one unit would support every question. It is a trace, not a
    # verdict: an empty list does not mean unanswered (the law answers in its own words)
    from types import SimpleNamespace as N
    items = [N(unit_id="custody", role="governing", heading="Custody of minor",
               text="The court may appoint a guardian of the person of a minor and order custody."),
             N(unit_id="def", role="definition", heading=None, text="maintenance assessed")]
    out = A.sub_question_coverage(["We divorced. Who gets custody of the minor?",
                                   "We divorced. How is maintenance assessed?"], items)
    assert out[0]["lexical_support"] == ["custody"]
    assert out[1]["lexical_support"] == []                  # a definition never counts as support
    none = A.sub_question_coverage(["عدت کتنی ہے؟"], items)
    assert none[0]["lexical_support"] in (None, [])         # no Latin terms unless the alias index glosses it


def test_no_partial_verdict_is_drawn_from_word_overlap():
    # D-110: on dev the overlap called both real multi-question cases partial and both were answered in other words
    from types import SimpleNamespace as N
    out = A.sub_question_coverage(["Who gets custody? What does the court look at?"],
                                  [N(unit_id="s17", role="governing", heading="Matters to be considered",
                                     text="the court shall be guided by the welfare of the minor")])
    assert set(out[0]) == {"text", "terms", "lexical_support"}
