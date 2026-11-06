#!/bin/bash
# pindefault.sh DOC [...] : return held docs to the default profile, then replay
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$(echo "$@" | tr " " ",")
.venv/bin/python tools/pin_segmentation_profile.py --documents $D --profile default --reason "recrawl queue 2026-10-23: unreleased-v4 trial left more pending units; back to default" --apply 2>&1 | tail -1
bash tools/recrawl/replay.sh "$@"
