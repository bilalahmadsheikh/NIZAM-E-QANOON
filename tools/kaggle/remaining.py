"""remaining.py SRC_DS DEST_DS : copy each in-GROUP.zip of SRC_DS into DEST_DS keeping only the PDFs whose stem has no
results yet in E:/nizam-data/ocr/colab/output (the stems another account's runs read). Prints the counts."""
import os, sys, zipfile
OUT = "/mnt/e/nizam-data/ocr/colab/output"
done = set(os.listdir(OUT))
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for z in sorted(f for f in os.listdir(src) if f.startswith("in-") and f.endswith(".zip")):
    zi = zipfile.ZipFile(os.path.join(src, z))
    keep = [n for n in zi.namelist() if n.endswith(".pdf") and os.path.splitext(os.path.basename(n))[0] not in done]
    with zipfile.ZipFile(os.path.join(dst, z), "w", zipfile.ZIP_STORED) as zo:
        for n in keep:
            zo.writestr(n, zi.read(n))
    print(z, len([n for n in zi.namelist() if n.endswith('.pdf')]), "->", len(keep), "unread")
