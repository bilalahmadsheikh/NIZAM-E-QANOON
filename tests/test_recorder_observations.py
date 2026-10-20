"""Which observations a curation reading is recorded on (tools/record_curation_patch.py; lead, 12 Oct 2026).

Doc 4419 (the Constitution) has two byte-identical catalogue observations, 507 and 132; 132's instrument was an exact
duplicate of 507's. The recorder looked only at non-duplicate instruments, so DE's readings landed on 507 alone; the
replay rebuilt 132 without them, it stopped being a duplicate and entered the release with the old text. Now every
observation behind an active instrument counts, one blob means one reading on each, and the identical-patch check is
per observation.
"""
from tools.record_curation_patch import observations_still_missing, patch_observations

BLOB = "a" * 64


def test_byte_identical_observations_are_recorded_together():
    assert patch_observations([(507, BLOB), (132, BLOB)], all_observations=False) == ([132, 507], None)
    assert patch_observations([(507, BLOB)], all_observations=False) == ([507], None)


def test_different_blobs_still_need_all_observations():
    observations, why = patch_observations([(424, BLOB), (434, "b" * 64)], all_observations=False)
    assert observations == [] and "all_observations" in why
    assert patch_observations([(424, BLOB), (434, "b" * 64)], all_observations=True) == ([424, 434], None)
    observations, why = patch_observations([(1, None), (2, None)], all_observations=False)   # unknown blob
    assert observations == [] and "all_observations" in why
    assert patch_observations([], all_observations=True) == ([], "0 active observations")


def test_a_rerun_records_only_on_the_missing_observation():
    assert observations_still_missing([132, 507], {507}) == ([132], [507], None)
    assert observations_still_missing([132, 507], set()) == ([132, 507], [], None)
    remaining, skipped, why = observations_still_missing([132, 507], {132, 507})
    assert remaining == [] and skipped == [132, 507] and "every observation" in why


def test_a_disposition_is_recorded_on_every_same_blob_observation():
    """tools/review_toc_dispositions.py (docs 4501, 2605): same blob -> each observation; another blob -> not."""
    from tools.review_toc_dispositions import same_blob_observations
    assert same_blob_observations(434, [(424, BLOB), (434, BLOB)]) == [424, 434]
    assert same_blob_observations(85, [(85, BLOB), (9567, BLOB), (77, "c" * 64)]) == [85, 9567]
    assert same_blob_observations(85, [(85, BLOB)]) == [85]
    assert same_blob_observations(85, []) == [85]          # the reviewed observation is always included


def test_recording_a_disposition_is_idempotent_per_observation():
    from tools.review_toc_dispositions import _record_on

    class Cur:
        def __init__(self, previous):
            self.previous, self.inserted = previous, 0

        def execute(self, sql, params=None):
            self.last = sql
            if "INSERT INTO toc_disposition_assertion" in sql:
                self.inserted += 1

        def fetchone(self):
            return self.previous

        def fetchall(self):
            return self.own

    Cur.own = [(1078330,)]

    entry = {"source_block_id": 7, "printed_label": "34A", "printed_heading": "[Omitted]", "source_page": 12,
             "ordinal": 3, "toc_entry_id": 99, "classification": "omitted", "body_section_hits": 0,
             "schedule_label_collisions": 0}
    artifact = {"path": "renders/x.png", "sha256": "f" * 64}
    same = Cur((5, "[Omitted]", 7, 12, "f" * 64))
    assert _record_on(same, entry, 424, artifact, None, False, "assistant") == "unchanged" and same.inserted == 0
    fresh = Cur(None)
    assert _record_on(fresh, entry, 424, artifact, None, False, "assistant") == "inserted" and fresh.inserted == 1
    duplicate = Cur(None)
    duplicate.own = []                     # the observation's instrument is an exact duplicate: no own entry
    assert _record_on(duplicate, entry, 424, artifact, None, False, "assistant") == "no_canonical_entry"
    assert duplicate.inserted == 0


def test_every_structural_key_has_a_recording_branch():
    # lead 13 Oct 2026: a structural key the recorder accepts but never copies into the evidence was dropped silently
    # (doc 4521's source_figure_subsections). Each key is recorded by the generic branch, the DF block-key branch or a
    # branch of its own; the run itself refuses a reading whose key did not reach the evidence.
    import pathlib
    import re as _re
    from nizam.workers.segment import DF_BLOCK_KEYS
    from tools import record_curation_patch as rcp
    assert rcp.GENERIC_STRUCTURAL_KEYS <= rcp.STRUCTURAL_KEYS
    src = pathlib.Path(rcp.__file__).read_text(encoding="utf-8")
    keys_block = src[src.index("STRUCTURAL_KEYS = frozenset("):src.index("READING_KEYS = STRUCTURAL_KEYS")]
    body = src.replace(keys_block, "")
    lacking = sorted(k for k in rcp.STRUCTURAL_KEYS
                     if k not in rcp.GENERIC_STRUCTURAL_KEYS and k not in DF_BLOCK_KEYS
                     and not _re.search(r"[\"']" + _re.escape(k) + r"[\"']", body))
    assert lacking == []
    assert "would not be recorded; refused rather than" in src
    assert rcp.named_block_ids({"source_figure_subsections": [{"section_block_id": 5, "subsections": [
        {"source_block_id": 6, "figure": "1"}]}], "source_margin_note_pieces": [
        {"target_block_id": 7, "source_block_ids": [8, 9], "label": "6"}]}) == {5, 6, 7, 8, 9}
    assert rcp.named_block_ids({"flag": True, "label": 4}) == set()



def test_cited_pages_take_one_or_several_additional_renders():
    # doc 4400's contents-region reading cites four further pages (pp8-11); a single render works as before
    from tools.record_curation_patch import reading_cited_pages
    assert reading_cited_pages({"additional_render": "x/doc4400-p8.png"}, 4400, 1) == {1, 8}
    assert reading_cited_pages({"additional_render": [f"x/doc4400-p{p}.png" for p in (8, 9, 10, 11)]}, 4400, 1) == {
        1, 8, 9, 10, 11}
    assert reading_cited_pages({"additional_render": ["x/doc9999-p8.png"]}, 4400, 1) == {1}
    assert reading_cited_pages({}, 4400, 3) == {3}
