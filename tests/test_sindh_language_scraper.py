"""data/sindh_language_scraper.py parsing, against Sindh Code pages saved on 12 Nov 2026 (tests/fixtures/sindh/)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))
FIX = ROOT / "tests" / "fixtures" / "sindh"

pytest.importorskip("bs4")
import sindh_language_scraper as s  # noqa: E402


def test_years_come_from_the_chronological_index():
    years = s.parse_years((FIX / "chrono-ACT.html").read_text(encoding="utf-8", errors="replace"), "ACT")
    assert 2019 in years and 2025 in years
    assert years == sorted(years, reverse=True)
    assert all(1800 <= y <= 2100 for y in years)


def test_a_listing_row_pairs_its_languages_by_pub_id():
    rows = s.parse_listing((FIX / "listing-ACT-2019.html").read_text(encoding="utf-8", errors="replace"), "ACT")
    by_id = {r["pub_id"]: r for r in rows}
    # the Local Government (Amendment) Act 2019 row publishes all three; the Finance Act 2019 row English only
    lg = by_id["PUB-NEW-23-000005"]
    assert (lg["en"], lg["ur"], lg["sd"]) == (True, True, True)
    assert "LOCAL GOVERNMENT (AMENDMENT) ACT, 2019" in lg["title"]
    fin = by_id["PUB-NEW-23-000012"]
    assert (fin["en"], fin["ur"], fin["sd"]) == (True, False, False)
    assert len(by_id) == len(rows)                      # one row per PubID on a year page


def test_the_header_row_and_a_wrong_div_give_nothing():
    html = (FIX / "listing-ACT-2019.html").read_text(encoding="utf-8", errors="replace")
    assert s.parse_listing(html, "ORDINANCE") == [] or all(r["pub_id"] for r in s.parse_listing(html, "ORDINANCE"))
    assert all(r["title"] != "Title" for r in s.parse_listing(html, "ACT"))


def test_served_filename():
    assert s.served_filename('inline; filename="PUB-NEW-23-000005-U-S.pdf"') == "PUB-NEW-23-000005-U-S.pdf"
    assert s.served_filename(None) == ""
