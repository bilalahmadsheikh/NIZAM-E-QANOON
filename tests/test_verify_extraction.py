"""The independent extractor gate must distinguish evidence from hints."""
from nizam.workers.verify_extraction import _chars, _tokens, _unexplained_extra


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
