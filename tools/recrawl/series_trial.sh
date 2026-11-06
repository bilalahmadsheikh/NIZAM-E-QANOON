#!/bin/bash
# series_trial.sh DOC FIRST_BODY_PAGE [BARE_SERIES] : generate the series-regulation openers (series_openers.py) into
# .artifacts/recrawl-queue/series-DOC.over.json and segment DOC in memory with them (trialseg.py) -- read-only
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
O=.artifacts/recrawl-queue/series-$1.over.json
# CONTENTS=first,last,body : also a reviewed contents region (rows 'none' -- series rows link to nothing), for a document
# whose contents list was read on into the body (doc 7004: the R-1 heading blocks were filed as contents)
.venv/bin/python tools/recrawl/series_openers.py $1 $2 ${3:-} 2>/dev/null | CONTENTS=${CONTENTS:-} .venv/bin/python -c "
import json, os, sys
o = {'source_printed_rule_openers': json.load(sys.stdin)}
c = os.environ.get('CONTENTS')
if c:
    f, l, b = map(int, c.split(','))
    o['source_contents_region'] = {'first_block_id': f, 'last_block_id': l, 'body_start_block_id': b, 'rows': 'none'}
print(json.dumps(o))" > $O
echo "openers: $(grep -o '"label"' $O | wc -l)"
.venv/bin/python tools/recrawl/trialseg.py $1 $O ${KINDS:-part,section,schedule,annexure,appendix} 2>&1 | cut -c1-130
