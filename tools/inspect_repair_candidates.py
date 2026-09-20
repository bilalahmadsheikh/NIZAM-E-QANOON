"""Inspect exact source anchors and pure-parser changes in an offline snapshot.

Diagnostic output only, no corpus writes (docs 02 section 5; 03 section 2A).
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('snapshot', type=Path)
ap.add_argument('documents', type=int, nargs='+')
ap.add_argument('--probe', type=Path)
ap.add_argument('--containers-only', action='store_true')
ap.add_argument('--gaps-only', action='store_true',
                help='Inspect unlinked TOC rows against the complete candidate tree')
ap.add_argument('--source-page-json', type=int, nargs='+',
                help='Output immutable fixture pages as JSON for regression review')
args = ap.parse_args()
if args.source_page_json is not None:
    if len(args.documents)!=1:
        ap.error('A page fixture requires exactly one document')
    doc=args.documents[0]
    blocks=json.loads((args.snapshot/'source-fixtures'/f'contents-{doc}.json').read_text())
    print(json.dumps([b for b in blocks if b['page_no'] in args.source_page_json],
                     ensure_ascii=False,indent=2))
    raise SystemExit(0)
instruments = json.loads((args.snapshot/'instruments.json').read_text())
probe = json.loads(args.probe.read_text()) if args.probe else {}
for doc in args.documents:
    print('DOCUMENT', doc)
    print(json.dumps([dict(title=i['short_title'], id=i['id'],
        toc=i['toc_count'], s7=i['s7_count'], source=i['source_url'],
        sha256=i['sha256']) for i in instruments if i['document_id']==doc]))
    drypath = args.snapshot/'dry-runs'/f'{doc}.json'
    if not drypath.exists():
        continue
    dry = json.loads(drypath.read_text())
    if args.gaps_only:
        from nizam.corpus.segment import _citation_label_key
        for entry in dry['toc_entries']:
            if entry.get('provision_key') is not None:
                continue
            matches = [p for p in dry['provisions']
                       if _citation_label_key(p['label']) == _citation_label_key(entry['label'])]
            print('GAP',json.dumps(dict(contents=entry,body=matches),ensure_ascii=False))
        print('RUN_ONLY',json.dumps(dry['missing'],ensure_ascii=False))
        print('COLLISIONS',json.dumps(dry['decisions'],ensure_ascii=False))
        continue
    if args.containers_only:
        nodes={p['key']:p for p in dry['provisions']}
        for p in nodes.values():
            if p['kind'] in ('schedule','part','form'):
                parent=nodes.get(p['parent_key'])
                print(json.dumps(dict(kind=p['kind'],label=p['label'],page=p['first_page'],
                    block=p['first_block'],heading=p['heading'],parent=dict(kind=parent['kind'],
                    label=parent['label'],page=parent['first_page']) if parent else None)))
        continue
    candidate = next((c for c in probe.get('changes',[]) if c['document_id']==doc),None)
    changed_anchors = set()
    if candidate:
        before = {(n['kind'],n['label'],n['first_block']):n for n in candidate['before']['nodes']}
        after = {(n['kind'],n['label'],n['first_block']):n for n in candidate['after']['nodes']}
        for key in before.keys() | after.keys():
            old, new = before.get(key),after.get(key)
            if old == new:
                continue
            changed_anchors.add(key[2])
            print(json.dumps(dict(key=key, before=old, after=new),ensure_ascii=False))
    for e in dry['toc_entries']:
        p = next((p for p in dry['provisions'] if p['key']==e['provision_key']),None)
        if p and (p['first_block'] in changed_anchors or e['method']!='label'):
            print('ANCHOR',json.dumps(dict(contents=e, body=p),ensure_ascii=False))
    fixture = args.snapshot/'source-fixtures'/f'contents-{doc}.json'
    if fixture.exists():
        for b in json.loads(fixture.read_text()):
            if b['id'] in changed_anchors:
                print('BLOCK',json.dumps(b,ensure_ascii=False))
