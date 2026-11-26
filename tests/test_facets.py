"""subject_matter by title rule (D-163): decided by the title or left unassigned, never guessed."""
from __future__ import annotations

from nizam.storage.facets import VOCABULARY, subjects_of


def values(t):
    return [v for v, _ in subjects_of(t)]


def test_a_title_that_decides_its_subject():
    assert values("The Dissolution of Muslim Marriages Act, 1939") == ["family"]
    assert values("West Pakistan Family Courts Act, 1964") == ["family"]
    assert "tax" in values("Income Tax Ordinance, 2001")
    assert "finance_banking" in values("Financial Institutions (Recovery of Finances) Ordinance, 2001")
    assert "criminal" in values("Pakistan Penal Code (XLV of 1860)")
    assert values("Constitution of the Islamic Republic of Pakistan") == ["constitutional"]
    assert "constitutional" in values("Constitution (Twenty-sixth Amendment) Act, 2024")


def test_the_misreadings_a_sample_found_are_refused():
    assert "constitutional" not in values("Sindh Criminal Prosecution Service (Constitution, Functions and Powers) Act")
    assert "criminal" in values("Sindh Criminal Prosecution Service (Constitution, Functions and Powers) Act")
    assert "labour_employment" not in values("Sugar Factories Control (Sindh Amendment) Act, 1994")
    assert "health" not in values("Public Health Engineering Department Service Rules")
    assert "property_land" not in values("Land Customs Act, 1924")


def test_the_apis_subject_list_is_the_vocabulary():
    import typing

    from nizam.api.precedent import SUBJECTS
    assert set(typing.get_args(SUBJECTS)) - {""} == set(VOCABULARY)


def test_a_title_that_decides_nothing_is_unassigned_and_values_are_the_vocabulary():
    assert values("The Carriage By Air Act, 1934") == []
    assert all(v in VOCABULARY for t in ("Banking Companies Ordinance", "Road Transport Workers Ordinance")
               for v in values(t))
    assert len(subjects_of("Liaquat University of Medical and Health Sciences Ordinance")) <= 3
