#!/bin/bash
# pend.sh DOC [DOC ...] : current pending S7 units of docs, triaged (sheets in /tmp/pend)
cd /mnt/e/Nizam_e_Qanoon; rm -rf /tmp/pend; PER_SHEET=6 .venv/bin/python tools/recrawl/s7_sheet.py /tmp/pend --docs "$@" >/dev/null 2>&1
.venv/bin/python tools/recrawl/triage.py /tmp/pend/manifest.json
