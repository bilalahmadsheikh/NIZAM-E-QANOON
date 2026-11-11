"""blockfix.py SPEC.json OUT.json : curation patch records from a page-read transcription, block by block (read-only on
the DB). For an OCR revision whose lines carry side notes, margin citations and misread characters through the middle
of the text, where substring patches would need dozens of fragile locators.

SPEC: {"document_id": D,
       "pages": {"P": {"set_aside": [block ids: running heads, side notes, sheet marks, stray label fragments],
                       "replace": {"block id": "the block as printed, one printed line per line"},
                       "observed": "optional: what else the page prints"}}}

Each replaced block becomes one record whose match_text is the block's whole current text (so the locator is the
block itself and never a fragment that a later patch could reuse); the page's set-aside blocks ride on its first
record. Every record carries the page's render (renders/docD-pP.png, which must exist). Prints a word diff summary."""
import hashlib, json, re, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
# --only ID,ID : re-record just those blocks' transcriptions (after retire_blocks.py retired their first records); the
# pages' set-asides were recorded with the first records and are not repeated
only = next(({int(i) for i in a.split("=", 1)[1].split(",")} for a in sys.argv if a.startswith("--only=")), None)
if only:
    # a page's reviewed structural overrides ride on its first re-recorded block (doc 9713: body start added later)
    spec["pages"] = {p: {"replace": {i: t for i, t in pg.get("replace", {}).items() if int(i) in only},
                         "observed": pg.get("observed"),
                         **{k: pg[k] for k in ("overrides", "overrides_fix") if k in pg},
                         # --keep-aside: the retired first record carried the page's set-asides (doc 9716 p2, 30 Oct:
                         # retiring it let 29 side notes back into the text) -- carry them on the re-record
                         **({"set_aside": pg.get("set_aside", [])} if "--keep-aside" in sys.argv else {})}
                     for p, pg in spec["pages"].items()}
    spec["pages"] = {p: pg for p, pg in spec["pages"].items() if pg["replace"]}
doc = int(spec["document_id"])
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s", (doc,))
    blocks = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    # every locator ever recorded on the document's observations, retired ones included
    cur.execute("""SELECT DISTINCT match_text FROM segmentation_curation_patch WHERE source_observation_id IN
                     (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (doc,))
    used = {r[0] for r in cur.fetchall()}
    # the recorder's 'identical' test is the (page, match_text, before_text) triple, retired rows included
    cur.execute("""SELECT DISTINCT page_no, match_text, before_text FROM segmentation_curation_patch
                    WHERE source_observation_id IN (SELECT source_observation_id FROM instrument
                                                     WHERE document_id=%s AND is_active)""", (doc,))
    used_triples = set(cur.fetchall())
    # the replacement texts already recorded and active, per page: a locator one of them repeats would match that
    # block too once the earlier patch has applied (doc 9713 p3, 30 Oct: 'of the land, and may' matched 2 blocks)
    cur.execute("""SELECT page_no, after_text, match_text FROM segmentation_curation_patch
                    WHERE retired_at IS NULL AND after_text <> match_text AND source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (doc,))
    # records whose locator lies inside a block this spec replaces are retired by retire_overlap.py once this spec
    # is accepted (txgo runs it after blockfix, 30 Oct): their texts are not counted
    _rep_txt = {}
    for _pp, _pg in spec["pages"].items():
        for _b in list(_pg.get("replace") or {}) + list(_pg.get("set_aside") or []):
            if int(_b) in blocks:
                _rep_txt.setdefault(int(_pp), []).append((blocks[int(_b)][1] or "").casefold())
    recorded_news = {}
    for _p, _t, _m in cur.fetchall():
        if any(_m.casefold() in x for x in _rep_txt.get(_p, [])):
            continue
        recorded_news.setdefault(_p, []).append(_t)
    # blocks an active record already rewrites: their stored text is gone by the time a later anchor is applied, so a
    # set-aside never anchors on one (doc 9713 p3, 30 Oct: 'matched 0 blocks')
    cur.execute("""SELECT DISTINCT before_text, page_no, match_text, after_text FROM segmentation_curation_patch
                    WHERE retired_at IS NULL AND after_text <> before_text AND source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (doc,))
    _doomed = lambda pg, m: any(m.casefold() in x for x in _rep_txt.get(pg, []))   # noqa: E731
    # this spec's own whole-block records are not doomed (doc 8935, 3 Nov: hiding them let a set-aside anchor be cut
    # from a block they rewrite -> 'matched 0 blocks')
    _spec_new = {(blocks[int(_b)][1], _t) for _pg in spec["pages"].values()
                 for _b, _t in (_pg.get("replace") or {}).items() if int(_b) in blocks}
    _bef_rows = cur.fetchall()
    _befores = {r[0] for r in _bef_rows if not _doomed(r[1], r[2])
                or any(r[0] in b and r[3] in a for b, a in _spec_new)}
    # replacements already recorded and active, (before, after): a second pass over a spec records only what changed
    # (whole-block records of this spec's own blocks stay: their locator is the whole block, so _doomed would hit them)
    cur.execute("""SELECT before_text, after_text, page_no, match_text,
                          evidence->'structural_overrides'->'source_apparatus_blocks' FROM segmentation_curation_patch
                    WHERE retired_at IS NULL AND source_observation_id IN
                          (SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active)""", (doc,))
    _rows = cur.fetchall()
    # a record whose page set-asides include a block this spec now transcribes is stale: retire_overlap.py retires it,
    # so it is recorded afresh here with the spec's set-asides (doc 9722 p6, 3 Nov: an older record still set aside
    # the Schedule's heading block and the Schedule fell into section 37)
    _spec_rep_ids = {int(_b) for _pg in spec["pages"].values() for _b in (_pg.get("replace") or {})}
    already = {(b, a) for b, a, pg, m, ap in _rows
               if not any(int(x) in _spec_rep_ids for x in (ap or []))
               and (not _doomed(pg, m) or a == m or any(b in ob and a in na for ob, na in _spec_new))}
    rewritten = {b for b, (_p, t) in blocks.items() if t in _befores}
    # set-asides already carried by an active, non-stale record of the page: a page with nothing new to record and
    # all its set-asides recorded needs no anchor record (doc 9588 p2, 3 Nov: a re-run found no fresh anchor line)
    aside_recorded = {}
    for b, a, pg, m, ap in _rows:
        if ap and not any(int(x) in _spec_rep_ids for x in ap):
            aside_recorded.setdefault(pg, set()).update(int(x) for x in ap)
recs = []


def locator(p, old, page_texts, news):
    """match_text for replacing the whole block `old` on page p: the block itself when fresh, else its shortest
    prefix (12+ characters) that is a fresh (page, match, before) triple, occurs (case folded) in exactly one
    original block of the page, and in none of the page's replacement texts -- patches apply one after another, so
    a locator another block's new text repeats would match two blocks (doc 8760, 29 Oct)."""
    f = str.casefold
    for k in [len(old)] + list(range(12, len(old))):
        m = old[:k]
        if len(m.strip()) < 12 or (p, m, old) in used_triples:
            continue
        if sum(f(t).count(f(m)) for t in page_texts) == 1 and not any(f(m) in f(n) for n in news):
            return m
    # no fresh prefix is left (a re-record, docs 9604 and 9596): any single-line window of 12+ characters will do
    for ln in old.split("\n"):
        for k in range(len(ln) - 11):
            for e in range(len(ln), k + 11, -1):
                m = ln[k:e]
                if m.strip() != m or len(m) < 12 or (p, m, old) in used_triples:
                    continue
                if sum(f(t).count(f(m)) for t in page_texts) == 1 and not any(f(m) in f(n) for n in news):
                    return m
    # ... and a window that spans a line break
    for k in range(len(old) - 11):
        for e in range(len(old), k + 11, -1):
            m = old[k:e]
            if "\n" not in m or m.strip() != m or (p, m, old) in used_triples:
                continue
            if sum(f(t).count(f(m)) for t in page_texts) == 1 and not any(f(m) in f(n) for n in news):
                return m
    return None
for p, pg in sorted(spec["pages"].items(), key=lambda kv: int(kv[0])):
    p = int(p)
    render = pg.get("render", f".artifacts/release-work-2026-09-24/claude/renders/doc{doc}-p{p}.png")
    sha = hashlib.sha256((ROOT / render).read_bytes()).hexdigest()
    aside = [int(i) for i in pg.get("set_aside", [])]
    for i in aside:
        assert blocks[i][0] == p, (i, "is not on page", p)
    reps = [(int(i), t) for i, t in pg.get("replace", {}).items()]
    if not reps:
        # a page with only set-asides: the locator is the longest set-aside block's own text when it is 12+ characters,
        # occurs once in the document and was never a locator; else the first such line of another block on the page
        def ok(s):
            # the recorder matches with whitespace collapsed (and case folded): count the same way
            fl = lambda x: re.sub(r"\s+", " ", x).casefold()   # noqa: E731
            # the anchor is its own match, before and after text: all three share one index row (~2.7 kB; doc 9848's
            # printed Index, a 3.6 kB column per page, failed the recorder's insert)
            return (len(s.strip()) >= 12 and s not in used and 3 * len(s.encode()) <= 2500
                    and sum(fl(t).count(fl(s)) for _p, t in blocks.values()) == 1)
        # the set-aside blocks longest first (a re-run finds the longest already spent as a locator, doc 9572 p4), then
        # a line of the page's other blocks, then -- a page set aside whole -- a line of a set-aside block
        i = next((b for b in sorted(aside, key=lambda b: -len(blocks[b][1]))
                  if b not in rewritten and ok(blocks[b][1])), None)
        if i is not None:
            reps = [(i, None)]
        else:
            line = next(((b, ln) for b, (bp, t) in sorted(blocks.items(), key=lambda kv: kv[0] in aside)
                         if bp == p and b not in rewritten
                         for ln in (t.split("\n")[0][:40], *t.split("\n")) if ok(ln) and len(ln) <= 80), None)
            assert line, (p, "no unique line on the page to anchor the set-asides")
            reps = [(line[0], ("__line__", line[1]))]
    pieces = []
    for i, new in reps:
        page, old = blocks[i]
        assert page == p, (i, "is not on page", p)
        if isinstance(new, tuple):   # the set-asides' anchor line from another block, unchanged
            pieces.append((i, new[1], None))
            continue
        if new == old:   # kept as printed ('CHAPTER I.'): no record, and not set aside
            pieces.append((i, old, new))
            continue
        assert len(old.strip()) >= 12, (i, "block text under 12 characters; set it aside or merge it", old)
        # a long block is cut in two as well: one locator plus its replacement must fit the patch table's index row
        if 2 * len(old.encode()) + len((new or "").encode()) > 2500 and new is not None:   # match+before+after share one index row (~2.7 kB)
            # a locator once recorded (even retired) is 'identical' to the recorder for ever: re-record a block under
            # two fresh locators -- its first and second halves, cut at a line break -- each carrying its share of the
            # new text (the new text cut at its last line break, or its last space). Neither half's new text may hold
            # the other half's locator, or the result would depend on the order the replay applies them.
            # prefer cuts whose following piece occurs in no other block of the page (doc 9845 p6: the OCR read
            # section 31 twice, the two blocks sharing their whole tail). A block too long for two pieces is cut
            # into as many as it needs (doc 9830 p2: one 4.8 kB block holding a whole page), old and new text alike
            # at line breaks (or spaces) nearest equal shares.
            _pg = [t for b, (bp, t) in blocks.items() if bp == p and b != i]
            ocuts = [k for k, ch in enumerate(old) if ch == "\n" and 12 <= k <= len(old) - 12]
            ocuts_f = [c for c in ocuts if not any(old[c:c + 40].casefold() in t.casefold() for t in _pg)] or ocuts
            # line breaks, and spaces too: a page-long paragraph has too few breaks for the pieces it needs (doc 9594 p13)
            ncuts = [k for k, ch in enumerate(new) if ch in "\n "]

            def _split(text, cand, n):
                ks, last = [], 0
                for q in range(1, n):
                    want = len(text) * q // n
                    c = min((c for c in cand if c > last), key=lambda c: abs(c - want), default=None)
                    if c is None:
                        return None
                    ks.append(c); last = c
                bounds = [0] + ks + [len(text)]
                return [text[a:b] for a, b in zip(bounds, bounds[1:])]
            _ocut_sets = [ocuts_f, [k for k, ch in enumerate(old) if ch in "\n " and 12 <= k <= len(old) - 12]]
            for _oc in _ocut_sets:   # a block with too few line breaks may be cut at spaces too (doc 9849 p6, 7 Nov)
                for n in range(2, 16):
                    op, np_ = _split(old, _oc, n), _split(new, ncuts, n)
                    if op and np_ and all(2 * len(o.encode()) + len(x.encode()) <= 2500 for o, x in zip(op, np_)):
                        break
                else:
                    continue
                break
            else:
                raise AssertionError((i, "block cannot be cut into pieces small enough"))
            for a, o in enumerate(op):
                assert old.count(o) == 1 and len(o.strip()) >= 12, (i, "piece not unique in the block", o[:40])
                assert not any(o in x for b, x in enumerate(np_) if b != a), (i, "a piece's new text holds another locator")
            pieces += [(i, o, x) for o, x in zip(op, np_)]
        else:
            pieces.append((i, old, new))
    # a block already reading exactly as transcribed needs no record (the recorder refuses a no-op, and the page's
    # set-asides must not ride on a refused record); if nothing is left, the set-asides take an anchor as above
    real = [x for x in pieces if (x[2] is None or x[2] != x[1]) and (x[1], x[2]) not in already]
    if not real and aside and set(aside) <= aside_recorded.get(p, set()):
        aside = []
    if not real and aside:
        def ok2(s):
            fl = lambda x: re.sub(r"\s+", " ", x).casefold()   # noqa: E731
            # nor a line an active record's replacement already holds: the anchor would then match two blocks (doc 9608 p7)
            return (len(s.strip()) >= 12 and s not in used and sum(fl(t).count(fl(s)) for _p, t in blocks.values()) == 1
                    and not any(fl(s) in fl(t) for t in recorded_news.get(p, []))
                    # nor a line this spec's own transcription of the page holds (doc 9722 p5, 3 Nov: 'Penalty not
                    # exceeding five hundred rupees.' set aside, and printed again in row 1 of the rewritten block)
                    # (a replacement identical to its block is no new text -- doc 9855 pp3-17, 5 Nov: every block
                    # pinned unchanged so only the running heads are set aside)
                    and not any(fl(s) in fl(t) for _b, t in (pg.get("replace") or {}).items()
                                if int(_b) not in blocks or blocks[int(_b)][1] != t))
        line = next(((b, ln) for b, (bp, t) in sorted(blocks.items()) if bp == p and b not in rewritten
                     for ln in (t.split("\n")[0][:40], *t.split("\n")) if ok2(ln) and len(ln) <= 80), None)
        assert line, (p, "no anchor for the set-asides")
        real = [(line[0], line[1], None)]
    pieces = real
    # what the page's other blocks read once the active whole-block records have applied (doc 9845 p6: a duplicate
    # reading replaced first so the real one has a unique locator)
    _cur = {t: a for t, a in already if t is not None and a is not None}
    page_texts = [t if b in [x[0] for x in pieces] else _cur.get(t, t) for b, (bp, t) in blocks.items() if bp == p]
    for n, (i, old, new) in enumerate(pieces):
        news = [x for j, _o, x in pieces if x and j != i]   # a block's own new text may repeat its locator
        news += [t for t in recorded_news.get(p, []) if t not in (new, old)]
        m = old if new is None else locator(p, old, page_texts, news)
        assert m, (i, "no fresh unique locator in the block", old[:60])
        r = {"document_id": doc, "page_no": p, "match_text": m, "before_text": old,
             "after_text": old if new is None else new}
        if new is None and not aside:   # an anchor for page-level overrides only
            r.update(defect=pg.get("defect", "the page's structure was misread"), fixes="anchor unchanged",
                     observed=f"Page {p} prints " + pg.get("observed", ""))
        elif new is None:
            r.update(defect="page furniture and margin notes were read into the provisions' text",
                     fixes="rule reviewed_apparatus_block: the running head, margin notes and stray fragments are set aside",
                     observed=f"Page {p} prints " + "; ".join(repr(blocks[b][1].replace(chr(10), ' ')) for b in aside)
                              + " outside the text column")
        else:
            r.update(defect="the OCR reading of this block is wrong: margin notes, citations or stray marks were read into "
                            "the line, or characters were misread",
                     fixes="parser-input correction: the block is replaced by the page's printed text, line for line",
                     observed=f"Page {p} prints: '{new.replace(chr(10), ' ')}'")
            if len(new) < 40 and pg.get("observed"):
                # a short piece ('context,—') is no observation on its own to the recorder: say what stands round it
                r["observed"] += "; round it the page prints " + pg["observed"]
        if n == 0 and pg.get("overrides"):
            # page-level reviewed structure ('source_division_openers', ...) rides on the page's first record
            r.update(pg["overrides"])
            r["fixes"] += "; " + pg.get("overrides_fix", "reviewed structural overrides: " + ", ".join(pg["overrides"]))
        if n == 0 and aside:
            r["source_apparatus_blocks"] = aside
            r["fixes"] += "; rule reviewed_apparatus_block sets aside the page's running head, margin notes and stray fragments"
            if pg.get("observed"):
                r["observed"] += ". " + pg["observed"]
        r.update(render=render, render_sha256=sha)
        recs.append(r)
json.dump(recs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"doc {doc}: {len(recs)} records, {sum(len(pg.get('set_aside', [])) for pg in spec['pages'].values())} blocks set aside, "
      f"{sum(len(pg.get('replace', {})) for pg in spec['pages'].values())} blocks re-read")
