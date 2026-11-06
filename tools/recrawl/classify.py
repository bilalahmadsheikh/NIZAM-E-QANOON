"""Classify every pending S7 unit by the demoted unit's text shape (read-only). classify.py OUT.jsonl"""
import json, re, sys, collections
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
PAT = [("distlist", r"^(?:The\s+)?(?:Principal\s+)?(?:Private\s+)?(?:Secretary|Section Officer|Registrar|Accountant General|Chief\s+(?:Secretary|Controller)|Director|Deputy|Additional|Under Secretary|P\.?S\.? to|PS to|All\s+(?:Deputy|Divisional|Administrative|Heads|District)|Master File|Office (?:Copy|order)|Personal File|The\s+(?:Senior Member|Advocate General|Controller|Manager|Comptroller|Commissioner))"),
       ("footnote", r"^(?:Subs\.|Ins\.|Added|Omitted|Rep\.|Substituted|Inserted|Sub\.)\s"),
       ("blank", r"^\W*$")]
with connect() as conn, conn.cursor() as cur:
    cur.execute(r"""SELECT c.id::text, c.document_id, c.printed_label, c.source_page, d.lane,
                          coalesce(cv.text_en,''), coalesce(cp.heading,''), length(coalesce(kv.text_en,'')),
                          left(regexp_replace(coalesce(kv.text_en,''),'\s+',' ','g'),60), coalesce(kp.heading,'')
                     FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id
                     JOIN document d ON d.id=c.document_id
                     JOIN provision cp ON cp.id=c.candidate_provision_id LEFT JOIN provision_version cv ON cv.provision_id=cp.id
                     JOIN provision kp ON kp.id=c.canonical_provision_id LEFT JOIN provision_version kv ON kv.provision_id=kp.id""")
    rows = cur.fetchall()
cnt = collections.Counter()
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    for cid, doc, label, page, lane, dt, dh, klen, kt, kh in rows:
        t = re.sub(r"\s+", " ", (dh + " " + dt).strip())
        cls = next((n for n, p in PAT if re.search(p, t, re.I)), "other")
        cnt[cls] += 1
        fh.write(json.dumps({"cid": cid, "doc": doc, "label": label, "page": page, "lane": lane, "cls": cls,
                             "dlen": len(dt), "dtext": t[:140], "klen": klen, "ktext": (kh + " " + kt)[:80]},
                            ensure_ascii=False) + "\n")
print(len(rows), "units", dict(cnt), len({r[1] for r in rows}), "docs")
