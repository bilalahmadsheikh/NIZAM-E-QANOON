import json, random, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools/recrawl")
from s7_profile import cls
rows = [json.loads(l) for l in open("/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/s7-units.jsonl", encoding="utf-8")]
want, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 1
pick = [r for r in rows if cls(r).startswith(want)]
random.seed(seed)
for r in random.sample(pick, min(n, len(pick))):
    print(f"--- doc {r['document_id']} lane {r['lane']} label {r['label']!r} kept p{r['kept_page']} {r['kept_path'].split('.',3)[-1]} | demoted p{r['demoted_page']} {r['demoted_path'].split('.',3)[-1]}")
    print("   KEPT   :", (r['kept_heading'] + ' :: ' + r['kept_text'])[:230].replace('\n', ' '))
    print("   DEMOTED:", (r['demoted_heading'] + ' :: ' + r['demoted_text'])[:230].replace('\n', ' '))
