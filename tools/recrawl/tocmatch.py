"""tocmatch.py DOC... : for each pending contents gap of DOC, the body provisions whose heading (or first words) best
match the row's printed heading -- a candidate for a found_elsewhere reading (tools/recrawl/tocread.py line FE),
to be confirmed on the page image. Read-only."""
import difflib, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
norm = lambda s: re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (s or "").lower())).strip()   # noqa: E731
with connect() as conn, conn.cursor() as cur:
    for d in map(int, sys.argv[1:]):
        cur.execute("""SELECT g.printed_label, g.printed_heading, g.source_page FROM v_toc_gap_pending g
                        WHERE g.document_id=%s ORDER BY g.source_page, g.printed_label""", (d,))
        gaps = cur.fetchall()
        cur.execute("""SELECT subpath(p.path,3)::text, p.kind::text, p.label, coalesce(p.heading,''), p.first_page,
                              left(coalesce(v.text_en,''), 120)
                         FROM instrument i JOIN provision p ON p.instrument_id=i.id AND p.is_active
                         LEFT JOIN provision_version v ON v.provision_id=p.id
                        WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL
                          AND p.kind IN ('section','article','schedule','chapter','part')""", (d,))
        provs = cur.fetchall()
        print(f"=== {d}")
        for label, heading, page in gaps:
            h = norm(heading)
            scored = sorted(((difflib.SequenceMatcher(None, h, norm(ph or tx[:len(heading or '') + 20])).ratio(),
                              path, kind, pl, ph, fp) for path, kind, pl, ph, fp, tx in provs), reverse=True)[:2]
            print(f"  row {label!r} {heading[:60]!r} (p{page})")
            for s, path, kind, pl, ph, fp in scored:
                print(f"     {s:.2f} {path} [{kind} {pl}] p{fp} {ph[:60]!r}")
