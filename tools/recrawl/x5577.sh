cd /mnt/e/Nizam_e_Qanoon; P=.artifacts/recrawl-queue/patches
bash tools/recrawl/render.sh 5577 1 70 >/dev/null; bash tools/recrawl/render.sh 5577 4 70 >/dev/null
.venv/bin/python tools/recrawl/span_patch.py $P/spec-5577.json
.venv/bin/python tools/recrawl/merge.py $P/patch-5577d.json $P/patch-5577b.json:1 $P/patch-5577c.json
bash tools/recrawl/patch.sh 5577 apply d 2>&1 | tail -3
.venv/bin/python tools/recrawl/tree.py 5577 section 2>/dev/null
