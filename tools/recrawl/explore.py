import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools/recrawl")
from probe import get
st, b = get("https://punjabcode.punjab.gov.pk/en/get_laws")
alpha = sorted(set(h for h in re.findall(r"""href=["']([^"']+)["']""", b) if "alphabetical/all" in h))
print(alpha)
st, b = get(alpha[0])
links = re.findall(r"""href=["']([^"']+)["']""", b)
print(st, len(b), "show_article:", sum(1 for h in links if "show_article" in h))
print(sorted(set(h for h in links if "alphabetical" in h))[:12])
print(re.findall(r"(?:Total|total|records|Records)[^<]{0,40}\d+", b)[:3])
