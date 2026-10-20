"""The S7 source stub guard measures provision TEXT, not block attribution (lead, 16 Oct 2026).

`tools/adjudicate_s7_from_source.py` refuses an `accept_non_citable` when the demoted unit carries 500+ characters and
the kept one less than half of it. It used to sum `provision_block.chars`, which charges a whole block to one
provision. Doc 4474 page 145 prints rule 382's original, 'Punjab Amendment:', then ONE block with the repeated heading
and the amended 'Rule382. (i) ...': its 311 characters were charged to the original, so the guard read 547 demoted
against 247 kept and refused a correct page-read decision. By text the original carries 249 and the amended print 493.
"""
import importlib.util
import pathlib

import pytest

_TOOL = pathlib.Path(__file__).resolve().parents[1] / "tools" / "adjudicate_s7_from_source.py"


def _tool():
    spec = importlib.util.spec_from_file_location("adjudicate_s7_from_source", _TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_threshold_is_unchanged():
    t = _tool()
    assert t.stub_guard_refusal(547, 247).startswith("stub guard: the demoted unit carries 547")
    assert t.stub_guard_refusal(500, 249) is not None
    assert t.stub_guard_refusal(500, 250) is None           # exactly half is kept: not a stub
    assert t.stub_guard_refusal(499, 0) is None             # under 500: the guard does not apply
    assert t.stub_guard_refusal(249, 493) is None


def test_sizes_are_measured_on_provision_text():
    sql = _tool().SIZES
    assert "provision_version" in sql and "text_en" in sql
    assert "provision_block" not in sql and "pb.chars" not in sql


def test_doc_4474_rule_382_measures_its_texts():
    # DB-backed regression (skipped without the local corpus, or once 4474 is re-segmented away from this shape)
    t = _tool()
    try:
        from nizam.storage.db import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT c.candidate_provision_id, c.canonical_provision_id
                             FROM v_active_structural_candidate c
                            WHERE c.document_id = 4474 AND c.printed_label = '382'""")
            rows = cur.fetchall()
            if len(rows) != 1:
                pytest.skip("doc 4474 rule 382 is not one active candidate in this corpus")
            cur.execute(t.SIZES, (rows[0][0],))
            demoted = cur.fetchone()[0]
            cur.execute(t.SIZES, (rows[0][1],))
            kept = cur.fetchone()[0]
    except Exception as error:                                 # noqa: BLE001
        pytest.skip(f"no corpus database: {error}")
    assert (demoted, kept) == (249, 493)
    assert t.stub_guard_refusal(demoted, kept) is None
