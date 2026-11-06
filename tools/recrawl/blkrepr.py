"""Print repr of block texts (read-only): blkrepr.py DOC BLOCK_ID..."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
doc = int(sys.argv[1]); ids = {int(x) for x in sys.argv[2:]}
for b in legal_write.blocks_for(doc):
    if b["id"] in ids:
        print(b["id"], b["page_no"], repr(b["text"]))
