from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

from scraper_paths import short_pdf_filename


def test_staging_name_is_short_ascii_and_stable_for_extreme_legal_title_url():
    url = ("https://punjabcode.punjab.gov.pk/uploads/articles/" +
           "PUNJAB-SOCIAL-WELFARE-AND-BAIT-UL-MAAL-" * 30 + ".pdf")
    first = short_pdf_filename(url)
    second = short_pdf_filename(url)

    assert first == second
    assert first.startswith("download-") and first.endswith(".pdf")
    assert len(first) == 37
    assert first.isascii()


def test_different_official_urls_do_not_collapse_to_one_staging_name():
    assert short_pdf_filename("https://official/a.pdf") != short_pdf_filename(
        "https://official/b.pdf")
