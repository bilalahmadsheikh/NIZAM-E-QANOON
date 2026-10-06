"""The `source_incomplete` contents-gap resolution (migration 0060): no DB required.

A copy that does not print a section the Act has may be released only with the
gap recorded: the reading names a standing migration-0054 record that says no
complete copy has been obtained, and carries a page reading. These tests pin the
tool-side halves of that -- the reading checks, the mirror of the database
trigger, the refetch classification that feeds the 0054 record, and how the
replay re-attachment treats the resolution.
"""
import hashlib
import pathlib
import re

from tools.adjudicate_toc_from_source import (
    RESOLUTIONS, incompleteness_problem, reading_problem, verify_renders)
from tools.reattach_orphaned_toc_adjudications import plan
from tools.record_source_refetch import DIFFERENT_COPY, attempt_note, classify

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELD = "3a7bb000f3ea56a154e556e32b183180156ae484f8c55f393f5b03ff56b58086"


def reading(**kw):
    """The doc 510 contents reading, as tools/adjudicate_toc_from_source.py
    takes it."""
    row = {
        "document_id": 510, "toc_entry_id": 1078005,
        "resolution": "source_incomplete", "source_incompleteness_id": 41,
        "source_page": 3,
        "observed": ("p3 prints section 3 and then directly section 5; no "
                     "page prints section 4, a stub or an omission mark."),
        "renders": [{"path": "p3.png", "sha256": "ab"}],
    }
    row.update(kw)
    return row


def record(**kw):
    """The INCOMPLETENESS query's row for the named 0054 record."""
    row = {"id": 41, "source_observation_id": 3151, "document_id": 510,
           "resolution": "no_complete_copy_acquired",
           "body_stops_at": "Page 3 prints section 3 and then section 5",
           "latest_id": 41, "built_from": 3151}
    row.update(kw)
    return row


# --- the vocabulary agrees with the migration -------------------------------
def test_the_tool_admits_exactly_the_closing_resolutions_the_table_allows():
    sql = (ROOT / "infra/postgres/migrations/0060_toc_gap_source_incomplete.sql"
           ).read_text(encoding="utf-8")
    check = re.search(r"toc_gap_adjudication_resolution_check CHECK "
                      r"\(resolution IN \((.*?)\)\)", sql, re.S).group(1)
    allowed = set(re.findall(r"'([a-z_]+)'", check))
    # parser_defect closes nothing and is recorded by the repair tools only.
    assert RESOLUTIONS == allowed - {"parser_defect"}
    assert "source_incomplete" in RESOLUTIONS


# --- the reading on its own -------------------------------------------------
def test_a_complete_source_incomplete_reading_passes():
    assert reading_problem(reading()) is None


def test_source_incomplete_must_name_the_0054_record():
    why = reading_problem(reading(source_incompleteness_id=None))
    assert "source_incompleteness_id required" in why


def test_the_named_record_must_be_an_integer_id():
    for bad in ("41", 0, -3, 4.5, True):
        assert reading_problem(reading(source_incompleteness_id=bad)), bad


def test_source_incomplete_still_needs_words_and_a_render():
    assert "no observation" in reading_problem(reading(observed="short"))
    assert "no rendered page" in reading_problem(reading(renders=[]))


def test_an_unknown_resolution_is_refused_by_name():
    why = reading_problem(reading(resolution="not_available"))
    assert "'not_available'" in why and "source_incomplete" in why


def test_other_instrument_still_needs_its_pointer():
    assert "other_instrument_id" in reading_problem(
        reading(resolution="other_instrument"))


def test_other_resolutions_do_not_need_an_incompleteness_record():
    assert reading_problem(reading(resolution="absent_in_source",
                                   source_incompleteness_id=None)) is None


# --- renders are hashed, not trusted ----------------------------------------
def test_renders_are_hashed_and_a_wrong_hash_is_refused(tmp_path):
    page = tmp_path / "doc510-p3.png"
    page.write_bytes(b"page three")
    digest = hashlib.sha256(b"page three").hexdigest()
    paths, digests, bad = verify_renders([{"path": str(page), "sha256": digest}])
    assert bad is None and digests == [digest] and paths[0].endswith("p3.png")
    _, _, bad = verify_renders([{"path": str(page), "sha256": "0" * 64}])
    assert "sha256 does not match" in bad


def test_a_render_that_is_not_on_disk_is_refused(tmp_path):
    _, _, bad = verify_renders([{"path": str(tmp_path / "missing.png")}])
    assert "not on disk" in bad


# --- the mirror of migration 0060's trigger ---------------------------------
def test_the_standing_record_for_the_same_file_is_accepted():
    assert incompleteness_problem(record(), 510) is None


def test_an_id_that_names_nothing_is_refused():
    assert "names no" in incompleteness_problem(None, 510)


def test_a_record_about_another_observation_is_refused():
    why = incompleteness_problem(record(built_from=9999), 510)
    assert "observation 3151" in why and "9999" in why


def test_a_record_about_another_document_is_refused():
    assert "document 510, not 511" in incompleteness_problem(record(), 511)


def test_a_superseded_record_is_refused_and_the_newer_one_named():
    why = incompleteness_problem(record(latest_id=57), 510)
    assert "not the latest" in why and "57" in why


def test_a_held_complete_copy_means_retire_the_tree_not_release_a_gap():
    why = incompleteness_problem(
        record(resolution="superseded_by_complete_copy"), 510)
    assert "apply_source_incompleteness" in why


# --- the dated refetch that the 0054 record rests on ------------------------
def test_identical_bytes_are_an_unchanged_copy():
    assert classify(200, HELD, HELD, True, None, None) == ("unchanged_copy", None)


def test_a_different_valid_pdf_is_not_recorded_as_an_attempt():
    outcome, why = classify(200, "f" * 64, HELD, True, None, None)
    assert outcome == DIFFERENT_COPY and HELD in why


def test_unreachable_server_error_status_and_bad_bytes_keep_their_names():
    assert classify(None, None, HELD, False, "URLError: refused", None) == (
        "network_error", "URLError: refused")
    assert classify(404, "a" * 64, HELD, False, "HTTP 404", None)[0] == "http_error"
    assert classify(200, "a" * 64, HELD, False, None,
                    "magic bytes are not %PDF-") == (
        "invalid_pdf", "magic bytes are not %PDF-")


def test_a_short_valid_pdf_is_still_judged_by_its_hash_not_its_validity():
    # The incomplete copy is a VALID pdf: identical bytes are unchanged_copy,
    # never 'recovered' (migration 0055).
    outcome, _ = classify(201, HELD, HELD, True, None, None)
    assert outcome == "unchanged_copy"


def test_the_ledger_text_states_the_identical_bytes_and_keeps_the_note():
    text = attempt_note("unchanged_copy", 23599, HELD, "s.4 still not printed")
    assert "byte-identical" in text and HELD in text
    assert text.endswith("s.4 still not printed")
    assert attempt_note("network_error", 0, None, None) is None


# --- carried across a replay while the source record stands -----------------
def orphan(**kw):
    row = {
        "id": "00000000-0000-0000-0000-000000000510",
        "document_id": 510,
        "old_instrument_id": "aaaaaaaa-0000-0000-0000-000000000510",
        "old_toc_entry_id": 1078005,
        "printed_label": "4",
        "resolution": "source_incomplete",
        "source_page": 3,
        "evidence": {"source_incompleteness_id": 41},
        "rationale": "read against the pages",
        "decided_by": "claude.toc-source-review/2",
        "old_source_block_id": 19681,
        "old_printed_heading": "Pass Book.",
        "old_entry_source_page": 1,
        "old_ordinal": 4,
        "reresolved_provision_id": None,
        "incompleteness_current": True,
    }
    row.update(kw)
    return row


def live_entry(**kw):
    row = {
        "toc_entry_id": 2000004, "document_id": 510,
        "instrument_id": "bbbbbbbb-0000-0000-0000-000000000510",
        "ordinal": 4, "printed_label": "4", "printed_heading": "Pass Book.",
        "source_block_id": 19681, "source_page": 1, "resolved": False,
        "is_pending_gap": True, "standing_adjudication_id": None,
        "standing_resolution": None, "standing_decided_by": None,
    }
    row.update(kw)
    return row


def test_a_standing_source_record_carries_the_decision_forward():
    result = plan([orphan()], [live_entry()])
    (row,) = result["rebind"]
    assert row["resolution"] == "source_incomplete"
    assert row["new_toc_entry_id"] == 2000004


def test_a_superseded_source_record_is_refused_not_carried():
    result = plan([orphan(incompleteness_current=False)], [live_entry()])
    assert not result["rebind"]
    assert result["refused"][0]["kind"] == "stale_source_record"


def test_the_truncated_copy_shape_does_not_block_it():
    # absent_in_source refuses a document with most of its contents unresolved
    # (the truncated-copy shape); for source_incomplete that shape is the point.
    others = [live_entry(toc_entry_id=2000000 + i, ordinal=i,
                         printed_label=str(i), printed_heading=f"H{i}.",
                         source_block_id=19670 + i)
              for i in (5, 6, 7, 8)]
    result = plan([orphan()], [live_entry()] + others)
    assert len(result["rebind"]) == 1
