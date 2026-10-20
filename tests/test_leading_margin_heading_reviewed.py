"""Rule `leading_margin_heading_unit` honoured for REVIEWED blocks in every profile (stage 3, agent DB, doc 252;
owner 12 Oct: implement the recommended fix and release).

Doc 252 (Balochistan Protection of Breast-Feeding and Child Nutrition Act) prints each section's heading in the left
margin; the text layer puts that heading at the head of the section's own block, so it leaked into the previous
section's text ("... purposes of this Act. Overriding Effect.") and s.21's first-sentence heading guess cut its text
at "(Ordinance No.". A reviewed `source_leading_margin_heading_blocks` [block ids] applies the v3 rule in exactly
those blocks (a bare label owning its line, '20', included); inert without a reading; fails closed if a named block
is never reached. Blocks: tests/fixtures/parser-drift-repair.json (doc 252, verbatim).
"""
import json
from pathlib import Path

import pytest

from nizam.corpus import segment as S

CASE = json.loads((Path(__file__).parent / "fixtures" / "parser-drift-repair.json").read_text(encoding="utf-8"))["252"]
GATE = {"source_heading_scan_section_only": True}
P13 = [11125, 11129, 11130, 11131]


def build(extra):
    res = CASE["structural_resolutions"] or None
    overrides = {}
    for row in res or []:
        overrides.update((row.get("evidence") or {}).get("structural_overrides") or {})
    overrides.update(extra)
    seg = S.segment(CASE["blocks"], structural_resolutions=res, structural_overrides=overrides or None,
                    detect_contents=CASE["window_pages"] is None)
    return {n.label: n for n in seg.flatten() if n.kind == "section"}


def test_without_the_reading_the_margin_heading_leaks_and_s21_is_cut():
    secs = build(GATE)
    assert secs["19"].text.endswith("Overriding Effect.")
    assert secs["21"].heading.endswith("(Ordinance No")


def test_in_reviewed_blocks_the_margin_heading_is_the_sections_own():
    secs = build(dict(GATE, source_leading_margin_heading_blocks=P13))
    assert secs["19"].text.endswith("carrying out the purposes of this Act.")
    assert secs["20"].heading == "Overriding Effect."          # the bare '20' owning its line
    assert secs["21"].heading == "Repeal."
    assert secs["21"].text.startswith("The provisions of the Protection of Breast-Feeding and Child")
    assert secs["21"].text.endswith("is hereby repealed.")


def test_a_named_block_the_rule_never_reaches_fails_closed():
    with pytest.raises(ValueError, match="source leading margin heading block not reached"):
        build(dict(GATE, source_leading_margin_heading_blocks=[11123]))
