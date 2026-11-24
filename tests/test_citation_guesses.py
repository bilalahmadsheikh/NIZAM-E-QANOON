"""The citation resolver never guesses a law (D-127): a kind word is not a name, and a printed year must agree.

Pure tests over a stand-in session; the real lookups are measured by evals/citation_resolution.py."""
from __future__ import annotations

from nizam.storage import citations as C
from nizam.storage.unit_search import Unit


class Session:
    """Titles as the title search would return them (best first), every one holding the labels asked for."""

    def __init__(self, titles, aliases=None):
        self.titles = titles
        self.asked = []
        self.aliases = aliases or {}

    def law_alias(self, key):
        return self.aliases.get(key)

    def instruments_titled(self, words, n, juris):
        self.asked.append(words)
        w = [x for x in words.lower().replace(",", " ").split() if x not in ("the", "of")]
        return [(f"id{i}", t, 0) for i, t in enumerate(self.titles)
                if all(x in t.lower().replace(",", " ").split() for x in w)][:n]

    def label_units(self, label, ids):
        return [Unit(f"{ids[0]}:{label}", "p", ids[0])]

    def child_by_label(self, unit, subs):
        return unit


TITLES = ["Trusts Act, 1882", "Arbitration Act, 1940", "Trade Organizations Act, 2013",
          "The Azad Jammu and Kashmir Family Courts Act, 1993", "West Pakistan Family Courts Act, 1964"]


def test_a_kind_word_alone_names_no_law_and_is_not_looked_up():
    for law in ("Act.", "ACT.", "Act, 2013", "the Act, 1940", "Amending Act", "the said Ordinance of 1979", "Rules"):
        s = Session(TITLES)
        r = C.resolve(s, C.Citation("x", "14", [], law))
        assert r.resolved_unit is None and r.unresolved.startswith("no law named"), law
        assert s.asked == []


def test_a_printed_year_must_agree_with_the_year_in_the_title():
    s = Session(TITLES)
    r = C.resolve(s, C.Citation("x", "17", [], "Family Courts Act of 1964"))
    assert r.resolved_law == "West Pakistan Family Courts Act, 1964"
    s = Session(["The Azad Jammu and Kashmir Family Courts Act, 1993"])
    r = C.resolve(s, C.Citation("x", "17", [], "Family Courts Act of 1964"))
    assert r.resolved_unit is None                                     # the only same-named law is of 1993


def test_a_distinctive_name_still_resolves_and_a_title_without_a_year_is_not_refused():
    assert C.resolve(Session(TITLES), C.Citation("x", "6", [], "Trusts Act, 1882")).resolved_law == "Trusts Act, 1882"
    r = C.resolve(Session(["Pakistan Penal Code"]), C.Citation("x", "302", [], "Pakistan Penal Code, 1860"))
    assert r.resolved_law == "Pakistan Penal Code"


# ---------------------------------------------------------------- D-134: the title's end, and reviewed aliases
def _one(text):
    found = C.find(text)
    assert len(found) == 1, found
    c = found[0]
    assert text[c.start:c.end] == c.raw                     # the span printed is exactly the raw kept
    return c


def test_a_title_stops_at_its_sentence_end_and_keeps_the_stop():
    c = _one("under section 3 of the Limitation Act. It is clear that")
    assert c.raw == "section 3 of the Limitation Act." and c.law == "Limitation Act."
    c = _one("section 4 of the Act. He argued")                   # still only a kind of law (D-127)
    assert c.law == "Act." and C.resolve(Session(TITLES), c).unresolved.startswith("no law named")
    c = _one("section 13 of the N.-W.F.P. Pre-emption Act, 1987 was")   # a dotted name inside a title is not a stop
    assert c.law == "N.-W.F.P. Pre-emption Act, 1987"
    assert _one("under section 154 of the Code of Criminal Procedure. However, the").law == "crpc"
    assert _one("section 6 of the Representation of the People Act, 1976. However").law == \
        "Representation of the People Act, 1976"


def test_a_title_stops_where_the_next_citation_begins_and_a_swallowed_sub_clause_is_dropped():
    found = C.find("section 24-A of the General Clauses Act and Article 4 of the Constitution")
    assert [c.law for c in found] == ["General Clauses Act", "constitution"]
    found = C.find("section 3 of the Limitation Act, Section 5 aside")
    assert [(c.label, c.law) for c in found] == [("3", "Limitation Act"), ("5", None)]
    found = C.find("as stipulated in Article 8(1) and (2) of the Constitution. Therefore")
    assert found[0].law == "constitution" and found[0].label == "8"


def test_trailing_parentheses_are_an_act_number_or_a_short_name_not_title_words():
    assert _one("section 115 of the Code of Civil Procedure (V of 1908) is").law == "cpc"
    assert _one("section 302 of the Pakistan Penal Code (Act XLV of 1860)").law == "ppc"
    c = _one("section 9 of the Financial Institutions (Recovery of Finances) Ordinance (“FIO”), the")
    assert c.law == "Financial Institutions (Recovery of Finances) Ordinance"   # inner parentheses are title words
    assert _one("u/s 544-A of the Code of Criminal Procedure (Cr.P.C.) and in default").law == "crpc"
    # a year printed only inside the parentheses is kept: the 2003 Ordinance, not the 1998 or 2004 one
    assert _one("section 5 of the Contempt of Court Ordinance (Ordinance V of 2003) with").law == \
        "Contempt of Court Ordinance, 2003"


def test_a_citation_inherits_a_law_only_when_bare_or_naming_the_same_kind():
    from nizam.storage import judgment_linking as JL
    assert _one("in terms of section 25 of the Hisba Bill was").named == "other"
    assert _one("under section 3 of the Ordinance the").named == "kind:ordinance"
    assert _one("under section 497(2) the").named is None                 # bare: nothing printed after it
    assert JL.may_inherit(None, "pc act") is True
    assert JL.may_inherit("other", "NAB Ordinance") is False                # the Hisba Bill is not the NAB Ordinance
    assert JL.may_inherit("kind:ordinance", "NAB Ordinance") is True
    assert JL.may_inherit("kind:ordinance", "PC Act") is False              # an Ordinance is not the PC Act
    assert JL.may_inherit("kind:order", "Qanoon-e-Shahadat Order, 1984") is True
    assert JL.may_inherit("kind:order", "qso") is True and JL.may_inherit("kind:code", "crpc") is True


def test_two_titles_are_one_law_in_two_copies_only_when_their_words_agree_and_no_printed_year_differs():
    assert C.same_law("Pakistan Penal Code", "Pakistan Penal Code, 1860")
    assert C.same_law("Qanun-e-Shahadat, 1984", "Qanun-E-Shahadat Order, 1984")
    assert C.same_law("Contract Act, 1872", "The Contract Act, 1872")
    assert not C.same_law("Industrial Relations Act, 2008", "Industrial Relations Act, 2012")
    assert not C.same_law("Industrial Relations Act, 2012", "Industrial Relations Ordinance, 2012")
    assert not C.same_law("Pakistan Penal Code", "Penal Code (West Pakistan Amendment) Act, 1964")


def test_a_copys_unit_is_the_same_provision_only_by_heading_or_words():
    from nizam.storage import judgment_linking as JL
    cheque = "Whoever dishonestly issues a cheque towards repayment of a loan or fulfilment of an obligation"
    prize = "Whoever sells, buys or deals in prize bonds or draws a lottery on prize bonds shall be punished"
    assert not JL.same_provision("Dishonestly issuing a cheque", "Prize bond lotteries", cheque, prize)
    assert JL.same_provision("1[Dishonestly issuing a cheque]", "Dishonestly issuing a cheque.", cheque, cheque)
    # same heading, words amended in one province: still the one provision
    assert JL.same_provision("Interim order for maintenance", "Interim order for maintenance",
                             "the Family Court may pass an interim order for maintenance at any stage",
                             "at the first appearance the Family Court shall fix interim maintenance rising ten "
                             "per cent annually")
    assert JL.same_provision("", "", cheque, cheque + " shall be punished")          # no headings: the words decide
    assert not JL.same_provision("", "", cheque, prize)
    rape = "Whoever commits rape shall be punished with death or imprisonment for a term"
    assert JL.same_provision("Punishment for rape", "Punishment of rape", rape, rape + " of not less than ten years")
    assert JL.same_provision("Insulting modesty or causing sexual harassment",
                             "Word, gesture or act intended to insult the modesty of a woman",
                             "Whoever intending to insult the modesty of any woman, or conducts sexual advances",
                             "Whoever, intending to insult the modesty of any woman, utters any word")
    assert not JL.same_provision("[Omitted]", "Definitions", "", "In this Act, unless")        # nothing to read


def test_a_stopped_kind_word_refers_back_by_kind_and_year_and_an_amending_act_never_does():
    from nizam.storage import judgment_linking as JL
    assert JL.back_reference("Act.") == ("kind:act", None)
    assert JL.back_reference("the said Ordinance of 1979") == ("kind:ordinance", "1979")
    assert JL.back_reference("Act, 2013") == ("kind:act", "2013")
    for other in ("Amending Act", "the principal Act", "the repealed Ordinance", "Land Acquisition Act", "Rules of"):
        assert JL.back_reference(other) is None, other
    assert JL.may_inherit("kind:act", "Land Acquisition Act, 1894") is True          # 'section 55 of the Act.'
    assert JL.may_inherit("kind:act", "Arbitration Act, 1940", "1940") is True       # 'section 14 of the Act, 1940'
    assert JL.may_inherit("kind:act", "Trusts Act, 1882", "1940") is False           # another year, another law
    assert JL.may_inherit("kind:act", "ppc") is False                                # the PPC is a Code


def test_law_key_folds_spelling_noise_but_keeps_the_words_and_the_year():
    assert C.law_key("Qanoon-e- Shahadat Order, 1984") == C.law_key("the Qanoon-e-Shahadat Order 1984") \
        == "qanoon e shahadat order 1984"
    assert C.law_key("NAB Ordinance") != C.law_key("NAB Ordinance, 1999")
    assert C.law_key("“ITO”, 2001") == "ito 2001"


def test_a_reviewed_alias_resolves_to_its_law_and_an_unreviewed_name_does_not():
    titles = ["Income Tax Ordinance, 2001", "Income Tax Ordinance, 1979"]
    s = Session(titles, {"ito 2001": ("Income Tax Ordinance, 2001", ("fed",))})
    r = C.resolve(s, C.Citation("x", "122", [], "ITO, 2001"))
    assert r.resolved_law == "Income Tax Ordinance, 2001" and r.via_alias == "ito 2001"
    r = C.resolve(Session(titles), C.Citation("x", "122", [], "ITO, 2001"))      # no reviewed row: not guessed
    assert r.resolved_unit is None and r.via_alias is None
    r = C.resolve(s, C.Citation("x", "122", [], "ITO, 1979"))                    # another key, another law
    assert r.resolved_unit is None
