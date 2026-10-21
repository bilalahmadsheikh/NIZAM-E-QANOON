"""Probe official listing pages (read-only, stdlib only): status, size and the link patterns they carry."""
import collections, html, re, ssl, sys, urllib.error, urllib.request
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


def get(u, timeout=90, attempts=4):
    """GET with retries: these portals are slow and drop reads mid-page."""
    import time
    last = None
    for n in range(attempts):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(3 * (n + 1))
    raise last


def main():
  for u in sys.argv[1:]:
    try:
        st, body = get(u)
    except Exception as e:
        print("ERR", u, type(e).__name__, str(e)[:80]); continue
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', body, re.S | re.I)
    pats = collections.Counter(re.sub(r"\d+", "N", re.sub(r"[?#].*", "?", h.rsplit("/", 2)[-2] + "/" + h.rsplit("/", 1)[-1] if h.count("/") >= 1 else h))[:70] for h, _ in links)
    print("==", st, len(body), u)
    for p, n in pats.most_common(10): print("   ", n, p)
    m = re.findall(r"Total Records Found\s*:?\s*(?:<[^>]+>)*\s*(\d+)", body)
    if m: print("    total records:", m[:2])
