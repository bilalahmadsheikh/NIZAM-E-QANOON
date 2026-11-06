"""Ordinance -> same-title later Act links (migration 0067, tools/record_instrument_supersession.py)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ris", Path(__file__).resolve().parents[1] / "tools" / "record_instrument_supersession.py")
ris = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ris)


def inst(i, kind, year, title, jur="federal"):
    return {"id": str(i), "kind": kind, "year": year, "title": title, "jurisdiction": jur}


def test_title_key_folds_the_and_kind_and_year():
    assert ris.title_key("The Cotton Ordinance, 1956") == ris.title_key("Cotton Act, 1957") == "cotton"
    assert ris.title_key("Sind Rented Premises Ordinance, 1979") == "sindhrentedpremises"


def test_one_later_act_pairs():
    pairs, amb = ris.plan([inst(1, "ordinance", 1956, "The Cotton Ordinance, 1956"),
                           inst(2, "act", 1957, "Cotton Act, 1957")])
    assert [(o["id"], a["id"]) for o, a in pairs] == [("1", "2")] and amb == 0


def test_earlier_act_other_jurisdiction_or_two_acts_do_not_pair():
    pairs, amb = ris.plan([inst(1, "ordinance", 1960, "The Jute Control Ordinance, 1960"),
                           inst(2, "act", 1957, "The Jute Control Act, 1957"),
                           inst(3, "act", 1961, "The Jute Control Act, 1961", jur="punjab")])
    assert pairs == [] and amb == 0
    pairs, amb = ris.plan([inst(1, "ordinance", 1960, "The Jute Control Ordinance, 1960"),
                           inst(2, "act", 1961, "The Jute Control Act, 1961"), inst(3, "act", 1965, "The Jute Control Act, 1965")])
    assert pairs == [] and amb == 1


def test_amendment_ordinance_pairs_only_within_a_year():
    base = [inst(1, "ordinance", 2001, "The Customs (Amendment) Ordinance, 2001")]
    assert ris.plan(base + [inst(2, "act", 2005, "The Customs (Amendment) Act, 2005")])[0] == []
    assert len(ris.plan(base + [inst(2, "act", 2002, "The Customs (Amendment) Act, 2002")])[0]) == 1


def test_names_ordinance_in_act_text():
    o = inst(1, "ordinance", 1961, "The Trade Organizations Ordinance, 1961")
    assert ris.names_ordinance(ris.fold("The Trade Organizations Ordinance, 1961 (XLV of 1961) is hereby repealed."), o)
    assert not ris.names_ordinance(ris.fold("The Trade Organizations Ordinance, 2007 is repealed."), o)
