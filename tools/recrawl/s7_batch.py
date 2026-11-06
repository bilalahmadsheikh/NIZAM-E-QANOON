import json, sys
rows = json.load(open("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/s7-e2-single.json", encoding="utf-8"))
a, b = int(sys.argv[1]), int(sys.argv[2])
for i, r in enumerate(rows[a:b], a):
    k = (r['kept_heading'] + ' :: ' + r['kept_text']).replace('\n', ' ')[:200]
    d = (r['demoted_heading'] + ' :: ' + r['demoted_text']).replace('\n', ' ')[:200]
    print(f"[{i}] doc {r['document_id']} #{r['label']} K p{r['kept_page']} {r['kept_path'].split('.',3)[-1]} ({r['kept_len']}) | D p{r['demoted_page']} {r['demoted_path'].split('.',3)[-1]} ({r['demoted_len']})")
    print(f"     K: {k}")
    print(f"     D: {d}")
