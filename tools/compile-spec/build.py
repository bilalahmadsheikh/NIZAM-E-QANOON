# -*- coding: utf-8 -*-
"""Compile the 17 specification documents into one consolidated volume.

Each source document keeps its own stylesheet, scoped to its part, so nothing
is restyled or reflowed. What the compiler adds is the apparatus of a bound
volume: front matter, a contents register, part dividers, and a spine.

Part identifiers are the original document numbers (01, 03a, 03b, 09a ...)
because those numbers are the project's citation scheme -- `docs/03 s2.3` must
keep resolving after the merge.
"""
import os, re, sys, io, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib, shell

DOCS = os.path.abspath(os.path.join(HERE, '..', '..', 'docs'))
OUT = os.path.join(DOCS, '00-complete-specification.html')

# ---------------------------------------------------------------- manifest
# (part id, file, title, role, one-line summary, band)
BANDS = [
    ('Foundation',            'the contract every other part inherits'),
    ('Corpus and store',      'L1 to L2 -- what the system knows and how it is kept'),
    ('The answer path',       'L3 to L6 -- evidence, generation, services, the wire'),
    ('Clients',               'L7 -- the four surfaces'),
    ('Platform',              'where it is built and where it runs'),
    ('Guarantees',            'cross-cutting quality and security authority'),
    ('Design and interaction','the visual and behavioural language of the product'),
    ('Appendix',              'retained for provenance'),
]

PARTS = [
 ('01',  '01-master-architecture.html',            'System Architecture',
  'Spine &middot; UML 2.5 + C4', 'Layers, domain model, interface contracts, 20 UML/C4 views, ADR index.', 0),
 ('02',  '02-corpus-and-ingestion.html',           'Corpus and Ingestion',
  'Layer L1', 'Sources, extraction, segmentation, enrichment, the seven QA gates.', 1),
 ('03',  '03-data-and-storage.html',               'Data and Storage',
  'Layer L2', 'Schema, extensions, indexes, the publish transaction, migrations.', 1),
 ('03a', '03a-capacity-plan.html',                 'Capacity Plan',
  'Annex to 03', 'Measured corpus sizing, free-tier analysis, the hosting ladder.', 1),
 ('03b', '03b-legal-data-model.html',              'Legal Data Model',
  'Annex to 03', '14 legal edge types, 9 facets, schedules as tables, the SQLite projection.', 1),
 ('04',  '04-retrieval.html',                      'Retrieval',
  'Layer L3', 'Query understanding, candidates, fusion, rerank, the abstention gate.', 2),
 ('05',  '05-generation-and-grounding.html',       'Generation and Grounding',
  'Layer L4', 'Provider port, typed answers, the verification cascade, offline answers.', 2),
 ('06',  '06-domain-services.html',                'Domain Services',
  'Layer L5', 'Citator, limitation engine, calculators, document factory, procedures.', 2),
 ('07',  '07-backend-api.html',                    'Backend API',
  'Layer L6', 'HTTP contract, identity, orchestration, audit, sync engines, SLOs.', 2),
 ('08',  '08-client-architecture.html',            'Client Architecture',
  'Layer L7', 'Four surfaces, seven sublayers, the offline pack, bidi, accessibility.', 3),
 ('09a', '09a-local-environment.html',             'Local Environment',
  'Platform', 'Machine requirements, the one-time build job, bootstrap.', 4),
 ('09b', '09b-production-deployment.html',         'Production Deployment',
  'Platform', 'Consumption model, provider pricing, capacity, operations.', 4),
 ('10',  '10-evaluation-and-quality.html',         'Evaluation and Quality',
  'Cross-cutting', 'Golden set, metrics, ablations, CI gates.', 5),
 ('11',  '11-security-and-privacy.html',           'Security and Privacy',
  'Cross-cutting', 'Classification, threat model, anonymous proof, RLS, evidence integrity.', 5),
 ('12',  '12-design-system.html',                  'Design System',
  'Client craft', 'The Stamp Paper palette, Spectral/Karla, spacing, components.', 6),
 ('13',  '13-ux-and-interaction-architecture.html','UX and Interaction Architecture',
  'Client craft', 'Journeys, answer anatomy, uncertainty, voice, the content system.', 6),
 ('A',   'blueprint.html',                         'Origin Blueprint',
  'Superseded origin', 'The twelve departures, reconciled against the four source proposals.', 7),
]

SUPERSEDED = ('This is the origin document, retained for provenance. It predates Parts 01&ndash;13 '
              'and is superseded by them wherever they differ. Cite it for history, never as the contract.')

INVARIANTS = [
 ('INV-1', 'No generated citation.',
  'Section numbers, article numbers, case citations, dates and URLs are rendered from database '
  'records. The model emits identifiers only.'),
 ('INV-2', 'No answer without a passing gate.',
  '<code>retrieve()</code> returns <code>GroundingContext | Abstention</code> &mdash; two-valued. '
  'No third return, no retry at a lower threshold, no fallback to model knowledge.'),
 ('INV-3', 'Every answer is replayable.',
  'Query, filters, retrieved IDs with scores, gate decision, prompt hash, model version and '
  'verifier result are persisted for every response.'),
 ('INV-4', 'Provisions are the citable unit.',
  'No chunk identifier above L2. Re-chunking must never break a stored citation.'),
 ('INV-5', 'Law is answered as at a date.',
  'Every retrieval carries <code>as_of</code>. Read <code>operative_provision</code>, never the '
  'base table.'),
]

FACTS = [
 ('4,595',    'distinct source PDFs archived; 4,716 official observations'),
 ('128.6 M',  'active extracted characters across 63,047 pages'),
 ('512,094',  'active provision nodes across 4,788 legal expressions'),
 ('106 docs', 'carry accepted OCR evidence; clean extraction remains the primary path'),
 ('1,682 MB', 'hot statutory build after multi-expression materialisation and safe compaction'),
 ('~10 GB',   'with case law included'),
 ('14.2 GB',  'RAM for production at 50k MAU'),
 ('~3%',      'share of the bill that is infrastructure, at scale'),
]

# ---------------------------------------------------------------- transforms

def normalize_theme(css, cls):
    """Give every part the full three-state theme contract.

    Documents vary in how completely they implement it. Some guard their dark
    tokens with a bare `:root` inside the dark media query, so an explicit light
    choice loses to a dark OS. Most carry no `[data-theme="dark"]` rule at all,
    so an explicit dark choice on a light OS does nothing. Merged as-is, those
    parts would render the wrong theme mid-volume. Rewrite the guard where it is
    missing and synthesise the stamped rule from the document's own dark tokens.
    """
    if re.search(r':root\[data-theme="dark"\]', css):
        return css, False
    out, dark_body = [], None
    for prelude, body in lib._blocks(css):
        if prelude.startswith('@media') and 'prefers-color-scheme' in prelude and 'dark' in prelude:
            inner = []
            for p2, b2 in lib._blocks(body):
                bare = p2.strip()
                if bare in (':root', ':root:not([data-theme="light"])'):
                    dark_body = b2
                    p2 = ':root:not([data-theme="light"])'
                inner.append('%s{%s}' % (p2, b2))
            out.append('%s{%s}' % (prelude, ''.join(inner)))
        else:
            out.append('%s{%s}' % (prelude, body))
    if dark_body is not None:
        out.append(':root[data-theme="dark"]{%s}' % dark_body)
    return ''.join(out), dark_body is not None


def label_figures(html, part):
    """Disambiguate 17 documents' worth of 'Figure 1' without renumbering them.

    The original number is left verbatim so in-prose references still resolve;
    the part identifier is prepended for global uniqueness.
    """
    tag = 'Doc %s &middot; ' % part
    return re.sub(r'(<span class="fignum">)', lambda m: m.group(1) + tag, html)


def anchor_sections(html, pfx):
    """Add a stable id to each <section> and return (html, [(anchor, num, title)])."""
    starts = [m for m in re.finditer(r'<section\b[^>]*>', html)]
    if not starts:
        return html, []
    entries, pieces, last = [], [], 0
    for i, m in enumerate(starts):
        chunk_end = starts[i + 1].start() if i + 1 < len(starts) else len(html)
        chunk = html[m.end():chunk_end]
        num = re.search(r'<span class="num">(.*?)</span>', chunk, re.S)
        h2 = re.search(r'<h2[^>]*>(.*?)</h2>', chunk, re.S)
        num = re.sub(r'<[^>]+>', '', num.group(1)).strip() if num else '&sect;%d' % (i + 1)
        title = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h2.group(1))).strip() if h2 else ''
        open_tag = m.group(0)
        # Several documents already give their sections meaningful ids
        # (#identity, #threat-model). Keep those as the anchor rather than
        # layering a generated one on top -- the contents must link to the id
        # that actually ends up in the markup.
        existing = re.search(r'\bid="([^"]+)"', open_tag)
        if existing:
            anchor, new_tag = existing.group(1), open_tag
        else:
            anchor = '%s-s%d' % (pfx, i + 1)
            new_tag = open_tag[:-1] + ' id="%s">' % anchor
        entries.append((anchor, num, title))
        pieces.append(html[last:m.start()]); pieces.append(new_tag); last = m.end()
    pieces.append(html[last:])
    return ''.join(pieces), entries


def esc_attr(s):
    return re.sub(r'<[^>]+>', '', s).replace('"', '&quot;')

# ---------------------------------------------------------------- build

def build():
    css_parts, body_parts, toc = [shell.SHELL_CSS], [], []
    stats = []
    for part, fname, title, role, summary, band in PARTS:
        src = lib.read(os.path.join(DOCS, fname))
        cls = 'p' + part
        pfx = 'd' + part

        css, synth = normalize_theme(lib.style_block(src), cls)
        css_parts.append('\n/* ===== Part %s -- %s ===== */\n' % (part, title))
        css_parts.append(lib.scope_css(css, cls))

        inner = lib.wrap_inner(src)
        header, rest = lib.split_header(inner)
        rest = lib.dgdefs(src) + rest
        rest = label_figures(rest, part)
        # namespace the document's own ids first, then inject already-prefixed
        # section anchors -- the other order would prefix them twice.
        rest, ids = lib.namespace_ids(rest, pfx)
        rest, sections = anchor_sections(rest, pfx)

        dek = lib.field(header, 'dek')
        meta = lib.meta_pairs(header)
        meta_html = ''.join('<span><b>%s</b> %s</span>' % (k, v) for k, v in meta)
        nfig = len(re.findall(r'<figure[\s>]', rest))

        divider = (
          '<div class="pdiv"><div class="pdiv-in">'
          '<div><span class="num">%s</span><span class="role">%s</span></div>'
          '<div><h2>%s</h2>%s%s%s'
          '<a class="back" href="#contents">&uarr; Contents</a></div>'
          '</div></div>'
        ) % (
          part, role, title,
          '<p class="dek">%s</p>' % dek if dek else '',
          '<div class="meta">%s</div>' % meta_html if meta_html else '',
          '<div class="supersede"><p>%s</p></div>' % SUPERSEDED if part == 'A' else '',
        )
        # The part scope class sits on an inner element, never on the article,
        # so the divider above it is out of reach of the document's own CSS.
        # Otherwise a document's `.dek` or `.meta` rule restyles the divider --
        # Part 12 renders its dek as cream, which on the shell ground is
        # invisible. Divider = the volume speaking; body = the document speaking.
        body_parts.append(
          '<article class="part" id="part-%s" aria-labelledby="%s-t">'
          '<h2 id="%s-t" hidden>Part %s &mdash; %s</h2>%s'
          '<div class="pbody %s"><div class="wrap">%s</div></div></article>'
          % (part, pfx, pfx, part, title, divider, cls, rest))

        toc.append((part, title, role, summary, band, sections, nfig))
        stats.append((part, len(sections), nfig, len(ids), synth))

    # ---- front matter
    spine = ''.join('<li><a href="#part-%s">%s</a></li>' % (p, p) for p, *_ in PARTS)
    inv = ''.join('<li><span class="tag">%s</span><span class="rule">%s</span><p>%s</p></li>'
                  % (t, r, d) for t, r, d in INVARIANTS)
    facts = ''.join('<div><span class="n">%s</span><span class="l">%s</span></div>'
                    % (n, l) for n, l in FACTS)

    bands_html = []
    for bi, (bname, bdesc) in enumerate(BANDS):
        rows = []
        for part, title, role, summary, band, sections, nfig in toc:
            if band != bi:
                continue
            subs = ''.join('<li><a href="#%s" title="%s">%s</a></li>'
                           % (a, esc_attr(t), n) for a, n, t in sections)
            rows.append(
              '<li><a class="toc-row" href="#part-%s">'
              '<span class="tn">%s</span>'
              '<span class="tt">%s<span class="ts">%s</span></span>'
              '<span class="tc">%d &sect; &middot; %d fig</span></a>'
              '<ul class="toc-sub">%s</ul></li>'
              % (part, part, title, summary, len(sections), nfig, subs))
        bands_html.append(
          '<div class="band"><div class="bh"><span class="bt">%s</span>'
          '<span class="bd">%s</span></div><ul class="toc">%s</ul></div>'
          % (bname, bdesc, ''.join(rows)))

    tot_sec = sum(len(s) for *_, s, _ in toc)
    tot_fig = sum(f for *_, f in toc)
    today = '30 August 2026'

    front = """
<nav class="spine" aria-label="Parts">
  <a class="spine-id" href="#top">Nizam-e-Qanoon <b>/</b> Specification</a>
  <div class="spine-scroll"><ul class="spine-list">%s</ul></div>
  <a class="spine-id" href="#contents">Contents</a>
</nav>
<div class="front" id="top">
  <header class="vol">
    <p class="kicker">Consolidated volume &middot; 17 documents &middot; the complete contract</p>
    <h1>Nizam-e-Qanoon<span class="ur">&#1606;&#1592;&#1575;&#1605;&#1616; &#1602;&#1575;&#1606;&#1608;&#1606;</span></h1>
    <p class="dek">Pakistan&rsquo;s first intelligent legal infrastructure: a bilingual,
      offline-capable platform over the statutory corpus and judicial precedent of the federation
      and four provinces. This volume binds every specification document into one reference.</p>
    <div class="meta">
      <span><b>Volume</b> 1.0</span>
      <span><b>Compiled</b> %s</span>
      <span><b>Parts</b> %d</span>
      <span><b>Sections</b> %d</span>
      <span><b>Figures</b> %d</span>
      <span><b>Project</b> FYP &middot; GIKI FCSE</span>
    </div>
  </header>

  <section class="fm lead">
    <h2>The five invariants</h2>
    <p class="lede">These are rejection criteria, not aspirations. A design that violates one is
      wrong regardless of how well it performs. Every part of this volume inherits them.</p>
    <ul class="inv">%s</ul>
    <div class="layer-rule"><p><b>Layer rule.</b> A layer calls <b>only</b> the layer immediately
      below it, plus the shared inference worker. L1 corpus &rarr; L2 storage &rarr; L3 retrieval
      &rarr; L4 generation &rarr; L5 services &rarr; L6 API &rarr; L7 clients.</p></div>
  </section>

  <section class="fm">
    <h2>The corpus, measured</h2>
    <p class="lede">Measured from <code>data/</code> on 28 August 2026, not estimated. These
      figures set the sizing, the hosting ladder and the scope of OCR; Part 03a shows the method.</p>
    <div class="facts">%s</div>
  </section>

  <section class="fm" id="contents">
    <h2>Contents</h2>
    <p class="lede">Parts keep their original document numbers because those numbers are the
      project&rsquo;s citation scheme &mdash; a reference to <code>docs/03 &sect;2.3</code> still
      resolves here. Section chips jump straight into a part.</p>
    %s
  </section>
</div>
""" % (spine, today, len(PARTS), tot_sec, tot_fig, inv, facts, ''.join(bands_html))

    colophon = """
<footer class="colophon">
  <h2>About this volume</h2>
  <p>This is a compilation, not a rewrite. Each part is its source document verbatim &mdash;
    same words, same tables, same figures, same stylesheet &mdash; scoped so that seventeen
    stylesheets coexist without collision. Parts 12 and 13 render in the <b>Stamp Paper</b> system
    because those documents <i>are</i> the design language; the remaining parts and this shell use
    the specification set&rsquo;s house style from Part 01.</p>
  <p>Three things the compiler changed, and nothing else: element ids are namespaced per part so
    that no two parts collide; figure labels are prefixed with their part
    (<code>Doc 04 &middot; Figure 1</code>) while keeping their original numbers so in-prose
    references still resolve; and seven parts that lacked an explicit
    <code>[data-theme=&quot;dark&quot;]</code> rule had the full three-state theme contract
    synthesised from their own dark tokens, so the whole volume follows the reader&rsquo;s theme
    as one document.</p>
  <p><b>Authority.</b> The individual documents in <code>docs/</code> remain the editable source.
    Regenerate this volume from them rather than editing it &mdash; it is built by
    <code>build.py</code> and any edit made here is lost on the next compile. Where Appendix A
    disagrees with Parts 01&ndash;13, the numbered parts govern.</p>
</footer>
"""

    html = ('<title>Nizam-e-Qanoon Specification</title>\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link rel="stylesheet" href="%s">\n'
            '<style>%s</style>\n%s%s%s\n<script>%s</script>\n'
            % (shell.FONTS, ''.join(css_parts), front, ''.join(body_parts), colophon, shell.SPINE_JS))

    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    return html, stats, tot_sec, tot_fig


if __name__ == '__main__':
    html, stats, tot_sec, tot_fig = build()
    print('wrote %s  (%.2f MB)' % (OUT, len(html.encode('utf-8')) / 1048576.0))
    print('%-5s %8s %8s %6s %s' % ('part', 'sections', 'figures', 'ids', 'theme-synth'))
    for p, ns, nf, ni, syn in stats:
        print('%-5s %8d %8d %6d %s' % (p, ns, nf, ni, 'yes' if syn else '-'))
    print('TOTAL %8d %8d' % (tot_sec, tot_fig))
