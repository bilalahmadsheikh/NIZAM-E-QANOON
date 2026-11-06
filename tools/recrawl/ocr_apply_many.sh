#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do echo "=== $d"; bash tools/recrawl/ocr_apply.sh $d 2>&1 | grep -E "STOP|NEW=|segmented|valid|^p[0-9]+ section" | head -12; done
