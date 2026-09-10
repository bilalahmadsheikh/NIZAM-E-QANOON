# -*- coding: utf-8 -*-
"""Post-compile checks on the consolidated volume."""
import re, sys, os, collections
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lib

PATH = os.path.abspath(os.path.join(HERE, '..', '..', 'docs',
                                    '00-complete-specification.html'))
s = lib.read(PATH)
fails = []

def check(ok, label, detail=''):
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', label, ('  -- ' + detail) if detail and not ok else ''))
    if not ok:
        fails.append(label)

# ---- 1. duplicate ids
ids = re.findall(r'\bid="([^"]+)"', s)
dupes = [k for k, v in collections.Counter(ids).items() if v > 1]
check(not dupes, 'no duplicate element ids (%d ids)' % len(ids), str(dupes[:8]))

# ---- 2. internal anchors resolve
idset = set(ids)
hrefs = set(re.findall(r'href="#([^"]+)"', s))
dangling = sorted(h for h in hrefs if h and h not in idset)
check(not dangling, 'every internal href resolves (%d links)' % len(hrefs), str(dangling[:8]))

# ---- 3. url(#..) svg references resolve
urlrefs = set(re.findall(r'url\(#([^)]+)\)', s))
badurl = sorted(u for u in urlrefs if u not in idset)
check(not badurl, 'every url(#id) svg reference resolves (%d refs)' % len(urlrefs), str(badurl[:8]))

# ---- 4. aria-labelledby targets resolve
aria = set()
for m in re.finditer(r'aria-(?:labelledby|describedby)="([^"]+)"', s):
    aria.update(m.group(1).split())
badaria = sorted(a for a in aria if a not in idset)
check(not badaria, 'every aria-labelledby/describedby target resolves (%d)' % len(aria), str(badaria[:8]))

# ---- 5. tag balance for structural elements
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr',
        'path','circle','rect','line','polyline','polygon','ellipse','use','stop','image','feoffset',
        'fegaussianblur','feblend','fecolormatrix','femerge','femergenode','fedropshadow','animate'}
class Bal(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack, self.errs = [], []
    def handle_starttag(self, tag, attrs):
        if tag in VOID: return
        raw = self.get_starttag_text() or ''
        if raw.endswith('/>'): return
        self.stack.append((tag, self.getpos()))
    def handle_startendtag(self, tag, attrs): pass
    def handle_endtag(self, tag):
        if tag in VOID: return
        if not self.stack:
            self.errs.append('stray </%s> at %s' % (tag, self.getpos())); return
        if self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    unclosed = [t for t, _ in self.stack[i+1:]]
                    self.errs.append('</%s> at %s closes over unclosed %s' % (tag, self.getpos(), unclosed))
                    del self.stack[i:]
                    break
            else:
                self.errs.append('stray </%s> at %s' % (tag, self.getpos()))
b = Bal(); b.feed(s)
leftover = [(t, p) for t, p in b.stack]
check(not b.errs and not leftover, 'html tags balance',
      'errs=%s leftover=%s' % (b.errs[:4], leftover[:6]))

# ---- 6. every section sits inside a part article (no orphan sections)
arts = len(re.findall(r'<article class="part" id="part-', s))
check(arts == 17, 'all 17 parts present as articles', 'found %d' % arts)
bodies = len(re.findall(r'<div class="pbody p', s))
check(bodies == 17, 'each part body carries its scope class', 'found %d' % bodies)
# the divider must sit outside the scoped body, or document CSS restyles it
outside = len(re.findall(r'<div class="pdiv"><div class="pdiv-in">', s))
check(outside == 17, 'dividers are outside the scoped part bodies', 'found %d' % outside)
for m in re.finditer(r'<div class="pdiv">.*?</div></div></div>', s, re.S):
    pass
check(not re.search(r'<div class="pbody [^"]*">\s*<div class="pdiv"', s),
      'no divider nested inside a scoped body')
secs = len(re.findall(r'<section\b', s))
manifest = lib.read(os.path.join(HERE, 'build.py'))
source_files = re.findall(r"\('[^']+',\s+'([^']+\.html)'", manifest)
docs_dir = os.path.dirname(PATH)
expected_doc_secs = sum(len(re.findall(r'<section\b', lib.read(os.path.join(docs_dir, f))))
                        for f in source_files)
check(secs == expected_doc_secs + 3,
      'section count = %d doc sections + 3 front-matter' % expected_doc_secs,
      'found %d' % secs)

# ---- 7. figures labelled with their part
figs = len(re.findall(r'<figure\b', s))
expected_figs = sum(len(re.findall(r'<figure\b', lib.read(os.path.join(docs_dir, f))))
                    for f in source_files)
fignums = re.findall(r'<span class="fignum">(.{0,14})', s)
prefixed = sum(1 for f in fignums if f.startswith('Doc '))
check(figs == expected_figs, 'figure count preserved', 'found %d' % figs)
check(prefixed == len(fignums) and prefixed > 0,
      'every figure label carries its part (%d labels)' % len(fignums),
      '%d of %d' % (prefixed, len(fignums)))

# ---- 8. css: no unscoped source rules leaked
css = re.search(r'<style>(.*?)</style>', s, re.S).group(1)
shell_end = css.find('/* ===== Part 01')
doc_css = css[shell_end:]
leaks = []
for prelude, body in lib._blocks(doc_css):
    sels = [prelude]
    if prelude.startswith('@media'):
        sels = [p for p, _ in lib._blocks(body)]
    for sel in sels:
        for one in sel.split(','):
            one = one.strip()
            if not one or one.startswith('@'): continue
            if not re.search(r'\.p(0[0-9][ab]?|1[0-3]|A)\b', one):
                leaks.append(one)
check(not leaks, 'every document rule is scoped to its part (%d rules)' % len(lib._blocks(doc_css)),
      str(leaks[:6]))

# ---- 9. theme contract: three states for every part
parts = ['01','02','03','03a','03b','04','05','06','07','08','09a','09b','10','11','12','13','A']
missing = []
for p in parts:
    cls = r'\.p%s\b' % re.escape(p)
    has_light = re.search(r':root\s+' + cls + r'\s*\{', doc_css) or re.search(r'(?<![\w.])' + cls + r'\s*\{', doc_css)
    has_media = re.search(r'prefers-color-scheme:\s*dark[^{]*\{[^}]*:root:not\(\[data-theme="light"\]\)\s*' + cls, doc_css)
    has_stamp = re.search(r':root\[data-theme="dark"\]\s+' + cls + r'\s*\{', doc_css)
    if not (has_light and has_stamp):
        missing.append((p, bool(has_light), bool(has_media), bool(has_stamp)))
check(not missing, 'every part defines light + explicit-dark tokens', str(missing[:6]))

# ---- 10. no nested document scaffolding
check('<!doctype' not in s.lower() and '<html' not in s.lower()
      and '<head>' not in s.lower() and '<body' not in s.lower(),
      'no nested doctype/html/head/body (artifact supplies the skeleton)')

# ---- 11. no external SUBRESOURCE loads beyond google fonts.
# Prose citations in href="" are link targets, not requests, and the CSP does
# not touch them; only things the page actually fetches matter here.
sub = set()
sub.update(re.findall(r'\bsrc="(https?://[^"]+)"', s))
sub.update(re.findall(r'<link[^>]+href="(https?://[^"]+)"', s))
sub.update(re.findall(r'url\((https?://[^)]+)\)', s))
sub.update(re.findall(r'@import\s+(?:url\()?["\']?(https?://[^"\')]+)', s))
allowed = {'fonts.googleapis.com', 'fonts.gstatic.com'}
bad = sorted(u for u in sub if re.match(r'https?://([a-z0-9.\-]+)', u).group(1) not in allowed)
check(not bad, 'no external subresource loads beyond Google Fonts (%d checked)' % len(sub), str(bad))

# ---- 12. size
size = os.path.getsize(PATH) / 1048576.0
check(size < 16, 'under the 16 MB artifact cap (%.2f MB)' % size)

print('\n%d check(s) failed' % len(fails) if fails else '\nall checks passed')
sys.exit(1 if fails else 0)
