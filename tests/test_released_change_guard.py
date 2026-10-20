"""A released tree is replaced only by an identical rebuild, or under an explicit approval (owner decision 11 Oct,
stage 0; docs/SEGMENTATION-PROFILES.md "Ungated changes and released trees").

The pure half compares a built instrument with stored rows. The database half rebuilds a released document
(2205, the Sind Public Conveyances Act, 1920) exactly as the worker does and calls the real `save()` on a
connection that is rolled back, so nothing is written: an identical rebuild passes, a changed provision text or
a moved contents anchor is refused, and the same change passes with an approval that save() reports.
"""
from __future__ import annotations

import contextlib
import copy

import pytest

from nizam.storage import legal_write


# -- pure: the identity ----------------------------------------------------------------------------------------------

class _Cursor:
    def __init__(self, tree, toc):
        self.results = [tree, toc]

    def execute(self, *_args):
        pass

    def fetchall(self):
        return self.results.pop(0)


def _inst():
    from nizam.shared.corpus_types import SegmentedInstrument  # noqa: F401  (shape only)

    class I:  # the attributes released_tree_change reads
        provisions = [
            {"key": 0, "parent_key": None, "path": "x.s_1", "kind": "section", "label": "1", "ordinal": 0,
             "first_page": 1, "last_page": 1, "first_block": 10, "text": "Short title.", "heading": "Title"},
            {"key": 1, "parent_key": 0, "path": "x.s_1.ss_1", "kind": "subsection", "label": "1", "ordinal": 1,
             "first_page": 1, "last_page": 1, "first_block": 11, "text": "This Act may be called.", "heading": None}]
        toc_entries = [{"ordinal": 1, "label": "1", "heading": "Title", "kind": "section", "provision_key": 0,
                        "method": "exact", "source_block_id": 5, "source_char_offset": 0, "source_page": 1}]
    return I()


def _stored(inst):
    tree, toc = legal_write._built_identity(inst)
    return [tuple(r) for r in tree], [tuple(t) for t in toc]


def test_an_identical_rebuild_is_no_change():
    inst = _inst()
    assert legal_write.released_tree_change(_Cursor(*_stored(inst)), "old", inst) is None


def test_a_text_change_is_a_change():
    inst = _inst()
    stored = _stored(inst)
    inst.provisions[1]["text"] = "This Act may be cited."
    change = legal_write.released_tree_change(_Cursor(*stored), "old", inst)
    assert change["provisions_changed"] == 1 and change["changed"][0] == {"path": "x.s_1.ss_1", "fields": ["text"]}


def test_an_anchor_only_change_is_a_change():
    inst = _inst()
    stored = _stored(inst)
    inst.toc_entries[0]["source_char_offset"] = 3
    change = legal_write.released_tree_change(_Cursor(*stored), "old", inst)
    assert change["provisions_changed"] == 0 and change["toc_changed"][0]["ordinal"] == 1


def test_an_approval_needs_a_reason():
    with pytest.raises(ValueError, match="needs a reason"):
        legal_write._approval("ok")
    assert legal_write._approval("  owner 11 Oct;   stage 2  ") == "owner 11 Oct; stage 2"


# -- the database: the real save() on a rolled-back connection ---------------------------------------------------------

DOC = 2205


@pytest.fixture()
def rolled_back(monkeypatch):
    try:
        import psycopg
        from nizam.storage.db import dsn
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"storage unavailable: {type(exc).__name__}")
    try:
        handle = psycopg.connect(dsn(), autocommit=False)
        handle.execute("SELECT 1")          # open the outer transaction: every save() below is a savepoint in it
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")

    @contextlib.contextmanager
    def same_connection(*_a, **_k):
        with handle.transaction():          # a savepoint per save(): its rows are rolled back below
            yield handle

    monkeypatch.setattr(legal_write, "connect", same_connection)
    try:
        yield handle
    finally:
        handle.rollback()
        handle.close()


def _rebuild(doc):
    """The worker's build of a released document, exactly as its main loop does it."""
    import nizam.workers.segment as worker
    targets = [t for t in legal_write.documents_needing_segmentation(redo=True, include_review=True)
               if t[0] == doc]
    if not targets:
        pytest.skip(f"document {doc} is not a segmentation target here")
    doc_id, sha, observation_id, source_id, title, year, _type, url = targets[0]
    blocks = legal_write.blocks_for(doc_id)
    patches = legal_write.segmentation_patches_for(observation_id)
    resolutions = legal_write.structural_resolutions_for(doc_id)
    inst, _seg = worker.build(doc_id, sha, observation_id, source_id, title, year, url, blocks,
                              legal_write.observed_on(observation_id), patches,
                              toc_dispositions=legal_write.toc_dispositions_for(observation_id),
                              structural_resolutions=resolutions,
                              structural_overrides=worker.reviewed_structural_overrides(resolutions, patches))
    return inst


def _released(conn, doc):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM v_release_instrument WHERE document_id=%s", (doc,))
        return [r[0] for r in cur.fetchall()]


def test_save_replaces_a_released_tree_only_when_identical_or_approved(rolled_back):
    if not _released(rolled_back, DOC):
        pytest.skip(f"document {DOC} is not released here")
    inst = _rebuild(DOC)
    with rolled_back.cursor() as cur:
        cur.execute("SELECT id FROM instrument WHERE document_id=%s AND is_active AND duplicate_of IS NULL", (DOC,))
        previous = cur.fetchone()[0]
        if legal_write.released_tree_change(cur, previous, inst) is not None:
            pytest.skip(f"document {DOC} no longer rebuilds identically; pick another fixture")

    def active(instrument):
        with rolled_back.cursor() as cur:
            cur.execute("SELECT is_active FROM instrument WHERE id=%s", (instrument,))
            return cur.fetchone()[0]

    # 1. identical: passes, as today (in its own rolled-back savepoint, so 2-4 meet the released tree again)
    with rolled_back.transaction(force_rollback=True):
        report: dict = {}
        new_id = legal_write.save(inst, "pytest", report=report)
        assert new_id != previous and report == {}
        assert active(new_id) and not active(previous)
    assert active(previous) and _released(rolled_back, DOC) == [previous]

    # 2. a changed provision text, no approval: refused, nothing replaced
    changed = copy.deepcopy(inst)
    row = next(r for r in changed.provisions if r["text"])
    row["text"] = row["text"] + " [pytest change]"
    with pytest.raises(ValueError, match="would change.*approve-release-change"):
        legal_write.save(changed, "pytest")
    assert _released(rolled_back, DOC) == [previous]

    # 3. an anchor-only change, no approval: refused too
    moved = copy.deepcopy(inst)
    entry = next(e for e in moved.toc_entries if e.get("source_char_offset") is not None)
    entry["source_char_offset"] = entry["source_char_offset"] + 1
    with pytest.raises(ValueError, match="would change"):
        legal_write.save(moved, "pytest")

    # 4. the same change with an approval: replaced, and the approval and the change are reported
    report = {}
    approved_id = legal_write.save(changed, "pytest", report=report,
                                   approve_release_change="pytest: owner decision 11 Oct, stage 0 test")
    assert report["release_change_approval"] == "pytest: owner decision 11 Oct, stage 0 test"
    assert report["release_change"]["provisions_changed"] == 1
    assert report["release_change"]["previous_instrument_id"] == str(previous)
    assert active(approved_id) and not active(previous)
