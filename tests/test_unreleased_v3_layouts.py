"""`unreleased-v3` layout rules on four released documents.

docs/SEGMENTATION-PROFILES.md. Docs 1142, 2983, 258 and 1934, frozen in
tests/fixtures/unreleased-v3-layouts.json with their page-read overrides (and
the two text patches 1142 and 258 carry, applied to the frozen blocks). The
assertions are what the pages print (renders doc<N>-p*.png).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from nizam.corpus import segment as S

FIXTURE = Path(__file__).parent / "fixtures" / "unreleased-v3-layouts.json"


@lru_cache(maxsize=None)
def _parse(document: str, profile: str = "unreleased-v3"):
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))[document]
    return S.segment(case["blocks"], profile=profile,
                     structural_overrides=case["structural_overrides"])


def _node(seg, *path):
    """Walk sections/children by label: _node(seg, "4", "1", "b")."""
    nodes = [n for n in seg.flatten() if n.kind == "section" and n.label == path[0]]
    assert len(nodes) == 1, path
    node = nodes[0]
    for label in path[1:]:
        matches = [c for c in node.children if c.label == label]
        assert matches, (path, label, [c.label for c in node.children])
        node = matches[0]
    return node


def _all_linked(seg):
    return seg.toc_entries and all(entry["node"] is not None for entry in seg.toc_entries)


def test_1142_marked_clause_and_split_margin_heading():
    seg = _parse("1142")
    assert [c.label for c in _node(seg, "4").children] == list("abcd")
    assert _node(seg, "4", "b").text.startswith("all laws in force in the added area")
    assert "of laws" not in _node(seg, "4").text
    assert _node(seg, "5").text.startswith("* * *")
    assert _all_linked(seg)


def test_2983_scheme_keeps_its_paragraphs_and_categories():
    seg = _parse("2983")
    scheme = [n for n in seg.flatten() if n.kind == "schedule"][0]
    assert [c.label for c in scheme.children] == [str(n) for n in range(1, 17)]
    para4 = scheme.children[3]
    assert [c.label for c in para4.children] == list("abcd")
    assert [c.label for c in para4.children[0].children] == ["1", "2", "3"]
    assert "xxxii" not in [c.label for c in _node(seg, "2").children]
    assert scheme.children[4].text.endswith("shall be as under:")
    assert _all_linked(seg) and len(seg.toc_entries) == 28


def test_2983_contents_survive_the_v3_rules():
    # the v3 rules once pushed this document into the refuted-contents path,
    # where no contents entry is recorded and every gate passes vacuously
    seg = _parse("2983")
    assert seg.toc_found and seg.agreement >= 0.99


def test_258_left_margin_headings_and_member_designations():
    seg = _parse("258")
    assert _node(seg, "1", "1").text == "This Act may be called the Balochistan Archives Act, 2014."
    assert _node(seg, "1", "3").text == "It shall come into force at once."
    assert _node(seg, "15", "2").text.endswith("Provincial Government.")
    members = _node(seg, "4", "3").children
    assert [m.label for m in members] == [str(n) for n in range(1, 11)]
    assert all(m.text.rstrip().endswith(("Member", "Chairperson", "Secretary")) for m in members)
    assert _node(seg, "4", "4").text == "The functions of the Board shall be—"
    role, owner = seg.block_roles[11342]      # "Short title, extent and commencement."
    assert role == "heading" and owner.kind == "section" and owner.label == "1"
    assert any(n.kind == "preamble" for n in seg.root.children)


def test_1934_em_dash_first_subsections_and_bracketed_members():
    seg = _parse("1934")
    for label in ("1", "3", "4", "6"):
        assert _node(seg, label).children[0].label == "1", label
    board = _node(seg, "4", "1").children
    assert [m.label for m in board] == ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "i"]
    assert all("Member" in m.text or "Chairman" in m.text for m in board)
    assert ".." not in _node(seg, "4", "2").text
    assert _all_linked(seg)


def test_default_profile_keeps_the_old_shapes():
    # released trees never see the v3 rules: under default, 1142's "1(b)" stays in (a)
    assert "b" not in [c.label for c in _node(_parse("1142", "default"), "4").children]
    assert not _parse("1934", "default").toc_entries or \
        _node(_parse("1934", "default"), "1").children[0].label != "1"
