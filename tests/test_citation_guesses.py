"""The citation resolver never guesses a law (D-127): a kind word is not a name, and a printed year must agree.

Pure tests over a stand-in session; the real lookups are measured by evals/citation_resolution.py."""
from __future__ import annotations

from nizam.storage import citations as C
from nizam.storage.unit_search import Unit


class Session:
    """Titles as the title search would return them (best first), every one holding the labels asked for."""

    def __init__(self, titles):
        self.titles = titles
        self.asked = []

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
