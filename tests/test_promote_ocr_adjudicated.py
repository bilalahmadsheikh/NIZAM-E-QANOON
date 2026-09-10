"""The E4 confidence convention, which decides whether Q1 can ever pass.

`document.printable_ratio` holds two different quantities depending on lane: the
printable-character ratio for E1-E3, and the word-weighted mean OCR confidence
for E4 (`nizam/corpus/ocr.py`), which is the number `verify_ocr` tests against
the 0.70 floor. A promoted revision that computed this any other way would leave
Q1 failing on text that is actually correct, so the weighting is worth pinning.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[1] / "tools" / "promote_ocr_adjudicated.py"
_spec = importlib.util.spec_from_file_location("promote_ocr_adjudicated", _MODULE)
promote = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(promote)

weighted_confidence = promote.weighted_confidence


def test_weights_by_words_not_by_block():
    """A long confident block outweighs a short doubtful one.

    Weighting by block would average 0.99 and 0.10 to 0.545 and drag a good
    page under the floor on the strength of one stray caption.
    """
    pairs = [("alpha beta gamma delta epsilon zeta eta theta iota kappa", 0.99),
             ("x", 0.10)]
    mean, words = weighted_confidence(pairs)
    assert words == 11
    assert mean == pytest.approx((0.99 * 10 + 0.10 * 1) / 11)
    assert mean > 0.9


def test_blocks_without_confidence_count_words_but_not_confidence():
    """A block with no confidence is text, not a zero-confidence reading.

    Counting it as 0.0 would punish a revision for carrying a block the engine
    declined to score; dropping its words from `ocr_words` would understate the
    document. It contributes to one total and not the other.
    """
    mean, words = weighted_confidence([("one two", 0.80), ("three four", None)])
    assert words == 4
    assert mean == pytest.approx(0.80)


def test_empty_input_is_zero_not_an_error():
    """A document with no text is a state the corpus records, not an exception."""
    assert weighted_confidence([]) == (0.0, 0)


def test_all_blocks_unscored_is_zero_confidence():
    """No scored block means no evidence of quality, which must not read as 1.0."""
    mean, words = weighted_confidence([("alpha", None), ("beta", None)])
    assert words == 2
    assert mean == 0.0


def test_matches_the_ocr_worker_on_a_uniform_page():
    """With one confidence throughout, the mean is that confidence exactly.

    This is the case that must agree with `nizam/corpus/ocr.py`, so a promoted
    revision is comparable with an originally-OCR'd one rather than merely close.
    """
    pairs = [("alpha beta", 0.9584), ("gamma", 0.9584), ("delta epsilon", 0.9584)]
    mean, words = weighted_confidence(pairs)
    assert words == 5
    assert mean == pytest.approx(0.9584)


def test_urdu_words_are_counted():
    """The tokenizer is Unicode-aware: Nastaliq text must not weigh zero.

    Every Q1 Urdu document would otherwise promote to a 0.0 confidence and stay
    in review no matter how good the reading was.
    """
    mean, words = weighted_confidence([("قانون نظام", 0.95)])
    assert words == 2
    assert mean == pytest.approx(0.95)
