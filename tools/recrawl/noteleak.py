"""noteleak.py DOC... : amendment-note text read into provisions (read-only). Flags an active provision of the active
instrument whose text holds an editorial note -- 'Subs. by', 'Sub.by', 'Ins. by', 'Inserted vide', 'added by',
'Proviso added', 'ibid', '(Amdt.)', 'Omitted by', 'w.e.f.' -- with the note's words, so a footnote the segmenter's
pattern did not take ('1New cl. (4) added by ...', a note's second line) is caught before a release, not after.
Legal text says 'inserted by' and 'substituted by' too: every hit is read, none is fixed blind."""
import re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
NOTE = re.compile(r"\b(?:Subs?\.\s*by|Sub\.by|Ins\.\s*by|Inserted\s+vide|Substituted\s+vide|added\s+by\s+the|Proviso\s+added"
                  r"|\bibid\b|\(Amdt\.?\)|Omitted\s+by|w\.\s*e\.\s*f\.)", re.I)
with connect() as conn, conn.cursor() as cur:
    for doc in map(int, sys.argv[1:]):
        cur.execute("""SELECT subpath(p.path, 3)::text, v.text_en FROM instrument i
                         JOIN provision p ON p.instrument_id=i.id AND p.is_active
                         JOIN provision_version v ON v.provision_id=p.id
                        WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL ORDER BY p.path""", (doc,))
        hits = [(path, m.start(), text) for path, text in cur.fetchall() for m in [NOTE.search(text or "")] if m]
        print(f"doc {doc}: {len(hits)} provision(s) with note words")
        for path, at, text in hits[:12]:
            print(f"   {path}: ...{text[max(0, at - 60):at + 90]!r}")
