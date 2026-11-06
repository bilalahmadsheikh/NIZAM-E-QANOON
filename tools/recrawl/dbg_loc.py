import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
doc, page, match = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
bs = legal_write.blocks_for(doc)
print(len(bs), "blocks;", sum(1 for b in bs if b["page_no"] == page), "on page")
print([b["id"] for b in bs if b["page_no"] == page and match.casefold() in b["text"].casefold()])
for b in bs:
    if b["page_no"] == page and "Librar" in b["text"]:
        print(b["id"], repr(b["text"][:80]))
