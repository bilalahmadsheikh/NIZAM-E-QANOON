"""G_blk.py DOC BLOCK [BLOCK ...] : repr of the raw text of blocks (read-only; agent G)."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
want = set(map(int, sys.argv[2:]))
for b in legal_write.blocks_for(int(sys.argv[1])):
    if b["id"] in want:
        print(b["id"], f"p{b['page_no']}", repr(b["text"][:400]))
