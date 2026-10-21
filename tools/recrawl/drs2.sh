#!/bin/bash
grep -oiE '(href|src|data-url|data-src|action)="[^"]+"' /tmp/drs-d.html | grep -viE 'fonts|svg|css|\.png|favicon|facebook|linkedin|x\.com|mailto|subCategory|RegulationGroup' | sort -u | head -30
grep -oiE '[^"'"'"' ]*(pdf|download|stream|viewer|blob)[^"'"'"' <]*' /tmp/drs-d.html | sort -u | head -20
curl -s -L -o /tmp/drs-big.html -m 180 -A Mozilla/5.0 'https://drs.molaw.gov.pk/documents?subCategory=Rules&pageNumber=1&pageSize=500'
echo "pageSize=500 -> $(grep -oE 'document-versions\?docId=[0-9]+' /tmp/drs-big.html | sort -u | wc -l) documents"
