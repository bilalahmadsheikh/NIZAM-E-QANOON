# -*- coding: utf-8 -*-
"""Extraction + CSS scoping primitives for the consolidated specification build."""
import re

# ---------------------------------------------------------------- extraction

def read(path):
    return open(path, encoding='utf-8').read()

def style_block(s):
    m = re.search(r'<style>(.*?)</style>', s, re.S)
    return m.group(1) if m else ''

def dgdefs(s):
    m = re.search(r'<svg class="dgdefs".*?</svg>', s, re.S)
    return m.group(0) if m else ''

def _match_div(s, start):
    """start is the index of '<div'; return index just past its matching </div>."""
    i, depth = start, 0
    while i < len(s):
        if s.startswith('<div', i) and (i + 4 >= len(s) or s[i + 4] in ' >\t\n'):
            depth += 1; i += 4
        elif s.startswith('</div>', i):
            depth -= 1; i += 6
            if depth == 0:
                return i
        else:
            i += 1
    raise ValueError('unbalanced <div> from %d' % start)

def wrap_inner(s):
    m = re.search(r'<div class="wrap"[^>]*>', s)
    if not m:
        raise ValueError('no .wrap')
    end = _match_div(s, m.start())
    return s[m.end():end - 6]

def split_header(inner):
    """Return (header_html, rest) splitting off <header class="masthead|hero">."""
    m = re.search(r'<header class="(?:masthead|hero)"[^>]*>.*?</header>', inner, re.S)
    if not m:
        return '', inner
    return m.group(0), inner[:m.start()] + inner[m.end():]

def field(header, cls, tag='p'):
    m = re.search(r'<%s class="%s"[^>]*>(.*?)</%s>' % (tag, cls, tag), header, re.S)
    return m.group(1).strip() if m else ''

def meta_pairs(header):
    m = re.search(r'<div class="meta"[^>]*>(.*?)</div>\s*$', header, re.S)
    if not m:
        m = re.search(r'<div class="meta"[^>]*>(.*?)</div>', header, re.S)
    if not m:
        return []
    out = []
    for sp in re.findall(r'<span>(.*?)</span>', m.group(1), re.S):
        b = re.search(r'<b>(.*?)</b>\s*(.*)', sp, re.S)
        if b:
            out.append((b.group(1).strip(), re.sub(r'\s+', ' ', b.group(2)).strip()))
    return out

# ---------------------------------------------------------------- css scoping

def _blocks(css):
    """Top-level (prelude, body) pairs. Only @media nesting occurs in this corpus."""
    out, i, depth, start, bstart, prelude = [], 0, 0, 0, 0, ''
    while i < len(css):
        c = css[i]
        if c == '{':
            if depth == 0:
                prelude = css[start:i]; bstart = i + 1
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                out.append((prelude.strip(), css[bstart:i])); start = i + 1
        i += 1
    return out

def scope_one(sel, cls):
    s = sel.strip()
    if not s:
        return ''
    if s == '*':
        return '.%s,.%s *' % (cls, cls)
    m = re.match(r'^(:root|html)(?![\w-])(.*)$', s, re.S)
    if m:
        root, rest = m.group(1), m.group(2)
        am = re.match(r'^((?:[:\[][^\s>+~,]*)*)(.*)$', rest, re.S)
        head = root + am.group(1)
        remainder = am.group(2).strip()
        if not remainder:
            return '%s .%s' % (head, cls)
        rm = re.match(r'^body(?![\w-])(.*)$', remainder, re.S)
        if rm:
            return '%s .%s%s' % (head, cls, rm.group(1))
        return '%s .%s %s' % (head, cls, remainder)
    m = re.match(r'^body(?![\w-])(.*)$', s, re.S)
    if m:
        return '.%s%s' % (cls, m.group(1))
    return '.%s %s' % (cls, s)

def scope_css(css, cls):
    """Prefix every rule so the document's styles apply only inside .<cls>."""
    out = []
    for prelude, body in _blocks(css):
        if prelude.startswith('@media'):
            inner = []
            for p2, b2 in _blocks(body):
                if p2.startswith('@'):
                    inner.append('%s{%s}' % (p2, b2)); continue
                sels = ','.join(scope_one(x, cls) for x in p2.split(',') if x.strip())
                inner.append('%s{%s}' % (sels, b2))
            out.append('%s{%s}' % (prelude, ''.join(inner)))
        elif prelude.startswith('@'):
            out.append('%s{%s}' % (prelude, body))
        else:
            sels = ','.join(scope_one(x, cls) for x in prelude.split(',') if x.strip())
            out.append('%s{%s}' % (sels, body))
    return ''.join(out)

# ---------------------------------------------------------------- id namespacing

_REF_ATTRS = ('aria-labelledby', 'aria-describedby', 'headers', 'aria-controls', 'aria-owns')

def namespace_ids(html, pfx):
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    if not ids:
        return html, ids
    def ren(name):
        return '%s-%s' % (pfx, name) if name in ids else name
    html = re.sub(r'\bid="([^"]+)"', lambda m: 'id="%s"' % ren(m.group(1)), html)
    html = re.sub(r'\bhref="#([^"]+)"', lambda m: 'href="#%s"' % ren(m.group(1)), html)
    html = re.sub(r'\burl\(#([^)]+)\)', lambda m: 'url(#%s)' % ren(m.group(1)), html)
    for a in _REF_ATTRS:
        html = re.sub(r'\b%s="([^"]+)"' % a,
                      lambda m, a=a: '%s="%s"' % (a, ' '.join(ren(t) for t in m.group(1).split())),
                      html)
    return html, ids
