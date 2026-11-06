#!/bin/bash
# tops.sh DOC [DOC ...] : toplabels for each doc, one paragraph per doc (read-only)
for d in "$@"; do echo "== $d"; bash /mnt/e/Nizam_e_Qanoon/tools/recrawl/toplabels.sh $d; echo; done
