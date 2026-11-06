#!/bin/bash
# gb.sh DOC : grepblk with the pattern stored in .artifacts/recrawl-queue/pat.txt (avoids shell quoting)
cd /mnt/e/Nizam_e_Qanoon && PYTHONPATH=. .venv/bin/python tools/recrawl/grepblk.py "$1" "$(cat .artifacts/recrawl-queue/pat.txt)"
