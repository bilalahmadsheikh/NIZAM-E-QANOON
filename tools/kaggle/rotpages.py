"""rotpages.py SUFFIX GROUP ROTS DOC:PAGE[,PAGE...]... : single-page PDFs of pages printed sideways or upside down,
turned by each of ROTS (comma list of degrees, PDF /Rotate), zipped as in-GROUP.zip into
E:/nizam-data/ocr/kaggle/ds-SUFFIX for `kg.sh dataset SUFFIX in-GROUP.zip`.

One rotation: stems DOC-pageN, imported as page candidates of DOC by tools/colab/import_returned.sh.
Several: stems DOC-pageN-rDEG; after the run tools/kaggle/rotchoose.py keeps, per page, the reading with the most
real words, and only when it beats the page's stored text (the importer scales Surya's boxes onto the page, so the
geometry is approximate). Writes a check render of the first PDF. Read-only on the DB."""
import pathlib, sys, zipfile
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
sfx, group, rots = sys.argv[1], sys.argv[2], [int(r) for r in sys.argv[3].split(",")]
ds = pathlib.Path(f"/mnt/e/nizam-data/ocr/kaggle/ds-{sfx}"); ds.mkdir(parents=True, exist_ok=True)
tmp = ds / "pages"; tmp.mkdir(exist_ok=True)
made = []
with connect() as conn, conn.cursor() as cur:
    for spec in sys.argv[4:]:
        doc, pages = spec.split(":")
        cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (int(doc),))
        src = pymupdf.open(pathlib.Path("/mnt/e/nizam-data") / cur.fetchone()[0])
        for p in map(int, pages.split(",")):
            for rot in rots:
                one = pymupdf.open()
                one.insert_pdf(src, from_page=p - 1, to_page=p - 1)
                one[0].set_rotation((one[0].rotation + rot) % 360)
                out = tmp / (f"{doc}-page{p}.pdf" if len(rots) == 1 else f"{doc}-page{p}-r{rot}.pdf")
                one.save(out)
                made.append(out)
z = ds / f"in-{group}.zip"
with zipfile.ZipFile(z, "w") as zf:
    for f in made:
        zf.write(f, f.name)
check = pymupdf.open(made[0])[0].get_pixmap(dpi=60)
check.save(str(ds / "check.png"))
print(len(made), "pdfs ->", z, "; check render", ds / "check.png")
