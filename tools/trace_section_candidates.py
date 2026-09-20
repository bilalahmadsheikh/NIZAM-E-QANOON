"""Read-only source-fixture trace for doc 02 section 5 boundary diagnoses."""
import argparse
import json
from pathlib import Path
import sys

from nizam.corpus.segment import (
    _FOOTNOTE, _SPLIT_NOTE_BODY, _SPLIT_NOTE_NUMBER, _is_footnote_run,
    _section_numbers, classify, parse_contents, subdivide,
)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("fixture", type=Path)
parser.add_argument("--pages", type=int, nargs="+", required=True)
parser.add_argument("--block", type=int)
args = parser.parse_args()
blocks = json.loads(args.fixture.read_text(encoding="utf-8"))
def opening_trace(frame, event, value):
    if event=='call':
        return opening_trace if frame.f_code.co_name in (
            'opening_matches_toc','boundary_preserves_toc','parse_contents') else None
    if event=='return' and frame.f_code.co_name in (
            'opening_matches_toc','boundary_preserves_toc','parse_contents'):
        names = ('candidate_boundary','promised','matched','key','wanted','actuals',
                 'best_idx','best_score','last_page','saw_marker','marker_indexes','explicit')
        print('OPENING',json.dumps(dict(function=frame.f_code.co_name,
            result=value if isinstance(value,(int,float,bool)) else None,
            context={k:frame.f_locals[k] for k in names if k in frame.f_locals}),
            ensure_ascii=False))
    return opening_trace
sys.settrace(opening_trace)
toc, boundary, found = parse_contents(blocks)
sys.settrace(None)
print(json.dumps(dict(boundary=boundary, found=found, toc=toc), ensure_ascii=False))
for index, block in enumerate(blocks):
    if block["page_no"] not in args.pages or (args.block is not None and block['id'] != args.block):
        continue
    notes = []
    for line in block['text'].splitlines():
        if not line.strip():
            continue
        if match := _SPLIT_NOTE_NUMBER.fullmatch(line):
            notes.append(dict(number=int(match.group(1)),parts=[]))
        elif notes:
            notes[-1]['parts'].append(line)
    for note in notes:
        value = ' '.join(note['parts'])
        note.update(text=value,footnote=bool(_FOOTNOTE.match(f"{note['number']}. {value}")),
                    other_apparatus=bool(_SPLIT_NOTE_BODY.match(value)))
    print(json.dumps(dict(index=index, block=block,
        logical_note_diagnosis=notes,
        footnote=bool(_FOOTNOTE.match(block["text"])),
        footnote_run=_is_footnote_run(block["text"]),
        units=[dict(text=piece, classification=classify(piece))
               for piece in subdivide(block["text"])]), ensure_ascii=False))
print(json.dumps([row for row in _section_numbers(blocks)
                  if blocks[row[0]]["page_no"] in args.pages], ensure_ascii=False))
