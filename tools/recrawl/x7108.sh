cd /mnt/e/Nizam_e_Qanoon; rm -f .artifacts/recrawl-queue/lines/m29.txt
bash tools/recrawl/render.sh 7108 9 70 >/dev/null; bash tools/recrawl/render.sh 7108 10 70 >/dev/null
.venv/bin/python tools/recrawl/auto_lines.py 7108 "Pages 9-10 print 'SCHEDULE I UNDER SECTION 12(2) OF THE NCA ORDINANCE:' with a numbered list of offences '1. Offences under the Pakistan Penal Code, 1860' to '21. Offences the Pakistan Atomic Energy Commission Ordinance, 1965', then the President's and Acting Secretary's signatures. The demoted '{label}' is Schedule item {label} ('{text}'); section {label} of the Ordinance is printed on page {kpage}." .artifacts/recrawl-queue/lines/m29.txt
bash tools/recrawl/readings.sh - .artifacts/recrawl-queue/lines/m29.txt m29 apply | grep -E "refused|recorded|guard"
bash tools/recrawl/rel.sh 7108
