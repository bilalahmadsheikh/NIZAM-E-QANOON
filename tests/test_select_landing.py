"""tools/acquire/select_landing.py: what is never landed, on titles law.gok.pk actually lists (14 Nov 2026)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "select_landing", Path(__file__).resolve().parents[1] / "tools" / "acquire" / "select_landing.py")
sl = importlib.util.module_from_spec(spec); spec.loader.exec_module(sl)

CLEAN = {"verdict": "clean"}


def row(title, kind="act", pages="4", grade="text"):
    return {"title": title, "kind": kind, "pages": pages, "grade": grade, "sha256": "x", "pdf_url": "u"}


def test_a_clean_ajk_act_is_selected():
    assert sl.exclusion(row("The Azad Jammu and Kashmir Board of Revenue Act, 1993 (ACT III of 1993)"), CLEAN) is None


def test_a_scan_is_never_selected_whatever_the_preflight():
    assert sl.exclusion(row("The Azad Jammu and Kashmir Drugs Ordinance, 1977", grade="scan"), CLEAN).startswith("grade")


def test_blocked_preflight_is_never_selected():
    why = sl.exclusion(row("The Azad Jammu and Kashmir Government Rules of Business, 1971"),
                       {"verdict": "blocked", "s7": "3", "toc_pending": "0", "quality": "passed", "sections": "40"})
    assert why.startswith("preflight blocked")


def test_compiled_volumes_and_indexes_are_left_out():
    assert "volume" in sl.exclusion(row("Final Volume IV", "media", "1051"), CLEAN)
    assert "volume" in sl.exclusion(row("vol5", "media", "993"), CLEAN)
    assert "volume" in sl.exclusion(row("Act 2020", "media", "259"), CLEAN)
    assert sl.exclusion(row("index (XIV) final", "media", "16"), CLEAN).startswith("not a law")


def test_judgments_reports_and_challans_are_not_laws():
    for t in ("2007 SCMR 410 (1)", "privacy breach", "Renewal Challan", "Res 518 NA PAK", "Law Department Manual 2016",
              "Azad Jammu and Kashmir State Judicial Policy, 2018"):
        assert sl.exclusion(row(t, "publication" if "Manual" in t or "Policy" in t else "media"), CLEAN).startswith(
            "not a law"), t


def test_reprinted_federal_codes_are_left_to_their_own_portal_but_ajk_publications_are_kept():
    assert "reprinted" in sl.exclusion(row("Pakistan Penal Code XLV of 1860", "publication", "175"), CLEAN)
    assert "reprinted" in sl.exclusion(row("Punjab Employees Efficiency, Discipline and Accountability Act", "publication"),
                                       CLEAN)
    assert sl.exclusion(row("Azad Jammu and Kashmir Interim Constitution", "publication", "115"), CLEAN) is None


def test_an_amendment_act_whose_title_contains_vol_is_not_a_volume():
    assert sl.exclusion(row("The Azad Jammu and Kashmir Volunteer Force (Amendment) Act, 2017"), CLEAN) is None
