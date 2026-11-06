# Nizam-e-Qanoon Surya run (Colab GPU, Drive transport) -- pasted into a cell by the lead via colab-mcp, after the
# engine-setup cell. Inputs: MyDrive/nizam-ocr/in-<priority>.zip (copied there from E:/nizam-data/ocr/colab by Drive
# for desktop); processed in priority order, waiting for zips still uploading. Outputs:
# MyDrive/nizam-ocr/out/<stem>/results.json (synced back to G:/My Drive/nizam-ocr/out). Resumable: done stems skip.
import json, os, pathlib, shutil, subprocess, time, zipfile
from google.colab import drive
if not pathlib.Path("/content/drive/MyDrive").exists():
    drive.mount("/content/drive")
D = pathlib.Path("/content/drive/MyDrive/nizam-ocr"); OUT = D / "out"; OUT.mkdir(parents=True, exist_ok=True)
W = pathlib.Path("/content/nz"); W.mkdir(exist_ok=True)
SURYA = shutil.which("surya_ocr"); CH = 20
ORDER = ["1-pages", "2-small", "5-extra", "3-holes", "4-large"]
import pypdfium2 as pdfium


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    with open(D / "run.log", "a") as f:
        f.write(line + "\n")


def run_one(pdf):
    stem = pdf.stem; final = OUT / stem / "results.json"
    if final.exists():
        return "skip"
    n = len(pdfium.PdfDocument(str(pdf))); merged = []
    for s in range(0, n, CH):
        e = min(s + CH, n) - 1; part = W / "work" / stem / f"p{s + 1}-{e + 1}"; rj = part / stem / "results.json"
        if not rj.exists():
            r = subprocess.run([SURYA, str(pdf), "--page_range", f"{s}-{e}", "--output_dir", str(part), "--keep_server"],
                               capture_output=True, text=True)
            if r.returncode or not rj.exists():
                log(f"FAIL {stem} pp{s + 1}-{e + 1}: {r.stderr[-300:]}"); return "fail"
        res = json.loads(rj.read_text(encoding="utf-8"))[stem]
        if [x["page"] for x in res] != list(range(1, e - s + 2)):
            log(f"FAIL {stem} pp{s + 1}-{e + 1}: page numbers"); return "fail"
        for i, x in enumerate(res):
            x["page"] = s + 1 + i; merged.append(x)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = W / f"{stem}.results.json"; tmp.write_text(json.dumps({stem: merged}, ensure_ascii=False), encoding="utf-8")
    shutil.copy(tmp, final); shutil.rmtree(W / "work" / stem, ignore_errors=True)
    return f"{n}p"


t_all = time.time(); n_done = 0
for k in ORDER:
    z = D / f"in-{k}.zip"
    for _ in range(240):                      # wait up to 2 h for a zip still uploading
        try:
            if z.exists() and zipfile.is_zipfile(z):
                break
        except OSError:
            pass
        time.sleep(30)
    else:
        log(f"=== {z.name} never arrived; skipped"); continue
    src = W / "in" / k
    if not src.exists():
        src.mkdir(parents=True); zipfile.ZipFile(z).extractall(src)
    pdfs = sorted(src.glob("*.pdf")); log(f"=== {k}: {len(pdfs)} pdfs")
    for pdf in pdfs:
        t0 = time.time(); st = run_one(pdf)
        if st not in ("skip", "fail"):
            n_done += 1; log(f"{k} {pdf.stem}: {st} in {time.time() - t0:.0f}s ({n_done} done)")
log(f"=== finished: {n_done} in {(time.time() - t_all) / 60:.0f} min")
