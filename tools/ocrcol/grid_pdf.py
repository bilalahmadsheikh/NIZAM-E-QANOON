"""grid_pdf.py IN.pdf OUT.png I [I ...] : selected pages of a PDF side by side (read-only)"""
import sys, pymupdf
src = pymupdf.open(sys.argv[1]); idx = [int(i) for i in sys.argv[3:]]
W = 300; Hh = 430
out = pymupdf.open(); pg = out.new_page(width=W * len(idx), height=Hh)
for j, i in enumerate(idx):
    pg.show_pdf_page(pymupdf.Rect(j * W, 0, (j + 1) * W, Hh), src, i)
pg.get_pixmap(dpi=110).save(sys.argv[2]); print(sys.argv[2])
