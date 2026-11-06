#!/bin/bash
# s7src.sh READINGS [--apply]
cd /mnt/e/Nizam_e_Qanoon && ./.venv/bin/python tools/adjudicate_s7_from_source.py --readings "$@"
