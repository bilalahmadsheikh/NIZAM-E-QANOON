"""tools/urdu/textlayer_check.py: the letter multiset survives the Sindh Urdu text layer's scrambled order."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "urdu"))
import textlayer_check as t  # noqa: E402


def test_scrambled_order_scores_as_the_same_letters():
    # text layer of PUB-NEW-23-000001-UR p1 ('دنسھ', 'رشع', '8102') against the printed words
    layer = "دنسھ زوکات اور رشع 8102"
    printed = "سندھ زکوٰۃ اور عشر 2018"
    s = t.prf(t.letters(layer), t.letters(printed))
    assert s["f1"] == 1.0, s
    assert t.prf(t.digits(layer), t.digits(printed))["f1"] == 1.0


def test_a_dropped_or_added_word_lowers_the_score():
    ref = t.letters("سندھ زکوٰۃ اور عشر")
    assert t.prf(ref, t.letters("سندھ زکوٰۃ عشر"))["recall"] < 1.0
    assert t.prf(ref, t.letters("سندھ زکوٰۃ اور عشر ترمیمی"))["precision"] < 1.0


def test_urdu_digits_and_presentation_forms_fold():
    assert t.digits("۲۰۱۹") == t.digits("2019")
    assert t.letters("ﻟﻠ") == t.letters("لل")      # presentation forms of lam
