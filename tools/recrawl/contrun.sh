#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/conttrial.py $(cat .artifacts/recrawl-queue/list-cont.txt)
