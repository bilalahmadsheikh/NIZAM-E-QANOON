"""Expose printed dashed starts, not fabricate labels (doc 02 §§5.1–5.2).

Six noncontiguous whole source blocks; not a complete Act or section fixture.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from nizam.corpus.segment import classify, subdivide


@pytest.mark.parametrize('block_id,label', [
    (358618,'15B'), (358620,'15C'), (358627,'15D'), (358764,'63A'),
])
def test_source_dashed_starts_fused_to_prior_text_are_exposed(block_id,label):
    blocks=json.loads((Path(__file__).parent/'fixtures'/'dashed-openers-3353.json').read_text(encoding='utf-8'))
    block=next(b for b in blocks if b['id']==block_id)
    original=deepcopy(block)
    pieces=subdivide(block['text'])
    # subdivide already omits an all-whitespace leading piece. All words,
    # internal spacing and punctuation (including both printed dots) remain;
    # the immutable input block itself must remain byte-for-byte unchanged.
    assert ''.join(pieces).lstrip()==block['text'].lstrip()
    matches=[c for piece in pieces for c in [classify(piece)]
             if c and c[:2]==('section',label)]
    assert len(matches)==1
    assert block==original


@pytest.mark.parametrize('text', [
    'Earlier material.\n15B ins. by the Act, 1882, s. 6.',
    'An interval of\n15.---20. days applies.',
    'The fee in excess of Rs.\n1000.---(1) Ten rupees.',
    'An earlier sentence.\n15B---(1) The Court may act.',  # dotless: separate cause
    'An earlier sentence.\n15D...---(1) Any person may act.',
    'An earlier sentence.\n15B.----(1) The Court may act.',
    'An earlier sentence.\n15B.---(2) The Court may act.',
    'An earlier sentence.\n15B.---(1) of section 3 applies.',
    'An earlier sentence contains 15B.---(1) The Court may act.',
    'An earlier sentence.\n44.---(1) The Court may act.',
    'An earlier sentence.\n61.---(1) The Court may act.',
])
def test_dashed_candidate_does_not_broaden_unproven_starts(text):
    assert subdivide(text)==[text]


def test_wrapped_cross_reference_before_65_does_not_hide_the_next_section():
    blocks=json.loads((Path(__file__).parent/'fixtures'/'dashed-openers-3353.json').read_text(encoding='utf-8'))
    block=next(b for b in blocks if b['id']==358770)
    pieces=subdivide(block['text'])
    # First establish the rendered document's actual cause before changing the
    # generic inner splitter: section 65 starts immediately after a newline.
    assert any(piece.lstrip().startswith('65. Any agriculturist') for piece in pieces)
    assert classify(next(piece for piece in pieces if piece.lstrip().startswith('65.')))[:2] == ('section','65')


def test_same_line_whitespace_padded_dotted_citation_is_not_a_section_break():
    # The correction above is deliberately a line-boundary change. It must not
    # revive the dotted-citation false split for which this guard was written.
    text='The reference in 6 . 2 . 3. This is still citation prose.'
    assert subdivide(text)==[text]
