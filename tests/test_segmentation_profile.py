"""Segmentation profiles: the default parse is untouched, a pin is honoured.

docs/SEGMENTATION-PROFILES.md. A profile switches on extra segmenter rules for
observations pinned to it in `segmentation_profile_pin` (migration 0056). The
contract these tests hold:

  * the default profile IS today's parser -- `segment(blocks)` and
    `segment(blocks, profile="default")` give the same tree, byte for byte,
    on whole stored documents;
  * a profile with no rules switched on gives that same tree too, so the
    plumbing alone can change nothing;
  * a rule is visible only inside the parse that asked for it, and never leaks
    to the next parse, even when the first one raises;
  * build() reads the observation's pin unless told the profile, and the
    writer identity names a non-default profile.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nizam.corpus import segment as S
from nizam.workers import segment as worker

FIXTURE = Path(__file__).parent / "fixtures" / "parser-drift-repair.json"
_CACHE: dict = {}


def _fixture() -> dict:
    if not _CACHE:
        _CACHE.update(json.loads(FIXTURE.read_text(encoding="utf-8")))
    return _CACHE


def _signature(seg) -> dict:
    """Everything a stored tree is built from, in a comparable form."""
    nodes = seg.flatten()
    index = {id(node): i for i, node in enumerate(nodes)}
    return {
        "nodes": [(node.kind, node.label, node.heading, node.marginal_note,
                   node.operation, node.amendment_note, node.text, node.depth,
                   node.first_page, node.last_page, node.first_block,
                   list(node.blocks),
                   index.get(id(node.parent)) if node.parent is not None else None)
                  for node in nodes],
        "block_roles": sorted(
            (block, role, index.get(id(node)) if node is not None else None)
            for block, (role, node) in seg.block_roles.items()),
        "toc_entries": [(e["ordinal"], e["label"], e["heading"], e["kind"],
                         index.get(id(e["node"])) if e["node"] is not None else None)
                        for e in seg.toc_entries],
        "decisions": [(d["printed_label"], d["original_kind"],
                       index.get(id(d["candidate"])), index.get(id(d["canonical"])),
                       bool(d.get("settled_by_review")))
                      for d in seg.repeated_label_decisions],
        "body_starts_page": seg.body_starts_page,
        "toc_found": seg.toc_found,
        "missing": list(seg.missing),
        "extra": list(seg.extra),
    }


def _segment(document: str, **kwargs):
    case = _fixture()[document]
    resolutions = case["structural_resolutions"] or None
    overrides: dict = {}
    for row in resolutions or []:
        overrides.update((row.get("evidence") or {}).get("structural_overrides") or {})
    return S.segment(case["blocks"], structural_resolutions=resolutions,
                     structural_overrides=overrides or None,
                     detect_contents=case["window_pages"] is None, **kwargs)


DOCUMENTS = sorted(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.mark.parametrize("document", DOCUMENTS)
def test_default_profile_is_todays_parser(document):
    implicit = _segment(document)
    explicit = _segment(document, profile="default")
    assert implicit.profile == explicit.profile == "default"
    assert _signature(implicit) == _signature(explicit)


@pytest.mark.parametrize("document", DOCUMENTS)
def test_a_profile_with_no_rules_changes_nothing(document, monkeypatch):
    monkeypatch.setitem(S.SEGMENTATION_PROFILES, "empty-for-test", frozenset())
    default = _segment(document)
    empty = _segment(document, profile="empty-for-test")
    assert empty.profile == "empty-for-test"
    assert _signature(default) == _signature(empty)


def test_unknown_profile_is_refused():
    with pytest.raises(ValueError, match="unknown segmentation profile"):
        S.segment([], profile="no-such-profile")


def test_rules_are_visible_only_inside_their_parse(monkeypatch):
    monkeypatch.setitem(S.SEGMENTATION_PROFILES, "probe", frozenset({"probe-rule"}))
    seen = []
    real = S._segment

    def spy(*args, **kwargs):
        seen.append(S.profile_rule("probe-rule"))
        return real(*args, **kwargs)

    monkeypatch.setattr(S, "_segment", spy)
    document = DOCUMENTS[0]
    _segment(document, profile="probe")
    _segment(document)
    assert seen == [True, False]
    assert not S.profile_rule("probe-rule")


def test_rules_reset_when_the_parse_raises(monkeypatch):
    monkeypatch.setitem(S.SEGMENTATION_PROFILES, "probe", frozenset({"probe-rule"}))

    def boom(*args, **kwargs):
        assert S.profile_rule("probe-rule")
        raise RuntimeError("parse failed")

    monkeypatch.setattr(S, "_segment", boom)
    with pytest.raises(RuntimeError):
        S.segment([], profile="probe")
    assert not S.profile_rule("probe-rule")


def test_writer_identity_names_a_non_default_profile():
    assert worker.segmenter_identity() == worker.SEGMENTER
    assert worker.segmenter_identity("default") == worker.SEGMENTER
    assert worker.segmenter_identity("unreleased-v1") == \
        f"{worker.SEGMENTER}+unreleased-v1"


def _blocks():
    return [
        {"id": 1, "page_no": 1, "text": "1. Short title.- This Act may be called "
                                         "the Example Act, 2020."},
        {"id": 2, "page_no": 1, "text": "2. Definitions.- In this Act, unless "
                                         "the context otherwise requires."},
    ]


def test_build_reads_the_pin_when_not_told(monkeypatch):
    asked = []

    def pinned(observation):
        asked.append(observation)
        return "default"

    monkeypatch.setattr(worker.legal_write, "segmentation_profile_for", pinned)
    _inst, seg = worker.build(5, "p" * 64, 314, "pk-federal", "Example Act, 2020",
                              "2020", None, _blocks(), "2026-09-26")
    assert asked == [314]
    assert seg.profile == "default"


def test_build_passes_a_named_profile_without_a_lookup(monkeypatch):
    def forbidden(observation):
        raise AssertionError("a named profile must not consult the pin")

    monkeypatch.setattr(worker.legal_write, "segmentation_profile_for", forbidden)
    monkeypatch.setitem(S.SEGMENTATION_PROFILES, "empty-for-test", frozenset())
    _inst, seg = worker.build(5, "p" * 64, 314, "pk-federal", "Example Act, 2020",
                              "2020", None, _blocks(), "2026-09-26",
                              profile="empty-for-test")
    assert seg.profile == "empty-for-test"
