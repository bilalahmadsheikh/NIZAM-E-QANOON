"""Compare completed diagnostic TSV runs without swapping live parser files."""
import argparse
import csv
from pathlib import Path

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('before',type=Path)
ap.add_argument('after',type=Path)
args=ap.parse_args()
def rows(path):
    with path.open(encoding='utf-8') as stream:
        return list(csv.DictReader(stream,delimiter='\t'))
before,after=rows(args.before),rows(args.after)
assert len(before)==len(after),'Different target counts; comparisons are not aligned'
changed=[]
for old,new in zip(before,after):
    assert old['document']==new['document'],'Different target order; do not infer changes'
    if old==new:
        continue
    diff={k:(old[k],new[k]) for k in old if old[k]!=new[k]}
    changed.append((old['document'],diff))
    print(old['document'],diff)
print(f'{len(before)} aligned expression-observation targets; {len(changed)} changed rows; '
      f'{len({doc for doc,_ in changed})} changed documents.')
for metric in ('unlinked','demoted','stranded','stranded_chars'):
    worse=[doc for doc,diff in changed if metric in diff and int(diff[metric][1])>int(diff[metric][0])]
    print(metric,'increased on',sorted(set(worse),key=int))
