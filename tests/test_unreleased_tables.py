"""Tables, member lists and wrapped openers under the unreleased profiles.

docs/SEGMENTATION-PROFILES.md. Two real documents, their blocks frozen in
tests/fixtures/unreleased-tables.json, each parsed under the profile it was
released under with its page-read body-start override. The assertions are
what the printed pages show (renders in .artifacts/release-work-2026-09-24/
claude/renders/doc2019-p*.png and doc1521-p*.png).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from nizam.corpus import segment as S

FIXTURE = Path(__file__).parent / "fixtures" / "unreleased-tables.json"


@lru_cache(maxsize=None)
def _parse(document: str, profile: str | None = None):
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))[document]
    return S.segment(case["blocks"], profile=profile or case["profile"],
                     structural_overrides=case["structural_overrides"])


def _find(seg, kind, label, parent_label=None):
    found = [n for n in seg.flatten() if n.kind == kind and n.label == label
             and (parent_label is None
                  or (n.parent is not None and n.parent.label == parent_label))]
    assert len(found) == 1, (kind, label, parent_label, len(found))
    return found[0]


def test_2019_appendices_are_tables_not_sub_sections_of_section_20():
    seg = _parse("2019")
    appendices = [n for n in seg.flatten() if n.kind == "appendix"]
    assert [n.label for n in appendices] == ["APPENDIX A", "APPENDIX B"]
    assert [c.label for c in appendices[0].children] == ["1", "2", "3", "4", "5", "6"]
    assert [c.label for c in appendices[1].children] == ["1", "2", "3", "4", "5"]
    # each Extent-of-Power cell with the row it is printed beside
    assert appendices[0].children[2].text.endswith("sanctioned estimates. Upto 5%")
    assert appendices[1].children[1].text.endswith("sanctioned estimates upto 10%")
    # the column-number row is table text, not three sub-sections
    section_20 = _find(seg, "section", "20")
    assert [c.label for c in section_20.children] == ["1", "2"]


def test_2019_divisions_and_definitions():
    seg = _parse("2019")
    assert [n.label for n in seg.flatten() if n.kind == "chapter"] == [
        "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    assert any(n.kind == "preamble" for n in seg.root.children)
    assert [c.label for c in _find(seg, "section", "2").children] == list("abcdefgh")
    members = _find(seg, "subsection", "1", "4").children
    assert [c.label for c in members] == [str(n) for n in range(1, 16)]
    assert not [d for d in seg.repeated_label_decisions if not d.get("settled_by_review")]
    assert all(entry["node"] is not None for entry in seg.toc_entries)


def test_2019_default_parse_keeps_its_old_shape():
    seg = _parse("2019", "default")
    assert not [n for n in seg.flatten() if n.kind == "appendix"]


def test_1521_member_table_and_its_closing_words():
    seg = _parse("1521")
    board = _find(seg, "subsection", "2", "3")
    designations = [c.text.rsplit(" ", 1)[-1] for c in board.children if c.kind == "clause"]
    assert designations == ["Chairperson", "Members", "Secretary", "Member", "Member",
                            "Members", "Members", "Member"]
    assert "In the absence of Chairman" in board.text
    assert [c.kind for c in board.children][-1] == "proviso"


def test_1521_wrapped_and_tight_openers():
    seg = _parse("1521")
    assert [c.label for c in _find(seg, "section", "10").children] == ["1", "2", "3", "4", "5"]
    assert [c.label for c in _find(seg, "section", "17").children] == ["1", "2"]
    assert "sub-section (1) of section 8" in _find(seg, "subsection", "1", "17").text


def test_1521_margin_note_belongs_to_the_section_it_sits_beside():
    seg = _parse("1521")
    role, node = seg.block_roles[91485]      # "Definitions." level with "2. In this Act"
    assert role == "heading" and node.kind == "section" and node.label == "2"
