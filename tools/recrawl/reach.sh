#!/bin/bash
for u in https://sindhlaws.gov.pk/ https://sindhlaws.gov.pk/setup/Publications/PUB-14-000135.pdf https://punjabcode.punjab.gov.pk/ https://punjabcode.punjab.gov.pk/en/get_rules https://pap.gov.pk/ http://balochistan.gov.pk/about/rules/ https://sngad.balochistan.gov.pk/downloads/rules-policies/; do
  printf '%-62s %s\n' "$u" "$(curl -s -o /dev/null -w '%{http_code} %{time_total}' -m 40 -A Mozilla/5.0 "$u")"
done
