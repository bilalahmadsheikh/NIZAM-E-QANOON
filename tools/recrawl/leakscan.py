"""leakscan.py [--quiet] DOC... : page apparatus read into the provisions of the active instrument (read-only).

The text gate (textgate.py) asks whether the words are words; side notes, running heads and margin citations are
words, so a document can pass it with its sections full of them (9630, 9662, 9751, 9755, 9768 were released so on
29 Oct and repaired the same night). This asks where the words are. Per provision it flags:
  head   a running head inside the text: 'GAZETTE', '16 | Page', '1972 : Act XXIX]', '[1947 : Sind XLIX'
  cite   a bare margin citation 'XI of 1922.' not preceded by Act / Ordinance / No. / Regulation
  note   an editorial note's words ('Subs. by', 'Inserted vide', 'ibid', 'w.e.f.', ...)
  dup    the instrument opens 4+ units with a repeated-label suffix '_nN_' (a misread level, as in 9630)
Prints one line per document (FLAGS or clean) and, unless --quiet, the first hits. Exit status 1 when any flagged.
--expression N checks one active canonical expression of a compilation; missing/empty expressions fail."""
import argparse,re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

# running heads print in capitals ('GAZETTE'); 'official Gazette' and 'Gazetted Officer' are the law's own words
HEAD = re.compile(r"GAZETTE|\b\d{1,4}\s*\|\s*[Pp]age\b|\b1[6-9]\d\d\s*[:;]\s*(?:Act|Ord|Sind|P\.\s*O|Reg)\.?\s*[IVXLC\d]+\s*\]"
                  r"|\[\s*1[6-9]\d\d\s*[:;]\s*(?:Act|Ord|Sind|P\.\s*O|Reg)\.?\s*[IVXLC\d]+")
CITE = re.compile(r"(?<![A-Za-z.]\s)(?<!Act\s)(?<!No\.\s)(?<!Ordinance\s)(?<!Regulation\s)(?<!Order\s)"
                  r"\b[IVXL]{1,6}\s+of\s+1[6-9]\d\d\.(?=\s|$)")
NOTE = re.compile(r"\b(?:Subs?\.\s*by|Sub\.by|Ins\.\s*by|Inserted\s+vide|Substituted\s+vide|Proviso\s+added|\bibid\b"
                  r"|\(Amdt\.?\)|Omitted\s+by|w\.\s*e\.\s*f\.)", re.I)
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('documents',nargs='+',type=int)
ap.add_argument('--quiet',action='store_true')
ap.add_argument('--expression',type=int,help='Check only this active canonical expression ordinal; missing expressions fail.')
args=ap.parse_args()
quiet,docs,expression=args.quiet,args.documents,args.expression
if expression is not None and expression<0:ap.error('--expression must be nonnegative')
bad = 0
with connect() as conn, conn.cursor() as cur:
    for doc in docs:
        if expression is not None:
            cur.execute('SELECT count(*) FROM instrument WHERE document_id=%s AND expression_ordinal=%s AND is_active AND duplicate_of IS NULL',(doc,expression))
            if cur.fetchone()[0]!=1:sys.exit(f'{doc}/e{expression}: expected exactly one active canonical expression')
        cur.execute("""SELECT subpath(p.path, 3)::text, coalesce(v.text_en, '') FROM instrument i
                         JOIN provision p ON p.instrument_id=i.id AND p.is_active
                         LEFT JOIN provision_version v ON v.provision_id=p.id
                        WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL
                          AND (%s::int IS NULL OR i.expression_ordinal=%s) ORDER BY p.path""", (doc,expression,expression))
        rows = cur.fetchall()
        if expression is not None and not any((text or '').strip()for _path,text in rows):sys.exit(f'{doc}/e{expression}: no nonblank active provision text to check')
        # side: a margin note woven into the text usually repeats the contents heading word for word ('... the
        # following IV of 1878. New section substituted for section 8, Act IV of 1878.'). A contents heading of 18+
        # characters, case as printed, found in a provision after its first few characters is that note.
        cur.execute("""SELECT DISTINCT trim(trailing '.' from regexp_replace(e.printed_heading, '\\s+', ' ', 'g'))
                         FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id
                        WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL
                          AND (%s::int IS NULL OR i.expression_ordinal=%s)
                          AND length(e.printed_heading) >= 18""", (doc,expression,expression))
        heads = [h for (h,) in cur.fetchall() if h and h[0].isupper()]
        hits = []
        for path, text in rows:
            for kind, rx in (("head", HEAD), ("cite", CITE), ("note", NOTE)):
                m = rx.search(text)
                if m:
                    hits.append((kind, path, text[max(0, m.start() - 50):m.end() + 40].replace("\n", " ")))
            flat = re.sub(r"\s+", " ", text)
            for h in heads:
                at = flat.find(h, 8)
                if at > 0:
                    hits.append(("side", path, flat[max(0, at - 50):at + len(h) + 20]))
                    break
        # provisos and explanations number on by design ('prov_Provided_n1_1'); a repeated section, sub-section or
        # clause label is what a misread level leaves
        dups = [p for p, _t in rows if re.search(r"(?:^|\.)(?:s|ss|cl)_[^.]*_n\d+_\d+$", p)]
        kinds = sorted({k for k, _p, _x in hits} | ({"dup"} if len(dups) >= 4 and len(dups) > 0.25 * len(rows) else set()))
        bad += bool(kinds)
        scope=f'{doc}/e{expression}'if expression is not None else str(doc)
        print(f"{scope}: {'FLAGS ' + ','.join(kinds) if kinds else 'clean'} ({len(hits)} hits, {len(dups)} dup-suffix units, "
              f"{len(rows)} provisions)")
        if not quiet:
            for kind, path, ctx in hits[:6]:
                print(f"    {kind} {path}: ...{ctx}...")
sys.exit(1 if bad else 0)
