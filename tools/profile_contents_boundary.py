"""Read-only trace of TOC promises versus the final body boundary (doc 02 §5.2)."""
import argparse
import json
from pathlib import Path

from nizam.corpus.segment import _section_numbers, parse_contents, segment
from nizam.storage.legal_write import blocks_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('documents', type=int, nargs='+')
    parser.add_argument('--fixtures', type=Path)
    args = parser.parse_args()
    for document in args.documents:
        blocks = blocks_for(document)
        toc, boundary, found = parse_contents(blocks)
        prefix = {label for idx, _, label, heading in _section_numbers(blocks)
                  if idx < boundary and heading}
        result = segment(blocks)
        print(json.dumps(dict(document=document, found=found, boundary=boundary,
              body_page=blocks[boundary]['page_no'] if blocks else None,
              promised=toc, outside_prefix=sorted(set(toc)-prefix),
              missing=result.missing, sections=sum(n.kind == 'section' for n in result.flatten()),
              schedules=[dict(label=n.label, page=n.first_page) for n in result.flatten() if n.kind=='schedule']),
              ensure_ascii=False, default=str))
        for idx, block in enumerate(blocks):
            if block['page_no'] <= 3:
                print(idx, block['id'], block['page_no'], repr(block['text'][:450]))
        if args.fixtures:
            args.fixtures.mkdir(parents=True, exist_ok=True)
            (args.fixtures / f'contents-{document}.json').write_text(
                json.dumps(blocks, ensure_ascii=False, default=str, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
