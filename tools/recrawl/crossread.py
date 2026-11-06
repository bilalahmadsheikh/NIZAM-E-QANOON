"""crossread.py [--quiet] [--spec DIR] DOC... : an independent reading of every page (Tesseract 5, eng, 200 dpi) set
against the stored blocks (read-only on the DB).

The stored reading of an E4 page comes from Surya, a model that writes fluent text: over show-through from the reverse
page it can write sentences the page does not print (doc 9834 p23: nine clauses '(ii) The Selection Board shall be
assigned to a suitable party to a suitable body.' between the printed ones). Neither the text gate nor leakscan sees
them -- real words, in place. Per block, the share of its consecutive word pairs that Tesseract also read on the page
is its support: printed blocks measure 0.7-1.0, the invented ones 0.00. A block of 6+ word pairs with support <= 0.15
on a page whose median block support is >= 0.60 (so Tesseract read the page well and the block is simply not there)
is INVENTED. With --spec DIR a blockfix spec DIR/crossread-DOC.json sets those blocks aside, one record per page.
Exit status 1 when any block is flagged."""
import difflib, json, os, re, statistics, subprocess, sys, tempfile
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
import pymupdf

args = sys.argv[1:]
quiet = "--quiet" in args
spec_dir = args[args.index("--spec") + 1] if "--spec" in args else None
# --weak T : also list every block whose word-pair support is under T (a garbled or interleaved reading to read)
weak = float(args[args.index("--weak") + 1]) if "--weak" in args else None
docs = [int(a) for a in args if a.isdigit() and len(a) >= 4]
W = re.compile(r"[A-Za-z]+")
tmp = tempfile.mkdtemp()
bad_any = False
with connect() as conn, conn.cursor() as cur:
    for doc in docs:
        cur.execute("SELECT b.object_key, d.lane FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (doc,))
        key, lane = cur.fetchone()
        pdf = pymupdf.open("/mnt/e/nizam-data/" + key)
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
        rows = cur.fetchall()
        # blocks a reviewed patch already sets aside or rewrites are judged already
        cur.execute("""SELECT jsonb_array_elements_text(evidence->'structural_overrides'->'source_apparatus_blocks')::bigint
                         FROM segmentation_curation_patch WHERE retired_at IS NULL
                          AND evidence->'structural_overrides' ? 'source_apparatus_blocks'
                          AND source_observation_id IN (SELECT source_observation_id FROM instrument
                                                         WHERE document_id=%s AND is_active AND duplicate_of IS NULL)""", (doc,))
        handled = {r[0] for r in cur.fetchall()}
        cur.execute("""SELECT match_text FROM segmentation_curation_patch WHERE retired_at IS NULL AND match_text <> after_text
                          AND source_observation_id IN (SELECT source_observation_id FROM instrument
                                                         WHERE document_id=%s AND is_active AND duplicate_of IS NULL)""", (doc,))
        rewritten = [m for (m,) in cur.fetchall() if m]
        pages = {}
        for i, p, t in rows:
            if i in handled or any(m in (t or "") for m in rewritten):
                continue
            pages.setdefault(p, []).append((i, t or ""))
        flagged = {}
        for p, blocks in sorted(pages.items()):
            if p > len(pdf) or sum(len(W.findall(t)) for _i, t in blocks) < 30:
                continue
            img = os.path.join(tmp, f"{doc}-{p}.png")
            pdf[p - 1].get_pixmap(dpi=200).save(img)
            tess = subprocess.run(["tesseract", img, "-", "-l", "eng"], capture_output=True, text=True).stdout
            tw = [w.lower() for w in W.findall(tess)]
            tflat = re.sub(r"[^a-z]", "", tess.lower())
            os.remove(img)
            pairs_seen = set(zip(tw, tw[1:]))
            scored = []
            for i, t in blocks:
                sw = [w.lower() for w in W.findall(t)]
                pairs = list(zip(sw, sw[1:]))
                if len(pairs) >= 6:
                    scored.append((i, sum(x in pairs_seen for x in pairs) / len(pairs), t))
            if len(scored) < 3:
                continue
            # the upper quartile, not the median: on 9834 p23 nine of eighteen blocks were invented
            med = statistics.quantiles([s for _i, s, _t in scored], n=4)[2]
            if weak is not None:
                for i, sc, t in scored:
                    if 0.15 < sc < weak:
                        print(f"    WEAK p{p} b{i} support {sc:.2f}: {t[:150]!r}".replace(chr(10), ' '))
            inv = [(i, s, t) for i, s, t in scored if s <= 0.15]
            # character coverage: the share of the block's letters lying in runs of 8+ letters that Tesseract also
            # read on the page. Real text Tesseract half-misread keeps long runs (a signature in small capitals);
            # an invented sentence has almost none.
            def cover(t):
                b = re.sub(r"[^a-z]", "", t.lower())
                if not b:
                    return 0.0
                m = difflib.SequenceMatcher(None, b, tflat, autojunk=False)
                return sum(x.size for x in m.get_matching_blocks() if x.size >= 8) / len(b)
            inv = [(i, s, t, round(cover(t), 2)) for i, s, t in inv]
            if med >= 0.60 and inv:
                flagged[p] = (med, inv)
        bad_any |= bool(flagged)
        n = sum(len(v[1]) for v in flagged.values())
        print(f"{doc}: {'INVENTED ' + str(n) + ' block(s) on ' + str(len(flagged)) + ' page(s)' if flagged else 'clean'}"
              f" ({len(pages)} pages, lane {lane})", flush=True)
        if not quiet:
            for p, (med, inv) in flagged.items():
                for i, s, t, c in inv[:4]:
                    print(f"    p{p} (page q3 {med:.2f}) b{i} support {s:.2f} cover {c:.2f}: {t[:120]!r}")
        if spec_dir and flagged:
            spec = {"document_id": doc, "pages": {str(p): {
                "set_aside": [i for i, _s, _t, _c in inv],
                "cover": {str(i): c for i, _s, _t, c in inv},
                "defect": "the OCR model wrote text the page does not print (show-through from the reverse page read as "
                          "sentences); an independent Tesseract reading of the page supports none of its word pairs",
                "observed": f"the page as rendered; Tesseract supports its other blocks (median {med:.2f}) and none of: "
                            + "; ".join(repr(t[:90]) for _i, _s, t, _c in inv)}
                for p, (med, inv) in flagged.items()}}
            json.dump(spec, open(os.path.join(spec_dir, f"crossread-{doc}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
sys.exit(1 if bad_any else 0)
