#!/bin/bash
curl -s -L -o /tmp/drs-r.html -m 90 -A Mozilla/5.0 'https://drs.molaw.gov.pk/documents?subCategory=Rules'
echo "rules page bytes $(wc -c < /tmp/drs-r.html)"
grep -oE 'href="[^"]*(page|Page|pageNumber|PageNumber|skip)[^"]*"' /tmp/drs-r.html | sort -u | head -8
grep -oE 'document-versions\?docId=[0-9]+&(amp;)?versionId=[0-9]+' /tmp/drs-r.html | sort -u | wc -l
grep -oE '[0-9,]+ (results|records|documents|items)|of [0-9,]+' /tmp/drs-r.html | head -5
python3 - <<'PY'
import re,html
b=open('/tmp/drs-r.html',encoding='utf-8',errors='replace').read()
i=b.find('document-versions?docId')
print(re.sub(r'\s+',' ',html.unescape(re.sub(r'<script.*?</script>','',b[i-1500:i+800],flags=re.S)))[:2200])
PY
D=$(grep -oE 'document-versions\?docId=[0-9]+&(amp;)?versionId=[0-9]+' /tmp/drs-r.html | head -1 | sed 's/&amp;/\&/')
curl -s -L -o /tmp/drs-d.html -m 90 -A Mozilla/5.0 "https://drs.molaw.gov.pk/documents/$D"
echo "doc $D bytes $(wc -c < /tmp/drs-d.html)"
grep -oiE '(href|src)="[^"]*(\.pdf|download|Download|file|File)[^"]*"' /tmp/drs-d.html | sort -u | head -10
