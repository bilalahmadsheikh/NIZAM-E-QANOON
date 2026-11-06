#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/gapzone.py .artifacts/recrawl-queue/gaps-now3.jsonl .artifacts/recrawl-queue/gapzone.json $(cat .artifacts/recrawl-queue/list-gz.txt)
