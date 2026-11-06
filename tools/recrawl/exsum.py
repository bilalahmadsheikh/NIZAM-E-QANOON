"""exsum.py DOC ... : per OCR review export -- pages, decisions, and any non-accept or note (read-only)"""
import json, sys
for d in sys.argv[1:]:
    e = json.load(open(f"/mnt/e/Nizam_e_Qanoon/.artifacts/ocr-review-exports/ocr-review-doc-{d}.json", encoding="utf-8-sig"))
    ds = e["decisions"]; acc = sum(x["decision"] == "accepted" for x in ds)
    print(d, "pages", e["source_page_count"], "decided", len(ds), "accepted", acc)
    for x in ds:
        if x["decision"] != "accepted" or (x.get("reason") or "").strip():
            print("   p%s %s: %s" % (x["page_no"], x["decision"], (x.get("reason") or "")[:300]))
