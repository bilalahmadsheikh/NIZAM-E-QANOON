cd /mnt/e/Nizam_e_Qanoon
D=$(sed -n "${1},${2}p" .artifacts/recrawl-queue/list-one.txt | tr '\n' ' ')
PER_SHEET=6 BELOW=95 KBELOW=45 .venv/bin/python tools/recrawl/s7_sheet.py .artifacts/recrawl-queue/sheets-one/$3 --docs $D
