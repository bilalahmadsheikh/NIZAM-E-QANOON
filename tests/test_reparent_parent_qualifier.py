"""A reviewed reparent may name the parent's label/kind, as it may the source's.

A section's first block usually also opens its first sub-section or clause
("4. (1) The Board shall ..."), so the block address alone resolves to two
nodes and the reparent was refused. Release agents met this on docs 1572,
2745, 3172 and 1834, where bare "2."/"3." sub-sections had to be moved under a
section that shares its block with sub-section (1). The qualifier is inert
unless a reviewed specification carries it.
"""
import pytest

from nizam.corpus.segment import Node, _apply_source_reparents


def _tree():
    root = Node(kind="root", label="", depth=0)
    section = Node(kind="section", label="4", depth=1, first_block=10, parent=root)
    first_sub = Node(kind="subsection", label="1", depth=2, first_block=10, parent=section)
    section.children.append(first_sub)
    stray = Node(kind="clause", label="2", depth=1, first_block=11, parent=root)
    root.children.extend([section, stray])
    return root, section, stray


def test_ambiguous_parent_block_is_refused_without_a_qualifier():
    root, _section, _stray = _tree()
    spec = {"source_block_id": 11, "parent_block_id": 10, "kind": "subsection"}
    with pytest.raises(ValueError, match="parent 10 matched 2"):
        _apply_source_reparents(root, [spec], [], {})


def test_parent_kind_qualifier_resolves_the_section():
    root, section, stray = _tree()
    spec = {"source_block_id": 11, "parent_block_id": 10, "kind": "subsection",
            "parent_kind": "section", "parent_label": "4"}
    enacted = _apply_source_reparents(root, [spec], [], {})
    assert stray.parent is section and stray in section.children
    assert stray not in root.children
    assert stray.kind == "subsection" and stray.depth == section.depth + 1
    assert enacted[0]["parent_kind"] == "section" and enacted[0]["parent_label"] == "4"


def test_qualifier_that_matches_nothing_is_refused():
    root, _section, _stray = _tree()
    spec = {"source_block_id": 11, "parent_block_id": 10, "kind": "subsection",
            "parent_kind": "chapter"}
    with pytest.raises(ValueError, match="parent 10 matched 0"):
        _apply_source_reparents(root, [spec], [], {})
