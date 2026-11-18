"""multi_compare.py DOC... : rebuild a multi-instrument document in memory (the materializer's own prepare) and
compare every expression's tree with the stored active tree: paths, kind, label, heading, text."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from tools.materialize_multi_instrument import prepare
from nizam.storage.db import connect

for doc in map(int, sys.argv[1:]):
    insts, _segs, _m, _b = prepare(doc)
    with connect() as conn, conn.cursor() as cur:
        for inst in insts:
            cur.execute("""SELECT p.path::text, p.kind::text, p.label, coalesce(p.heading,''),
                                  coalesce((SELECT pv.text_en FROM provision_version pv WHERE pv.provision_id=p.id AND pv.operation='original'
                                             ORDER BY lower(pv.validity) NULLS FIRST LIMIT 1),'')
                             FROM instrument i JOIN provision p ON p.instrument_id=i.id AND p.is_active
                            WHERE i.is_active AND i.document_id=%s AND i.expression_ordinal=%s""",
                        (doc, inst.expression_ordinal))
            stored = {r[0]: r[1:] for r in cur.fetchall()}
            built = {p["path"]: (p["kind"], p["label"], p.get("heading") or "", p.get("text") or "") for p in inst.provisions}
            rem, add = set(stored) - set(built), set(built) - set(stored)
            fld = [k for k in set(stored) & set(built) if tuple(stored[k][:3]) != tuple(built[k][:3])]
            txt = [k for k in set(stored) & set(built) if " ".join(stored[k][3].split()) != " ".join(built[k][3].split())]
            print(f"doc {doc} e{inst.expression_ordinal}: stored {len(stored)} built {len(built)} "
                  f"removed {len(rem)} added {len(add)} kind/label/heading {len(fld)} text {len(txt)}"
                  + (f"  e.g. -{sorted(rem)[:5]} +{sorted(add)[:5]} {sorted(fld)[:2]} {sorted(txt)[:2]}" if rem or add or fld or txt else ""))
