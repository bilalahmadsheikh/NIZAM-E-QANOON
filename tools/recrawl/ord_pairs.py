"""Count Ordinance -> later same-title Act pairs (read-only)."""
import re, sys, collections
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
def key(t):
    t = (t or "").lower().replace("sind ", "sindh ")
    t = re.sub(r"\b(ordinance|act)\b.*$", "", t)
    return re.sub(r"[^a-z]", "", re.sub(r"^\s*the\s+", "", t))
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT i.id::text, i.kind::text, i.jurisdiction::text, i.year, i.short_title, i.document_id,
                          EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
                     FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL""")
    rows = cur.fetchall()
print(collections.Counter(r[1] for r in rows))
ords = [r for r in rows if re.search(r"\bOrdinance\b", r[4] or "", re.I)]
acts = collections.defaultdict(list)
for r in rows:
    if re.search(r"\bAct\b", r[4] or "") and not re.search(r"\bOrdinance\b", r[4] or "", re.I):
        acts[(r[2], key(r[4]))].append(r)
pairs, multi = [], 0
for o in ords:
    c = [a for a in acts.get((o[2], key(o[4])), []) if a[3] and o[3] and a[3] >= o[3]]
    if len(c) == 1: pairs.append((o, c[0]))
    elif len(c) > 1: multi += 1
print(len(ords), "ordinances;", len(pairs), "with exactly one later same-title Act;", multi, "ambiguous")
for o, a in pairs[:15]:
    print(f"  {o[5]} {o[3]} {o[4][:60]!r} -> {a[5]} {a[3]} {a[4][:60]!r}")
