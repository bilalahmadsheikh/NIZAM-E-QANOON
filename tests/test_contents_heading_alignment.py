"""Profile rule `contents_heading_alignment`: a contents list at an offset.

docs/SEGMENTATION-PROFILES.md. Doc 1014 (Sind Teaching, Promotion and Use of
Sindhi Language Act 1972) prints a contents row "3. Constitution of Governing
Body" that its body does not have, and every later row runs one ahead of the
body: body section 3 is "Provincial Language", the contents' row 4. Doc 1486
skips 4, so rows 5-16 name body sections 4-15. The default parser links rows
by number, so each unit in the run carries the next row's heading and the
body's own heading lines are read as the previous unit's text.

Under `unreleased-v1` the rows are aligned by the heading each unit prints,
the units are named by their own printed headings, and a row naming no unit
is left unlinked for a page-read adjudication. Nothing citable changes. The
default parser is untouched: every stored document in the parser-drift
fixture rebuilds identically under the profile.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nizam.corpus import segment as S

FIXTURE = Path(__file__).parent / "fixtures" / "contents-offset.json"
DRIFT = Path(__file__).parent / "fixtures" / "parser-drift-repair.json"
_CACHE: dict = {}


def _case(document: str) -> dict:
    if not _CACHE:
        _CACHE.update(json.loads(FIXTURE.read_text(encoding="utf-8")))
    return _CACHE[document]


def _links(seg) -> list[tuple[str, str | None, str]]:
    return [(e["label"], e["node"].label if e["node"] is not None else None,
             e["method"]) for e in seg.toc_entries]


def _headings(seg) -> dict[str, str]:
    return {n.label: (n.heading or "").rstrip(".")
            for n in seg.flatten() if n.kind == "section"}


def _citable(seg) -> list[tuple[str, str]]:
    return [(n.kind, n.label) for n in seg.flatten()
            if n.kind in ("section", "article")]


def test_printed_heading_matches():
    assert S._printed_heading_matches("Teaching of Sindhi.", "Teaching of Sindhi.")
    assert S._printed_heading_matches(
        "Definitions.- In this Act, unless the context otherwise requires",
        "Definitions.")
    # the first printed word must agree
    assert not S._printed_heading_matches("Promotion of Sindhi.", "Sindhi Promotion of.")
    # too short to name anything
    assert not S._printed_heading_matches("Act.", "Act.")
    assert not S._printed_heading_matches("Power to make rules.",
                                          "Power of entry and inspection.")


def test_default_profile_links_by_number():
    seg = S.segment(_case("1014")["blocks"])
    assert seg.contents_alignment is None
    assert _links(seg)[2][:2] == ("3", "3")
    assert _links(seg)[7][:2] == ("8", None)
    assert _headings(seg)["3"] == "Constitution of Governing Body"


def test_1014_rows_follow_the_printed_headings():
    default = S.segment(_case("1014")["blocks"])
    seg = S.segment(_case("1014")["blocks"], profile="unreleased-v1")
    assert seg.contents_alignment == {"0": "1", "1": "2", "2": None, "3": "3",
                                      "4": "4", "5": "5", "6": "6", "7": "7"}
    assert [(label, node) for label, node, _ in _links(seg)] == [
        ("1", "1"), ("2", "2"), ("3", None), ("4", "3"), ("5", "4"),
        ("6", "5"), ("7", "6"), ("8", "7")]
    assert _links(seg)[2][2] == "unmatched"
    assert _headings(seg) == {
        "1": "Short title, commencement and extent", "2": "Definition",
        "3": "Provincial Language", "4": "Teaching of Sindhi",
        "5": "Sindhi Promotion of", "6": "Use of Sindhi",
        "7": "Power to make rules"}
    section_3 = next(n for n in seg.flatten() if n.label == "3")
    assert "Teaching of Sindhi" not in section_3.text
    # renamed and relinked, never restructured
    assert _citable(seg) == _citable(default)
    # the unlinked row is still reported, by its printed number
    assert "3" in seg.missing


def test_1486_every_row_links():
    default = S.segment(_case("1486")["blocks"])
    seg = S.segment(_case("1486")["blocks"], profile="unreleased-v1")
    assert sum(1 for _, node, _ in _links(default) if node is None) == 1
    assert all(node is not None for _, node, _ in _links(seg))
    assert ("5", "4") in [(label, node) for label, node, _ in _links(seg)]
    assert ("16", "15") in [(label, node) for label, node, _ in _links(seg)]
    assert _headings(seg)["4"] == "Appeal"
    assert _headings(seg)["15"] == "Power to make rules"
    assert _citable(seg) == _citable(default)


def test_2803_every_row_names_the_rule_that_prints_its_heading():
    """Rows 2-13 name rules 3-14 and rows 14-25 rules 16-27; row 1 has no
    heading evidence either way and keeps its number. The body's own, longer
    headings are kept whole (`printed_heading_extent`)."""
    case = _case("2803")
    default = S.segment(case["blocks"], curation_patches=case["patches"])
    seg = S.segment(case["blocks"], curation_patches=case["patches"],
                    profile="unreleased-v1")
    links = {label: node for label, node, _ in _links(seg)}
    assert links["1"] == "1" and links["2"] == "3" and links["13"] == "14"
    assert links["14"] == "16" and links["25"] == "27"
    assert all(node is not None for node in links.values())
    rules = {n.label: n for n in seg.flatten() if n.kind == "section"}
    assert rules["2"].heading is None                    # definitions: none printed
    assert rules["9"].heading == ("Amendment of correct valuation list and the "
                                  "filling of objections thereto")
    assert rules["9"].text.startswith("The notice under the proviso")
    assert rules["17"].heading == "Recovery of tax from tenants"
    assert rules["17"].text.startswith("The notice provided by section 14")
    assert rules["15"].heading is None                   # the contents lists no rule 15
    assert _citable(seg) == _citable(default)


def test_printed_heading_extent():
    flat = ("Amendment of correct valuation list and the filling of objections "
            "thereto.- The notice under the proviso to Section 9")
    assert S._printed_heading_extent(flat, len("Amendment of correct valuation")) == (
        "Amendment of correct valuation list and the filling of objections thereto",
        "The notice under the proviso to Section 9")
    # the contents' name already reaches the body's terminator: default path
    assert S._printed_heading_extent("Assessing Authority.- (1) A", 19) is None
    # operative words are text, not heading
    assert S._printed_heading_extent(
        "Definitions In this Act the Board shall mean. It", 11) is None
    # a sub-section after the name is text
    assert S._printed_heading_extent("Appeal (1) An appeal shall lie.", 6) is None
    assert S._printed_heading_line(
        "Collection of tax through tax-collecting staff.",
        "Collection of Tax through Tax Collection Staff") == (
        "Collection of tax through tax-collecting staff")
    assert S._printed_heading_line(
        "Any person may appeal.", "Appeal") is None


@pytest.mark.parametrize("document",
                         sorted(json.loads(DRIFT.read_text(encoding="utf-8"))))
def test_stored_documents_are_untouched_by_the_profile(document):
    case = json.loads(DRIFT.read_text(encoding="utf-8"))[document]
    resolutions = case["structural_resolutions"] or None
    overrides: dict = {}
    for row in resolutions or []:
        overrides.update((row.get("evidence") or {}).get("structural_overrides") or {})
    kwargs = dict(structural_resolutions=resolutions,
                  structural_overrides=overrides or None,
                  detect_contents=case["window_pages"] is None)
    default = S.segment(case["blocks"], **kwargs)
    profiled = S.segment(case["blocks"], profile="unreleased-v1", **kwargs)
    assert profiled.contents_alignment is None
    assert _links(profiled) == _links(default)
    expected = dict(_headings(default))
    expected.update(KNOWN_REPAIRS.get(document, {}))
    assert _headings(profiled) == expected


# Defects in stored (released) trees that a profile rule repairs. Released
# documents are never pinned, so these repairs do not reach the corpus; they
# are listed for the released-correctness lane.
KNOWN_REPAIRS = {
    # s.21 opens "The provisions of the ... Ordinance, 2002 (Ordinance No.
    # LXXXIV ..." and the first-sentence guess cut its heading at "No."
    "252": {"21": "Repeal"},
    # s.1's heading is its own enacting sentence "This Act, may be called the
    # Municipal Taxation Act, 1881"; the contents names it "Short title".
    "983": {"1": "Short title"},
}
