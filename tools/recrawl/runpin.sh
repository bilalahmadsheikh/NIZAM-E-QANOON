#!/bin/bash
# runpin.sh FROM TO : pin trial over words FROM..TO of list-pin.txt
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$(tr -d "" < .artifacts/recrawl-queue/list-pin.txt | cut -d" " -f$1-$2)
.venv/bin/python tools/recrawl/pintrial.py $D
