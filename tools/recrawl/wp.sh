#!/bin/bash
for h in balochistan.gov.pk sngad.balochistan.gov.pk; do
  for q in 'wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page=1' ; do
    curl -s -m 60 -A Mozilla/5.0 -D /tmp/wp-h.txt -o /tmp/wp.json "https://$h/$q"
    echo "== $h  $(grep -iE '^HTTP|x-wp-total' /tmp/wp-h.txt | tr -d '\r' | tr '\n' ' ')  bytes $(wc -c < /tmp/wp.json)"
    python3 -c "
import json
try:
    d=json.load(open('/tmp/wp.json'))
    print('   sample:', [ (x.get('title',{}).get('rendered','')[:60], x.get('source_url','')[-60:]) for x in d[:3]])
except Exception as e: print('   not json', e)"
  done
done
