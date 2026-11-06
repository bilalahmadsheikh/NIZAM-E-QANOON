"""rotchoose.py RUN_OUT_DIR [--apply] : after a turned-page run (tools/kaggle/rotpages.py with several rotations), keep
for each page the reading with the most real words -- and only when it clearly beats the page's stored text.

Real words: the share of a page's words in a vocabulary of the words printed 30+ times across the released corpus
(cached in E:/nizam-data/ocr/kaggle/vocab.txt). A reading is kept when its share is at least 0.60 and at least 0.15
above the stored text's; it is then written as colab/output/DOC-pageN/results.json under the stem DOC-pageN, which
tools/colab/import_returned.sh imports as that page's Surya candidate. A page whose stored text is already as good (a
genuine list of names the detector flagged) keeps it. Prints one line per page; writes only with --apply."""
import html as _html, json, pathlib, re, sys
from collections import Counter
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

run, apply = pathlib.Path(sys.argv[1]), "--apply" in sys.argv
OUT = pathlib.Path("/mnt/e/nizam-data/ocr/colab/output")
VOC = pathlib.Path("/mnt/e/nizam-data/ocr/kaggle/vocab.txt")
words = lambda t: [w.lower() for w in re.findall(r"[A-Za-z]{2,}", t or "")]   # noqa: E731
with connect() as conn, conn.cursor() as cur:
    if not VOC.exists():
        freq = Counter()
        cur.execute("""SELECT v.text_en FROM v_release_instrument r JOIN provision p ON p.instrument_id=r.id
                        AND p.is_active JOIN provision_version v ON v.provision_id=p.id WHERE random() < 0.2""")
        for (t,) in cur:
            freq.update(words(t))
        VOC.write_text("\n".join(sorted(w for w, n in freq.items() if n >= 30)))
    vocab = set(VOC.read_text().split())
    share = lambda ws: sum(w in vocab for w in ws) / len(ws) if ws else 0.0   # noqa: E731
    pages = {}
    for f in run.glob("**/results.json"):
        for stem, res in json.load(open(f)).items():
            m = re.fullmatch(r"(\d+)-page(\d+)-r(\d+)", stem)
            if not m:
                continue
            text = " ".join(re.sub(r"<[^>]+>", " ", _html.unescape(b.get("html") or ""))
                            for page in res for b in page.get("blocks", []))
            pages.setdefault((int(m[1]), int(m[2])), []).append((share(words(text)), int(m[3]), stem, res))
    kept = 0
    for (d, p), variants in sorted(pages.items()):
        cur.execute("SELECT string_agg(text, ' ') FROM text_block WHERE document_id=%s AND page_no=%s", (d, p))
        stored = share(words(cur.fetchone()[0]))
        best = max(variants)
        ok = best[0] >= 0.60 and best[0] >= stored + 0.15
        print(f"{d} p{p}: stored {stored:.0%}  " + "  ".join(f"r{r} {s:.0%}" for s, r, _, _ in sorted(variants, key=lambda v: v[1]))
              + f"  -> {'KEEP r%d' % best[1] if ok else 'stored'}")
        if ok:
            kept += 1
            if apply:
                dst = OUT / f"{d}-page{p}"; dst.mkdir(parents=True, exist_ok=True)
                (dst / "results.json").write_text(json.dumps({f"{d}-page{p}": best[3]}))
    print(kept, "of", len(pages), "pages take a turned reading", "(written)" if apply else "(dry run)")
