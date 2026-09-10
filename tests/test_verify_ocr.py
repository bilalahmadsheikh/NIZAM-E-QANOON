"""OCR verification must apply equally to Latin and Arabic-script output."""

from nizam.workers.verify_ocr import _words_per_page


def test_yield_uses_recorded_ocr_words_not_english_regex_tokens():
    # 240 Urdu words over four pages are still 60 words/page even when an
    # English-only legal vocabulary would find zero tokens.
    assert _words_per_page("240", 4) == 60


def test_missing_or_zero_page_metadata_is_safe():
    assert _words_per_page(None, 4) == 0
    assert _words_per_page("not-a-number", 4) == 0
    assert _words_per_page(100, 0) == 0
