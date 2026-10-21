"""Print a window of a page's HTML around the first match of a pattern (read-only)."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools/recrawl")
from probe import get
u, pat = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
st, body = get(u)
m = re.search(pat, body, re.S | re.I)
print(st, len(body), "match at", m.start() if m else None)
if m: print(re.sub(r"\s+", " ", body[max(0, m.start() - 200):m.start() + n]))
