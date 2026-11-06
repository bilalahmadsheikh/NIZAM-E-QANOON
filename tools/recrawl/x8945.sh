cd /mnt/e/Nizam_e_Qanoon; P=.artifacts/recrawl-queue/patches
.venv/bin/python tools/recrawl/span_patch.py $P/spec-8945c.json
.venv/bin/python tools/recrawl/merge.py $P/patch-8945d.json $P/patch-8945b.json $P/patch-8945c.json
bash tools/recrawl/patch.sh 8945 apply d 2>&1 | grep -v locator | tail -4
bash tools/recrawl/patch.sh 8786 apply b 2>&1 | grep -v locator | tail -4
.venv/bin/python tools/recrawl/tree.py 8945 section,schedule 2>/dev/null
.venv/bin/python tools/recrawl/tree.py 8786 section 2>/dev/null | head -4
