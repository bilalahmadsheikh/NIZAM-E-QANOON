import re, html
b = open('/tmp/drs-big.html', encoding='utf-8', errors='replace').read()
cards = re.split(r"<a href='/documents/document-versions\?docId=", b)[1:3]
for c in cards:
    t = re.sub(r"<svg.*?</svg>", "", c, flags=re.S)
    print(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", t)))[:700])
    print("----")
