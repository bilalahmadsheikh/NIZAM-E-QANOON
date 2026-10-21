"""Read-only: newly released recrawl instruments that share jurisdiction + folded title + year with ANOTHER released
instrument (a possible second copy of one law)."""
import collections, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon"); sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools/recrawl")
from diff_listing import title_key
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT i.id::text, i.jurisdiction::text, i.short_title, i.year, o.scraper_version='recrawl-2026-10-20/1', o.source_id
                     FROM v_release_instrument r JOIN instrument i ON i.id=r.id JOIN source_observation o ON o.id=i.source_observation_id""")
    rows = cur.fetchall()
groups = collections.defaultdict(list)
for iid, jur, title, year, new, sid in rows:
    groups[(jur, title_key(title, sid), year)].append((new, title, iid))
hits = [(k, v) for k, v in groups.items() if len(v) > 1 and any(n for n, _, _ in v)]
print("groups with a new release and another release of the same folded title+year:", len(hits))
for k, v in hits[:25]:
    print(" ", k[0], k[2], [("NEW" if n else "old", t[:60]) for n, t, _ in v])
