"""Historical amendment provenance is apparatus, not a citable section.

Source-derived from 3353; doc 02 §§5.1–5.2 and doc 03 §2A. The fixture keeps
whole extracted blocks and their source coordinates, not reconstructed text.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from nizam.corpus.segment import _FOOTNOTE, _PARENTHESIZED_CHAPTER, classify, subdivide


def _blocks():
    return json.loads((Path(__file__).parent/'fixtures'/'editorial-provenance-3353.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('block_id', [358589, 358615, 358629, 358638, 358646])
def test_explicit_editorial_provenance_is_recognised_as_apparatus(block_id):
    block=next(b for b in _blocks() if b['id']==block_id)
    original=deepcopy(block)
    assert _FOOTNOTE.match(block['text'])
    assert block==original


@pytest.mark.parametrize('block_id,label', [(358548,'II'), (358654,'IV')])
def test_editorial_note_and_parenthesized_chapter_are_preserved_separately(block_id,label):
    block=next(b for b in _blocks() if b['id']==block_id)
    original=deepcopy(block)
    assert _FOOTNOTE.match(block['text'])
    assert _PARENTHESIZED_CHAPTER.search(block['text'])
    pieces=subdivide(block['text'])
    assert len(pieces)>=2
    assert all(_FOOTNOTE.match(piece) for piece in pieces[:-1])
    assert classify(pieces[-1])[:2]==('chapter',label)
    assert ''.join(pieces)==block['text']
    assert block==original


@pytest.mark.parametrize('text', [
    '1. In section 13A of the Act, the following shall be inserted by Act 2026.',
    '1. The words “old text” are repealed by this Act.',
    '1. See now the Code of Civil Procedure as amended by this section shall apply.',
    '1. Section 15-D is inserted by this Act.',
    '(Chapter II of this Act) applies to the following proceedings.',
])
def test_operative_amendment_or_cross_reference_is_not_provenance_apparatus(text):
    assert not _FOOTNOTE.match(text)
    assert not _PARENTHESIZED_CHAPTER.search(text)
