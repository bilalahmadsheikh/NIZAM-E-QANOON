"""D-097, pure: places -> territory, the citation grammar, and when a question's frame is stripped."""
import pytest

from nizam.retrieval.citations import find
from nizam.retrieval.places import places, territory_of
from nizam.retrieval.query import parse


@pytest.mark.parametrize("q,terr", [
    ("My landlord in Lahore wants me out", "punjab"),
    ("Dera Ghazi Khan land dispute", "punjab"),
    ("a court in Mirpur Khas", "sindh"),          # the longer name wins over AJK's Mirpur
    ("I live in Mirpur, AJK", "ajk"),
    ("Khyber Pakhtunkhwa police", "kp"),
    ("Islamabad rent", "ict"),
    ("Quetta property", "balochistan"),
    ("Gilgit land", "gb"),
])
def test_a_place_names_its_territory(q, terr):
    assert territory_of(q) == terr


@pytest.mark.parametrize("q,terr", [
    ("پنجاب میں مالک مکان کرایہ دار کو کن وجوہات پر مکان خالی کروا سکتا ہے؟", "punjab"),
    ("کیا سندھ میں بچوں کی تعلیم مفت اور لازمی ہے؟", "sindh"),
    ("کیا اسلام آباد میں کوئی کمپنی مجھے نوکری دینے سے انکار کر سکتی ہے؟", "ict"),
    ("آزاد کشمیر میں رینٹ کنٹرولر کے فیصلے کے خلاف اپیل کتنے دن میں کی جا سکتی ہے؟", "ajk"),
    ("میرپور خاص میں زمین کا مقدمہ", "sindh"),                 # the longer name wins over AJK's Mirpur
    ("KP mein ghar mein aurat par tashaddud ki saza kya hai?", "kp"),
])
def test_an_urdu_script_place_and_kp_name_their_territory(q, terr):
    # D-109: a question written in Urdu names its place in Urdu
    assert territory_of(q) == terr


def test_no_place_or_two_places_is_no_territory():
    assert territory_of("can my employer fire me") is None
    assert territory_of("a case in Karachi South and Quetta") is None      # a comparison: never guessed


def test_ordinary_words_are_not_districts():
    assert places("a tank of water near the hub of the bagh") == []
    assert places("lahore in lower case is not taken") == []                 # case-sensitive by design


@pytest.mark.parametrize("q,label,subs,law", [
    ("What is the punishment under s. 302 PPC?", "302", [], "ppc"),
    ("bail under section 497(5) CrPC", "497", ["5"], "crpc"),
    ("PPC 302", "302", [], "ppc"),
    ("crpc 497", "497", [], "crpc"),
    ("what does s.337A of the Pakistan Penal Code say", "337A", [], "ppc"),
    ("PPC 462 I. electricity theft", "462 I", [], "ppc"),
    ("under sec 489-F PPC cheque", "489-F", [], "ppc"),
    ("Article 199 of the Constitution", "199", [], "constitution"),
    ("section 9 of the Code of Civil Procedure, 1908 says", "9", [], "cpc"),
    ("section 17 of the Qanun-e-Shahadat, 1984", "17", [], "qso"),
    ("section 15 of the Punjab Rented Premises Act, 2009", "15", [], "Punjab Rented Premises Act, 2009"),
    ("section 3 of the Dowry and Bridal Gifts (Restriction) Act, 1976", "3", [],
     "Dowry and Bridal Gifts (Restriction) Act, 1976"),
    ("section 3 of the Workmen’s Compensation Act, 1923", "3", [], "Workmen’s Compensation Act, 1923"),
    ("section 9 of the Zainab Alert, Response and Recovery Act, 2020", "9", [],
     "Zainab Alert, Response and Recovery Act, 2020"),
])
def test_the_citation_grammar(q, label, subs, law):
    c = find(q)[0]
    assert (c.label, c.subs, c.law) == (label, subs, law)


def test_what_is_not_a_citation_is_not_read_as_one():
    assert find("I paid Rs. 500 in 2019 for 3 years") == []                 # the 's.' of 'Rs.'
    assert find("Order 39 CPC") == [] and find("O. 39 r. 1 CPC") == []      # CPC Order/Rule numbering
    assert find("Article 199 writ")[0].law is None                          # no law named: typed ambiguity
    assert find("section 5 of the Act")[0].law is None                      # 'the Act' depends on context
    assert find("302 PPC")[0].label == "302"                                # the label never eats the alias


def test_only_a_sentence_loses_its_frame():
    q = parse("My landlord in Lahore wants me out of the house I rent. On what grounds can he evict me?")
    assert q.sentence and "my" not in q.lexical.lower().split() and q.territory == "punjab"
    short = parse("grounds for eviction")
    assert not short.sentence and short.lexical == "grounds for eviction"
    assert parse("talaq کب واقع ہوتی ہے").script == "arabic"
