"""List every item the official portals publish now (read-only; stdlib only). Lead, 20 Oct 2026.

    python3 tools/recrawl/list_portals.py SOURCE OUT.jsonl

SOURCE: federal | kp | sindh | balochistan. One JSON object per listed item:
{source_id, listing, kind, year, title, detail_url, pdf_url, number, date, extra}. Nothing is downloaded here;
tools/recrawl/diff_listing.py compares the listing with the catalogue, and land_missing.py fetches what is missing.

Listing routes (probed 20 Oct 2026):
  federal      pakistancode.gov.pk/english/sHyuRiF.php -- the numbered list of every federal law (1,044)
  kp           kpcode.kp.gov.pk/homepage/list_all_law/0/15/{offset} (575 laws); /homepage/rules -> 69
               search_by_year_rule/{id} pages -> RuleDetails/{n}
  sindh        Chrono.aspx?pg={ACT,ORDINANCE,RULE} -> SindhGazetteDetail.aspx?X=..&Year=.. (Sindh Code, codified,
               PDF links in the rows); Gazette.aspx?pg={ACT,ORDINANCE} -> GazetteDetail.aspx?X=..&Year=..
               (Gazette publications, GazetteDownload.aspx?PubID=..)
  balochistan  balochistancode.gob.pk Document.aspx?wise=chronological&year={y}&opento=2&dst= (laws; the type
               filter does not work, so rules are not listable here); pabalochistan.gov.pk/acts (the Assembly's
               Acts with their PDFs)
"""
from __future__ import annotations

import concurrent.futures as cf
import html
import json
import re
import sys
from urllib.parse import urljoin

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon/tools/recrawl")
from probe import get  # noqa: E402

HREF_A = re.compile(r"""<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.S | re.I)


def text(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def item(**kw) -> dict:
    base = {"source_id": None, "listing": None, "kind": None, "year": None, "title": None, "detail_url": None,
            "pdf_url": None, "number": None, "date": None, "extra": None}
    base.update(kw)
    return base


def pmap(fn, args, workers=4):
    with cf.ThreadPoolExecutor(workers) as ex:
        for out in ex.map(fn, args):
            yield from out


# --------------------------------------------------------------------------- federal
def federal():
    base = "https://pakistancode.gov.pk/english/"
    st, b = get(base + "sHyuRiF.php", timeout=180)
    blocks = re.findall(r"(\d+)\s*--\s*<a href=\"([^\"]+)\">(.*?)</a>\s*</div>\s*<div class='accordion-section-content'"
                        r"[^>]*>(.*?)</div>", b, re.S)
    for n, href, title, content in blocks:
        c = text(content)
        cat = c.split("|")[0].strip()
        num = re.search(r"\b([IVXLCDM]+|\d+)\s+of\s+(\d{4})", c)
        date = re.search(r"(?:Promulgation|Enactment|Assent|Passing)?\s*Date:\s*([A-Za-z]+ \d{1,2},? \d{4})", c)
        yr = re.search(r"\b(1[789]\d\d|20\d\d)\b", text(title))
        yield item(source_id="pk-federal", listing="pakistancode:list", kind=cat, title=text(title),
                   year=int(yr.group(1)) if yr else (int(num.group(2)) if num else None),
                   detail_url=urljoin(base, href), number=num.group(0) if num else None,
                   date=date.group(1) if date else None, extra={"serial": int(n)})


# ------------------------------------------------------------------ federal: Ministry of Law archive (DRS)
def federal_drs():
    """drs.molaw.gov.pk -- the Ministry of Law and Justice's Document Retrieval System: Acts, Ordinances, Rules,
    President's Orders, Regulations (all groups). Listing cards give title, type, year and publication date; the
    PDF is the document page's data-pdf-url (read at landing)."""
    base = "https://drs.molaw.gov.pk"
    routes = [("Act", "subCategory=Act"), ("Ordinance", "subCategory=Ordinance"), ("Rules", "subCategory=Rules"),
              ("President Order", "subCategory=President%20Order"), ("Constitution", "subCategory=Constitution"),
              ("Regulation", "RegulationGroup=all")]
    for kind, q in routes:
        page = 1
        while True:
            st, b = get(f"{base}/documents?{q}&pageNumber={page}&pageSize=500", timeout=240)
            cards = re.split(r"<a href='/documents/document-versions\?docId=", b)[1:]
            if not cards:
                break
            for c in cards:
                m = re.match(r"(\d+)&(?:amp;)?versionId=(\d+)", c)
                body = [x.strip() for x in html.unescape(re.sub(r"<[^>]+>", "|", re.sub(r"<svg.*?</svg>", "", c, flags=re.S))).split("|")
                        if x.strip() and "class=" not in x]
                title = next((x for x in body if len(x) > 6 and not x.isdigit()), None)
                yr = next((x.split(":", 1)[1].strip() for x in body if x.startswith("Year:")), "")
                pub = next((x.split(":", 1)[1].strip() for x in body if x.startswith("Published:")), None)
                yield item(source_id="pk-federal", listing="drs:" + kind, kind=kind, title=title,
                           year=int(yr) if yr.isdigit() else None, date=pub,
                           detail_url=f"{base}/documents/document-versions?docId={m.group(1)}&versionId={m.group(2)}" if m else None,
                           extra={"docId": m.group(1) if m else None})
            if len(cards) < 500:
                break
            page += 1


# ----------------------------------------------------- Balochistan: government sites (rules the Code cannot list)
def balochistan_gov():
    """balochistan.gov.pk and sngad.balochistan.gov.pk (WordPress): the media library's PDFs whose titles name a legal
    instrument -- Rules, Regulations, an Act, an Ordinance, Bye-laws or an Order (budgets, forms, policies and
    vacancy notices are not listed)."""
    legal = re.compile(r"\b(rules?|regulations?|act|ordinance|bye[- ]?laws?|order)\b", re.I)
    junk = re.compile(r"\b(budget|psdp|proforma|form\b|advertis|vacanc|merit|result|tender|minutes|agenda|"
                      r"seniority|list|schedule of|calendar|notice)\b", re.I)
    for host in ("balochistan.gov.pk", "sngad.balochistan.gov.pk"):
        page = 1
        while True:
            st, b = get(f"https://{host}/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page={page}", timeout=180)
            try:
                rows = json.loads(b)
            except ValueError:
                break
            if not isinstance(rows, list) or not rows:
                break
            for r in rows:
                t = text((r.get("title") or {}).get("rendered", "")).replace("-", " ")
                if not legal.search(t) or junk.search(t):
                    continue
                yr = re.findall(r"\b(1[89]\d\d|20\d\d)\b", t)
                yield item(source_id="pk-balochistan", listing="balochistangov:media", title=t,
                           kind=legal.search(t).group(1).lower(), year=int(yr[-1]) if yr else None,
                           pdf_url=r.get("source_url"), date=(r.get("date") or "")[:10], extra={"host": host, "media_id": r.get("id")})
            page += 1


# --------------------------------------------------------------------------- Punjab
def punjab():
    """punjabcode.punjab.gov.pk: /en/get_laws (#chronological -> /en/articles_by_year/YYYY) and /en/get_rules
    (service_rules_by_department/N, general_rules_by_department/N); entries are <div class="artlist"><a ..>."""
    base = "https://punjabcode.punjab.gov.pk"
    art = re.compile(r"""<div class="artlist">\s*<a href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.S)

    def page(arg):
        kind, url, year, dept = arg
        st, b = get(url if url.startswith("http") else urljoin(base, url))
        return [item(source_id="pk-punjab", listing="punjabcode:" + kind, kind=kind, title=text(t), year=year,
                     detail_url=h if h.startswith("http") else urljoin(base, h), extra={"department": dept} if dept else None)
                for h, t in art.findall(b)]
    # laws: the chronological tab is gone (21 Oct 2026); the alphabetical list pages 100 at a time to the end
    jobs = []
    offset = 0
    while True:
        rows = page(("law", f"{base}/en/alphabetical/all/100/{offset}", None, None))
        if not rows:
            break
        for r in rows:
            yr = re.findall(r"\b(1[789]\d\d|20\d\d)\b", r["title"] or "")
            r["year"] = int(yr[-1]) if yr else None
            yield r
        offset += 100
    st, b = get(base + "/en/get_rules")
    for kind, pat in (("service rules", r"/en/service_rules_by_department/\d+"), ("general rules", r"/en/general_rules_by_department/\d+")):
        for h, t in HREF_A.findall(b):
            if re.search(pat, h):
                jobs.append((kind, h, None, re.sub(r"\s*\(\d+\)\s*$", "", text(t))))
    yield from pmap(page, jobs)


# --------------------------------------------------------------------------- KP
def kp():
    base = "https://kpcode.kp.gov.pk/homepage/"

    def law_page(offset):
        st, b = get(f"{base}list_all_law/0/15/{offset}")
        out = []
        for href, t in re.findall(r"""<div class="artlist">\s*<a href=["']([^"']+lawDetails/\d+)["'][^>]*>(.*?)</a>""", b, re.S):
            out.append(item(source_id="pk-kp", listing="kpcode:list_all_law", kind="law", title=text(t),
                            detail_url=href))
        return out
    yield from pmap(law_page, range(0, 575 + 15, 15))
    st, b = get(base + "rules")
    years = sorted(set((h, text(t)) for h, t in HREF_A.findall(b) if "search_by_year_rule" in h))

    def rule_year(arg):
        href, yr = arg
        st, b = get(href if href.startswith("http") else urljoin(base, href))
        out = []
        for h, t, dets in re.findall(r"""<div class="artlist"><a href=["']([^"']+RuleDetails/\d+)["'][^>]*>(.*?)</a>\s*</div>\s*"""
                                     r"""<div class="artdets">(.*?)</div>""", b, re.S):
            d = text(dets)
            date = re.search(r"Promulgation Date:\s*([\d-]+)", d)
            out.append(item(source_id="pk-kp", listing="kpcode:rules", kind="rules", title=text(t), detail_url=h,
                            year=int(yr) if yr.isdigit() else None, date=date.group(1) if date else None,
                            extra={"department": d.split("|")[0].strip()}))
        return out
    yield from pmap(rule_year, years)


# --------------------------------------------------------------------------- Sindh
def sindh():
    base = "https://sindhlaws.gov.pk/"

    def codified(arg):
        x, yhref = arg
        st, b = get(urljoin(base, yhref))
        out = []
        m = re.search(r'<div[^>]+id="' + x + r'"(.*?)</table>', b, re.S) or re.search(
            r'ContentPlaceHolder1_DV' + x + r'(.*?)</table>', b, re.S)
        if not m:
            return out
        yr = re.search(r"Year=(\d{4})", yhref)
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 3:
                continue
            a = re.search(r"""href=["']([^"']+)["']""", cells[2])
            href = a.group(1).strip() if a else None
            out.append(item(source_id="pk-sindh", listing="sindhlaws:code", kind=x, title=text(cells[1]),
                            year=int(yr.group(1)) if yr else None,
                            pdf_url=urljoin(base, href) if href and href.lower().endswith(".pdf") else None,
                            date=text(cells[5]) if len(cells) > 5 else None))
        return out

    def gazette(arg):
        x, yhref = arg
        st, b = get(urljoin(base, yhref))
        yr = re.search(r"Year=(\d{4})", yhref)
        out = []
        for num, title, pub, date in re.findall(
                r"<tr><td[^>]*>([^<]*)</td><td[^>]*>(.*?)</td><td[^>]*><a href='GazetteDownload\.aspx\?PubID=([^']+)'"
                r"[^>]*>.*?</a></td><td[^>]*>([^<]*)</td></tr>", b, re.S):
            out.append(item(source_id="pk-sindh", listing="sindhlaws:gazette", kind=x, title=text(title),
                            year=int(yr.group(1)) if yr else None, number=text(num), date=text(date),
                            pdf_url=urljoin(base, f"setup/Publications/{pub}.pdf"),
                            detail_url=urljoin(base, f"GazetteDownload.aspx?PubID={pub}"), extra={"pub_id": pub}))
        return out
    jobs = []
    for x in ("ACT", "ORDINANCE", "RULE"):
        st, b = get(f"{base}Chrono.aspx?pg={x}")
        jobs += [(x, h) for h in sorted(set(h for h, _t in HREF_A.findall(b) if "SindhGazetteDetail.aspx" in h and f"X={x}" in h))]
    yield from pmap(codified, jobs)
    jobs = []
    for x in ("ACT", "ORDINANCE"):
        st, b = get(f"{base}Gazette.aspx?pg={x}")
        jobs += [(x, h) for h in sorted(set(h for h, _t in HREF_A.findall(b) if "GazetteDetail.aspx" in h and f"X={x}" in h))]
    yield from pmap(gazette, jobs)


# --------------------------------------------------------------------------- Balochistan
def balochistan():
    base = "http://balochistancode.gob.pk/"

    def year(y):
        try:
            st, b = get(f"{base}Document.aspx?wise=chronological&year={y}&opento=2&dst=", timeout=120)
        except Exception:                                        # noqa: BLE001
            return [item(source_id="pk-balochistan", listing="balochistancode:year-ERROR", year=y)]
        m = re.search(r'id="datafield"[^>]*value="([^"]*)"', b) or re.search(r'value="([^"]*)"[^>]*id="datafield"', b)
        out = []
        for href, t in re.findall(r"href='([^']+)'[^>]*>\s*([^<]+)", html.unescape(m.group(1)) if m else ""):
            out.append(item(source_id="pk-balochistan", listing="balochistancode:chronological", kind="law",
                            year=y, title=re.sub(r"\s*,\s*\d{4}\s*$", "", text(t)), detail_url=urljoin(base, href)))
        return out
    yield from pmap(year, range(2026, 1854, -1), workers=3)
    st, b = get("https://pabalochistan.gov.pk/acts", timeout=180)
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", b, re.S):
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        pdf = re.search(r"""href=["']([^"']+\.(?:pdf|docx?))["']""", row, re.I)
        if len(cells) >= 3 and pdf:
            yield item(source_id="pk-balochistan", listing="pabalochistan:acts", kind="act",
                       title=next((c for c in cells if len(c) > 15 and not re.fullmatch(r"[\d/ -]+", c)), cells[1]),
                       pdf_url=urljoin("https://pabalochistan.gov.pk/", pdf.group(1)), extra={"cells": cells})


def main():
    src, out = sys.argv[1], sys.argv[2]
    n = 0
    with open(out, "w", encoding="utf-8") as fh:
        for it in {"federal": federal, "federal_drs": federal_drs, "kp": kp, "sindh": sindh, "punjab": punjab, "balochistan_gov": balochistan_gov,
                   "balochistan": balochistan}[src]():
            fh.write(json.dumps(it, ensure_ascii=False) + "\n"); fh.flush(); n += 1
    print(src, "listed", n)


if __name__ == "__main__":
    main()
