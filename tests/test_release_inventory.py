"""A named worklist must not silently contain release-qualified expressions."""
import pytest

from tools.diagnose_release_snapshot import write_inventory


def test_saved_worklist_escapes_titles_and_records_exact_pending_counts(tmp_path):
    state=dict(measured_at='2026-09-15T13:17Z',database='nizam_clean',
        canonical=10,released=9,blocked=1,toc=2,s7=0)
    item=dict(document_id=12,id='source-expression',short_title='Act | rules\n1974',
        toc_count=2,s7_count=0,labels=['5.A','5.1'],released=False)
    write_inventory(tmp_path,state,[item])
    text=(tmp_path/'INVENTORY.md').read_text()
    assert '9/10 releasable; 1 withheld; 2 TOC gaps; 0 S7 units.' in text
    assert r'Act \| rules 1974' in text
    assert '5.A, 5.1' in text


def test_worklist_refuses_release_ready_rows_or_a_count_mismatch(tmp_path):
    with pytest.raises(AssertionError):
        write_inventory(tmp_path,dict(blocked=1),[dict(released=True)])
    with pytest.raises(AssertionError):
        write_inventory(tmp_path,dict(blocked=2),[dict(released=False)])
