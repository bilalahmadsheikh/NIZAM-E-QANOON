#!/bin/bash
# G_dry.sh DOC [READINGS.json] : agent G -- materializer dry run (optionally with unrecorded readings); per expression: s7, toc, labels
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
X=""; [ -n "$2" ] && X="--unrecorded-readings $2"
.venv/bin/python tools/materialize_multi_instrument.py --document $1 $X 2>&1 | .venv/bin/python -c "
import sys,json
t=sys.stdin.read(); i=t.find('[\n')
if i<0: print(t[-1500:]); sys.exit()
for d in json.loads(t[i:]):
  for e in d['expressions']:
    print(e['ordinal'], e['role'], e['title'][:60], 'p%s-%s'%(e['first_page'],e['last_page']), 's7=%s toc_missing=%s blocked=%s patches=%s'%(e['s7_candidates'],e['toc_missing'],e['blocked'],e['curation_patches_applied']))
    print('   ', ' '.join(e['top_level_citable_labels']))
"
