"""D-105: the legal alias index. An Urdu-language question gains the English words of its legal terms in the lexical
query; an English question is never changed; spelling variants of Roman Urdu meet; Urdu script is read word by word."""
from __future__ import annotations

import pytest

from nizam.retrieval import aliases
from nizam.retrieval.query import parse


@pytest.mark.parametrize("q,expected", [
    ("Talaq ke baad shohar ko notice dena zaroori hai?", {"divorce", "husband"}),
    ("Tallaq ke baad kya hota hai?", {"divorce"}),                                 # a doubled letter folds
    ("Talak ke baad kya hota hai?", {"divorce"}),                                  # k/q fold
    ("Mere haq mehr ki adaigi kab hogi?", {"dower"}),                              # a phrase before its parts
    ("Makan malik mujhe ghar se nikal raha hai kya karun?", {"landlord", "house"}),
    ("Na-qabil-e-zamanat jurm mein zamanat kab mil sakti hai?", {"non-bailable", "bail", "offence"}),
    ("طلاق کے بعد نان نفقہ کون دے گا؟", {"divorce", "maintenance"}),             # Urdu script, punctuation removed
    ("کیا مکان مالک کرایہ بڑھا سکتا ہے؟", {"rent"}),
])
def test_urdu_terms_are_glossed(q, expected):
    assert expected <= set(aliases.gloss(q)), aliases.gloss(q)


@pytest.mark.parametrize("q", [
    "Can my landlord evict me for not paying rent?",
    "What is the punishment for theft under the PPC?",
    "Police custody: how long can I be held before seeing a magistrate?",
    "Is fraud a cognizable offence?",
])
def test_english_questions_are_never_glossed(q):
    assert aliases.gloss(q) == []
    assert parse(q).lexical == parse(q).lexical and parse(q).gloss == []


def test_roman_urdu_is_recognised_by_function_words_not_by_one_word():
    assert aliases.is_urdu("Kya talaq ke baad notice zaroori hai?")
    assert not aliases.is_urdu("Talaq notice under section 7")         # a legal term alone is not a language
    assert aliases.is_urdu("طلاق")


def test_parse_adds_the_gloss_and_keeps_the_question_words():
    s = parse("Kya sood par qarz dena jurm hai?")
    assert {"interest", "loan", "offence"} <= set(s.gloss)
    assert "sood" in s.lexical and "interest" in s.lexical            # Roman Urdu: own words kept, gloss added
    u = parse("کیا سود پر قرض دینا جرم ہے؟")
    assert u.script == "arabic" and u.lexical.split() == u.gloss        # Urdu script: the English index reads the gloss


def test_the_table_has_no_empty_or_duplicate_forms():
    latin, urdu = aliases._LATIN, aliases._URDU
    assert all(k and all(k) for k in list(latin) + list(urdu))
    assert len(latin) > 120 and len(urdu) > 120
