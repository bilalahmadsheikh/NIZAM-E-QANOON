"""Read recent corpus progress from a local Claude JSONL transcript.

Assistant narrative and scoped corpus command summaries only; no environment
values or arbitrary tool-result dumps. This never modifies the transcript.
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('transcript', type=Path)
ap.add_argument('--since', required=True)
args = ap.parse_args()
with args.transcript.open(encoding='utf-8') as stream:
    for line in stream:
        row = json.loads(line)
        if row.get('timestamp','') < args.since or row.get('type')!='assistant':
            continue
        for part in row.get('message',{}).get('content',[]):
            if part.get('type') == 'text':
                print(row['timestamp'],part.get('text',''),flush=True)
            elif part.get('type') == 'tool_use':
                inp = part.get('input',{})
                description = inp.get('description','')
                if description and any(term in description.lower() for term in
                    ('corpus','s7','toc','segment','fingerprint','release','audit','replay')):
                    print(row['timestamp'],'TOOL',part.get('name'),description,flush=True)
