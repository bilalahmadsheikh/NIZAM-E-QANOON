#!/bin/bash
# pinv5.sh DOC [DOC ...] : pin held documents to profile unreleased-v5 (reviewed division openers etc.), then replay
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
D=$(echo "$@" | tr ' ' ',')
.venv/bin/python tools/pin_segmentation_profile.py --documents $D --profile unreleased-v5 \
  --reason "recrawl queue 2026-10-23: held document needs reviewed source rules (schedule/division openers in blocks) that only unreleased-v5 carries (contents-promised next section); owner standing delegation 'whatever is best'" --apply 2>&1 | tail -2
bash tools/recrawl/replay.sh "$@"
