#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/contfind.py .artifacts/recrawl-queue/contfind.json $(cat .artifacts/recrawl-queue/list-allheld.txt) > .artifacts/recrawl-queue/contfind-all.txt
grep -c ": first" .artifacts/recrawl-queue/contfind-all.txt
