"""The independent extractor gate must distinguish evidence from hints."""
from nizam.workers.verify_extraction import (
    REPLACEMENT_GLYPH, _chars, _tokens, _unexplained_extra, credit_stripped_replacement,
)


def test_character_comparison_ignores_typographic_spacing_only():
    assert _chars("1Substituted") == _chars("1 Substituted")
    assert _chars("section 10") != _chars("section 11")


def test_token_counter_cannot_claim_reading_order():
    # Equal counters have deliberately forgotten sequence.  A low counter
    # overlap may be a useful hint, but this representation cannot prove order.
    assert _tokens("alpha beta") == _tokens("beta alpha")


def test_decoder_specific_control_and_private_use_glyphs_are_not_legal_text():
    assert _chars("law\x12\uf0a8") == _chars("law")


def test_confidence_labelled_ocr_is_not_called_pdf_decoder_fabrication():
    assert not _unexplained_extra(
        "born digital OCR evidence", "born digital", "", "OCR evidence"
    )
    assert _unexplained_extra(
        "born digital invented", "born digital", "", ""
    ) == _chars("invented")


def test_stripped_replacement_glyphs_are_credited_only_up_to_the_reviewed_count():
    # doc 9862 (4994 p13): the source font prints 29 empty boxes, which Poppler also reads as U+FFFD
    ref = _chars("Topics " + REPLACEMENT_GLYPH * 29 + " Leadership")
    ours = _chars("Topics Leadership")
    missing = ref - ours
    total = sum(ref.values())
    assert credit_stripped_replacement(missing, total, 29) == 1.0
    assert credit_stripped_replacement(missing, total, 28) == (total - 1) / total


def test_stripped_replacement_credit_never_covers_lost_letters():
    ref = _chars("Topics " + REPLACEMENT_GLYPH * 3 + " Leadership")
    ours = _chars("Topics Leader")
    missing = ref - ours
    total = sum(ref.values())
    assert credit_stripped_replacement(missing, total, 99) == (total - len("ship")) / total
