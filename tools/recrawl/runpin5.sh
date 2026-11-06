#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/pintrial5.py $(cat .artifacts/recrawl-queue/list-v5.txt) > .artifacts/recrawl-queue/pintrial5.log 2>&1
