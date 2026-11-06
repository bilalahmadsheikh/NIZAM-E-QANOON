"""Column-band detection for scanned two-column pages (prototype; pure pymupdf, no numpy).

bands(page) -> list of ("full"|"left"|"right", pymupdf.Rect) in reading order, or None for a one-column page.
A gutter is a near-empty vertical band in the middle 35-65% of the page width; full-page vertical rules are ignored.
Rows whose ink crosses the gutter form full-width bands (mastheads, titles spanning both columns); the rest are
two-column bands, read left column then right column."""
import pymupdf

DPI = 50


def _gray(page):
    pm = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    return pm.width, pm.height, pm.samples, pm.stride


def bands(page, debug=False):
    W, H, s, st = _gray(page)
    dark = [[s[y * st + x] < 165 for x in range(W)] for y in range(H)]
    rows_ink = [sum(r) for r in dark]
    body = [y for y in range(H) if rows_ink[y] > 0]
    if len(body) < H * 0.3:
        return None
    y0b, y1b = body[0], body[-1]
    bh = y1b - y0b + 1
    col = [sum(dark[y][x] for y in range(y0b, y1b + 1)) for x in range(W)]
    rule = [c > 0.45 * bh for c in col]                       # vertical rules (column separators, borders)
    g = max(3, int(W * 0.016))
    lo, hi = int(W * 0.33), int(W * 0.67)
    sh = max(8, int(H * 0.05))
    votes, inked = [], 0
    for ys in range(y0b, y1b + 1, sh):
        rows = range(ys, min(ys + sh, y1b + 1))
        colink = [0 if rule[x] else sum(dark[y][x] for y in rows) for x in range(W)]
        if sum(colink) < W * 0.02:
            continue
        inked += 1
        x = min(range(lo, hi - g), key=lambda x: sum(colink[x:x + g]))
        if sum(colink[x:x + g]) == 0 and sum(colink[:x]) > 0.2 * sum(colink) and sum(colink[x + g:]) > 0.2 * sum(colink):
            votes.append(x)
    if not votes:
        return None
    buckets = {}
    for x in votes:
        buckets[x // max(1, int(W * 0.015))] = buckets.get(x // max(1, int(W * 0.015)), 0) + 1
    kb = max(buckets, key=lambda k: buckets[k] + buckets.get(k - 1, 0) + buckets.get(k + 1, 0))
    agree = [x for x in votes if abs(x // max(1, int(W * 0.015)) - kb) <= 1]
    best = sorted(agree)[len(agree) // 2]
    ok = len(agree) >= max(5, 0.5 * inked)
    if debug:
        print(f"  W{W} H{H} gutter x={best} ({best/W:.2f}) agree={len(agree)}/{inked} ok={ok}")
    if not ok:
        return None
    gx0, gx1 = best, best + g
    # rows crossing the gutter (ignoring rule pixels)
    cross = [any(dark[y][x] and not rule[x] for x in range(gx0, gx1)) for y in range(H)]
    # group rows into runs, closing small gaps
    kinds = []
    y = 0
    while y < H:
        if rows_ink[y] == 0:
            y += 1
            continue
        k = "full" if cross[y] else "two"
        y2 = y
        while y2 + 1 < H and (rows_ink[y2 + 1] == 0 or ("full" if cross[y2 + 1] else "two") == k):
            y2 += 1
        kinds.append([k, y, y2])
        y = y2 + 1
    # absorb tiny runs (< 1.2% of H) into the previous run
    merged = []
    for k, a, b in kinds:
        if merged and (b - a + 1 < H * 0.012 or merged[-1][0] == k):
            merged[-1][2] = b
            continue
        merged.append([k, a, b])
    if not any(k == "two" and (b - a) > H * 0.08 for k, a, b in merged):
        return None
    sx = page.rect.width / W
    sy = page.rect.height / H
    out = []
    for k, a, b in merged:
        ya, yb = max(0, a - 1) * sy, min(H, b + 2) * sy
        if k == "full":
            out.append(("full", pymupdf.Rect(0, ya, page.rect.width, yb)))
        else:
            mid = (gx0 + gx1) / 2 * sx
            out.append(("left", pymupdf.Rect(0, ya, mid, yb)))
            out.append(("right", pymupdf.Rect(mid, ya, page.rect.width, yb)))
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
    from pathlib import Path
    from nizam.storage.db import connect
    out = pymupdf.open()
    with connect() as conn, conn.cursor() as cur:
        for a in sys.argv[2:]:
            d, p = map(int, a.split(":"))
            cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (d,))
            src = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            page = src[p - 1]
            print(f"doc {d} p{p}")
            bs = bands(page, debug=True)
            for k, r in bs or []:
                print(f"   {k:5s} y {r.y0:6.1f}-{r.y1:6.1f} x {r.x0:6.1f}-{r.x1:6.1f}")
            np_ = out.new_page(width=page.rect.width, height=page.rect.height)
            np_.show_pdf_page(np_.rect, src, p - 1)
            for k, r in bs or []:
                np_.draw_rect(r, color=(1, 0, 0) if k == "full" else (0, 0, 1) if k == "left" else (0, .6, 0), width=1.5)
    out.save(sys.argv[1])
