"""Source-derived boundary regressions: doc 02 §5.1–5.2, no DB required."""
import json
from pathlib import Path

import pytest

from nizam.corpus.segment import _detached_schedule_reference, parse_contents, segment


@pytest.mark.parametrize('document,boundary', [(1438, 15), (2581, 14)])
def test_final_body_boundary_and_promises_use_the_same_source_prefix(document, boundary):
    blocks = json.loads((Path(__file__).parent / 'fixtures' / f'contents-{document}.json').read_text(encoding='utf-8'))
    toc, actual_boundary, found = parse_contents(blocks)
    assert found and actual_boundary == boundary  # no shrinkage of the body
    assert set(toc) == {'1', '2', '3', '4'}
    result = segment(blocks)
    assert not result.missing
    assert result.repeated_labels_demoted == 0
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert [n.label for n in sections] == ['1', '2', '3', '4']
    assert all(n.first_page == 2 for n in sections)
    schedule = [n for n in result.flatten() if n.kind == 'schedule']
    assert len(schedule) == 1 and schedule[0].first_page == 3
    parts = [n for n in schedule[0].children if n.kind == 'part']
    assert [n.label for n in parts] == ['I', 'II']
    assert [n.label for n in parts[0].children if n.kind == 'clause'] == [str(i) for i in range(1, 25)]
    assert set(result.block_roles) == {b['id'] for b in blocks}
    assert all(e['source_page'] == 1 and e['node'] is not None for e in result.toc_entries)


def test_detached_schedule_proof_does_not_accept_continued_prose():
    assert _detached_schedule_reference('THE SCHEDULE', '(See sections 2 and 3)')
    assert not _detached_schedule_reference('the Schedule', '(See sections 2 and 3)')
    assert not _detached_schedule_reference('THE SCHEDULE', '(See sections 2 and 3) shall apply')
    assert not _detached_schedule_reference('THE SCHEDULE referred to', '(See section 2)')
