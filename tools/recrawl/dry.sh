#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python -m nizam.workers.segment --document $1 --redo --include-review --dry-run 2>&1 | grep -iE "error|fail|Error" | head -5
