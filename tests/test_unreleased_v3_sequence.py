"""`unreleased-v3` rules that read numbering against the contents sequence.

docs/SEGMENTATION-PROFILES.md. Docs 2923 and 2818, frozen in
tests/fixtures/unreleased-v3-sequence.json, parsed under v3 with their
page-read body-start overrides; plus pure shapes for the smaller rules. What
is asserted is what the pages print (renders doc2923-p*.png, doc2818-p*.png).
"""
from __future__ import annotations

import contextlib
import json
from functools import lru_cache
from pathlib import Path

import pytest

from nizam.corpus import segment as S

FIXTURE = Path(__file__).parent / "fixtures" / "unreleased-v3-sequence.json"


@contextlib.contextmanager
def profile(name: str):
    token = S._ACTIVE_PROFILE_RULES.set(S.SEGMENTATION_PROFILES[name])
    try:
        yield
    finally:
        S._ACTIVE_PROFILE_RULES.reset(token)


@lru_cache(maxsize=None)
def _parse(document: str, profile_name: str = "unreleased-v3"):
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))[document]
    return S.segment(case["blocks"], profile=profile_name,
                     structural_overrides=case["structural_overrides"])


def _sections(seg):
    return {n.label: n for n in seg.flatten() if n.kind == "section"}


def test_2923_omitted_section_stubs_are_the_sections():
    seg = _parse("2923")
    sections = _sections(seg)
    for label in ("3", "4", "5", "6", "21", "22"):
        assert sections[label].text.startswith("* * *"), label
        assert not sections[label].children
    # no stub became a sub-section of section 20 or of the chapter
    assert [c.label for c in sections["20"].children] == []
    assert all(entry["node"] is not None for entry in seg.toc_entries)


def test_2923_first_subsection_after_a_decoded_dash():
    sections = _sections(_parse("2923"))
    composition = sections["8"]
    assert composition.text == ""
    first = composition.children[0]
    assert (first.kind, first.label) == ("subsection", "1")
    assert [c.label for c in first.children] == list("abcdef")
    for label in ("7", "10", "11", "12", "13"):
        assert sections[label].children[0].label == "1", label


def test_2923_chapter_one_after_the_promulgating_formula():
    seg = _parse("2923")
    assert [n.label for n in seg.flatten() if n.kind == "chapter"] == ["I", "II", "III", "IV"]
    assert any(n.kind == "preamble" for n in seg.root.children)


def test_2818_bare_numbered_rules_open_in_sequence():
    seg = _parse("2818")
    sections = _sections(seg)
    assert sections["26"].text.startswith("Certificates and provisional orders")
    assert sections["50"].text.startswith("whenever charge of a boiler")
    for label in ("27", "35", "40"):
        assert label in sections
    assert all(entry["node"] is not None for entry in seg.toc_entries)
    assert not [d for d in seg.repeated_label_decisions if not d.get("settled_by_review")]


def test_2818_unnamed_rules_carry_no_heading_and_no_false_exception():
    sections = _sections(_parse("2818"))
    for label in ("9", "12", "22", "26", "38", "50"):
        assert sections[label].heading is None, label
    rule_three = [n for n in _parse("2818").flatten()
                  if n.kind == "explanation" and n.parent is not None
                  and n.parent.label in ("3", "b")]
    assert rule_three == []
    assert sections["25"].children[0].label == "a"
    assert sections["14"].children[0].label == "a"


def test_2818_default_profile_keeps_its_old_shape():
    sections = _sections(_parse("2818", "default"))
    assert "26" not in sections and "50" not in sections


def test_bracketed_omission_stub_only_under_v3():
    # doc 1142 p3 "3[5 * * *]" -- footnote 3: "Section-5, omitted vide order ibid."
    assert S.classify("3[5 * * *]") is None
    with profile("unreleased-v3"):
        assert S.classify("3[5 * * *]") == ("section", "5", "* * *]")
        # an omission inside running text is not a stub
        assert S.classify("district concerned 2[* * *] to the added area") is None


def test_exception_needs_a_word_boundary_under_v3():
    line = "Exceptional cases, which are not covered by the regulations, should be reported."
    assert S.classify(line)[0] == "explanation"
    with profile("unreleased-v3"):
        assert S.classify(line) is None
        assert S.classify("Exception.- Nothing in this section applies")[0] == "explanation"


@pytest.mark.parametrize("block,first,second", [
    ("25. Issue of certificate and provisional order.(a) When a certificate is required",
     "25.", "(a)"),
    ("14. Inspection at special times. .(a) No examination of a boiler shall be made",
     "14.", "(a)"),
])
def test_tight_first_clause_only_under_v3(block, first, second):
    assert len(S.subdivide(block)) == 1
    with profile("unreleased-v3"):
        pieces = [p.strip() for p in S.subdivide(block)]
        assert pieces[0].startswith(first) and pieces[1].startswith(second)


def test_decoded_dash_first_subsection_only_under_v3():
    block = "8. Composition of the Commission.―(1) The Commission shall consist of"
    assert len(S.subdivide(block)) == 1
    with profile("unreleased-v3"):
        assert [p.strip()[:3] for p in S.subdivide(block)] == ["8. ", "(1)"]


def _mini_act_with_marked_row():
    rows = ["CONTENTS", "1. Short title.", "2. * * * *.", "3. Commencement.", "4. Savings."]
    body = ["1. Short title.— This Act may be called the Test Act.",
            "3. Commencement.— It shall come into force at once.",
            "4. Savings.— Nothing in this Act affects any pending proceeding."]
    blocks = [{"id": i + 1, "text": t, "page_no": 1, "y0": 80.0 + 20 * i, "x0": 72.0,
               "x1": 400.0, "page_height": 792} for i, t in enumerate(rows)]
    blocks += [{"id": 10 + i, "text": t, "page_no": 2, "y0": 80.0 + 40 * i, "x0": 72.0,
                "x1": 520.0, "page_height": 792} for i, t in enumerate(body)]
    assertion = {"id": 1, "source_block_id": 3, "printed_label": "2", "printed_heading": "* * * *.",
                 "disposition": "repealed", "source_page": 1, "amending_instrument_id": None}
    return blocks, [assertion]


def test_printed_disposition_row_needs_v3_and_a_reviewed_record():
    # doc 4222's contents prints "16. * * * *." and the body's note says the
    # section was repealed; the reviewed record carries the note's word
    blocks, dispositions = _mini_act_with_marked_row()
    with pytest.raises(ValueError, match="stale TOC disposition"):
        S.segment(blocks, toc_dispositions=dispositions)
    seg = S.segment(blocks, toc_dispositions=dispositions, profile="unreleased-v3")
    placeholder = _sections(seg)["2"]
    assert placeholder.operation == "omitted" and placeholder.text == ""
    assert all(entry["node"] is not None for entry in seg.toc_entries)
    # without a record the marked row stays open: the marks alone prove nothing
    # (doc 2818 prints "*****" for rules that exist, unnamed)
    unrecorded = S.segment(blocks, profile="unreleased-v3")
    assert [e["label"] for e in unrecorded.toc_entries if e["node"] is None] == ["2"]


def test_v3_extends_v2():
    assert S.SEGMENTATION_PROFILES["unreleased-v2"] < S.SEGMENTATION_PROFILES["unreleased-v3"]
    for rule in ("sequence_omission_stub", "sequence_bare_number", "mark_only_heading_none",
                 "printed_disposition_rows", "decoded_dash_first_subsection"):
        assert rule not in S.SEGMENTATION_PROFILES["unreleased-v2"]
