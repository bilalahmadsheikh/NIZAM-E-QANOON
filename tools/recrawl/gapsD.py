"""Agent D helper (read-only): every contents entry of a document with its link state,
then the section-level tree with provision ids.

    python tools/recrawl/gapsD.py DOC [--tree] [--kinds section,article,...]"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

args = sys.argv[1:]
doc = int(args[0])
show_tree = "--tree" in args
kinds = "section,article,rule,regulation,paragraph,schedule,part,chapter,order"
if "--kinds" in args:
    kinds = args[args.index("--kinds") + 1]
kinds = kinds.split(",")
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT i.id::text, i.short_title, d.page_count FROM instrument i JOIN document d ON d.id=i.document_id "
                "WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL", (doc,))
    insts = cur.fetchall()
    for inst, title, pages in insts:
        print(f"=== doc {doc} inst {inst} {title!r} pages={pages}")
        cur.execute("""
          SELECT e.id, e.ordinal, e.entry_kind, e.printed_label, coalesce(e.printed_heading,''), e.source_page,
                 e.printed_page, p.kind::text, p.label, p.first_page,
                 EXISTS (SELECT 1 FROM v_toc_gap_pending g WHERE g.toc_entry_id=e.id),
                 (SELECT a.resolution FROM v_toc_gap_adjudication_latest a WHERE a.toc_entry_id=e.id LIMIT 1)
            FROM instrument_toc_entry e LEFT JOIN provision p ON p.id=e.provision_id
           WHERE e.instrument_id=%s ORDER BY e.ordinal""", (inst,))
        rows = cur.fetchall()
        near = set()
        for k, r in enumerate(rows):
            if r[10]:
                near.update(range(k - 2, k + 3))
        for k, (eid, ordn, ek, lab, head, sp, pp, pk, pl, pfp, pend, res) in enumerate(rows):
            if "--near" in args and k not in near:
                continue
            if pend:
                st = f"GAP   entry={eid}"
            elif pk:
                st = f"-> {pk} {pl} p{pfp}"
            else:
                st = f"settled:{res} entry={eid}"
            print(f"  #{ordn:<3} c.p{sp} {ek:8} {lab!r:8} {head[:60]!r:64} {st}")
        if show_tree:
            cur.execute(r"""SELECT p.id::text, p.first_page, p.kind::text, subpath(p.path,3)::text, p.label,
                                   coalesce(p.heading,''),
                                   left(regexp_replace(coalesce(v.text_en,''),'\s+',' ','g'),90),
                                   length(coalesce(v.text_en,''))
                              FROM provision p LEFT JOIN provision_version v ON v.provision_id=p.id
                             WHERE p.instrument_id=%s AND p.is_active AND p.kind::text = ANY(%s)
                               AND nlevel(p.path) > 3
                             ORDER BY p.first_page, p.path""", (inst, kinds))
            for r in cur.fetchall():
                print(f"  {r[0]} p{r[1]} {r[2]:8} {r[3]:24} [{r[7]}c] {r[5][:40]!r} :: {r[6]}")
