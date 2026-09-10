# -*- coding: utf-8 -*-
"""Shell chrome for the consolidated volume: tokens, front matter, dividers.

Palette and faces are inherited from Document 01, the root of the specification
set: paper/indigo/rubric on Newsreader + Public Sans + IBM Plex Mono. Parts 12
and 13 keep their own Stamp Paper system because those documents *are* the
design system and must render in their own language.
"""

FONTS = ('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;'
         '0,6..72,500;0,6..72,600;1,6..72,400&family=Public+Sans:ital,wght@0,400;0,500;'
         '0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&family=Spectral:ital,'
         'wght@0,300;0,400;0,500;0,600;1,400&family=Karla:ital,wght@0,400;0,500;0,600;'
         '0,700;1,400&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap')

SHELL_CSS = """
:root{
 --paper:#F3F4F7;--surface:#FFFFFF;--surface-2:#EDEFF3;--surface-3:#E3E7EE;
 --ink:#14171E;--ink-2:#4C5566;--ink-3:#7E879A;
 --rule:#DCDFE7;--rule-2:#C6CBD6;
 --indigo:#26397A;--indigo-soft:#E4E8F5;
 --rubric:#9E3B2F;--rubric-soft:#F6E7E4;
 --ok:#2C6349;--ok-soft:#E0EDE7;--warn:#7E6114;--warn-soft:#F3EBD8;
 --shadow:0 1px 2px rgba(20,23,30,.05),0 8px 24px -12px rgba(20,23,30,.14);
 --f-display:"Newsreader",Georgia,serif;
 --f-body:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
 --f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
 --f-urdu:"Noto Nastaliq Urdu",serif;
 --measure:70ch;--bar:3.25rem;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --paper:#0D0F14;--surface:#14171E;--surface-2:#1B1F28;--surface-3:#232935;
 --ink:#E6E9EF;--ink-2:#A0A9BA;--ink-3:#6D7688;
 --rule:#252A34;--rule-2:#333A47;
 --indigo:#93A8E8;--indigo-soft:#1B2136;
 --rubric:#D8867A;--rubric-soft:#2B1D1B;
 --ok:#6FBF95;--ok-soft:#152520;--warn:#D3AB5C;--warn-soft:#241E10;
 --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
}}
:root[data-theme="dark"]{
 --paper:#0D0F14;--surface:#14171E;--surface-2:#1B1F28;--surface-3:#232935;
 --ink:#E6E9EF;--ink-2:#A0A9BA;--ink-3:#6D7688;
 --rule:#252A34;--rule-2:#333A47;
 --indigo:#93A8E8;--indigo-soft:#1B2136;
 --rubric:#D8867A;--rubric-soft:#2B1D1B;
 --ok:#6FBF95;--ok-soft:#152520;--warn:#D3AB5C;--warn-soft:#241E10;
 --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -14px rgba(0,0,0,.7);
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:calc(var(--bar) + 1rem)}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}
 *,*::before,*::after{animation-duration:.01ms !important;transition-duration:.01ms !important}}
body{margin:0;background:var(--paper);color:var(--ink);
 font-family:var(--f-body);font-size:16.5px;line-height:1.62;-webkit-font-smoothing:antialiased}
:focus-visible{outline:2px solid var(--rubric);outline-offset:3px;border-radius:2px}

/* ---- spine: sticky part navigator -------------------------------------- */
.spine{position:sticky;top:0;z-index:60;height:var(--bar);display:flex;align-items:center;
 gap:1rem;padding:0 1.1rem;background:var(--paper);
 border-bottom:1px solid var(--rule)}
@supports (backdrop-filter:blur(1px)){
 .spine{background:color-mix(in srgb,var(--paper) 86%,transparent);
  backdrop-filter:saturate(1.5) blur(12px);-webkit-backdrop-filter:saturate(1.5) blur(12px)}}
.spine-id{font-family:var(--f-mono);font-size:.66rem;letter-spacing:.15em;text-transform:uppercase;
 color:var(--ink-2);white-space:nowrap;font-weight:600;text-decoration:none}
.spine-id b{color:var(--rubric);font-weight:600}
.spine-scroll{flex:1;min-width:0;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.spine-scroll::-webkit-scrollbar{display:none}
.spine-list{display:flex;gap:.3rem;list-style:none;margin:0;padding:0}
.spine-list a{display:block;font-family:var(--f-mono);font-size:.68rem;font-weight:500;
 letter-spacing:.04em;color:var(--ink-3);text-decoration:none;padding:.28rem .5rem;
 border-radius:4px;white-space:nowrap;border:1px solid transparent;transition:color .15s,background .15s}
.spine-list a:hover{color:var(--ink);background:var(--surface-2)}
.spine-list a[aria-current="true"]{color:var(--rubric);background:var(--rubric-soft);
 border-color:var(--rubric)}

/* ---- front matter ------------------------------------------------------ */
.front{max-width:76rem;margin:0 auto;padding:0 1.5rem}
.vol{border-bottom:2px solid var(--ink);padding:4.5rem 0 1.4rem;margin-bottom:2.6rem}
.vol .kicker{font-family:var(--f-mono);font-size:.68rem;letter-spacing:.16em;text-transform:uppercase;
 color:var(--rubric);margin:0 0 1.1rem}
.vol h1{font-family:var(--f-display);font-weight:500;font-size:clamp(2.6rem,7vw,4.6rem);
 line-height:1.02;letter-spacing:-.022em;margin:0 0 .3rem;text-wrap:balance}
/* RTL direction for the script, isolated per Part 08's bidi rule, but kept on
   the left so it sits under the title rather than at the far margin. */
.vol h1 .ur{font-family:var(--f-urdu);font-size:.46em;font-weight:400;color:var(--ink-2);
 display:block;margin-top:.1rem;line-height:1.75;direction:rtl;unicode-bidi:isolate;
 text-align:left}
.vol .dek{font-family:var(--f-display);font-size:clamp(1.06rem,2.2vw,1.34rem);color:var(--ink-2);
 max-width:60ch;margin:1.3rem 0 1.9rem;font-style:italic}
.vol .meta{display:flex;flex-wrap:wrap;gap:.5rem 2.25rem;font-family:var(--f-mono);font-size:.7rem;
 letter-spacing:.05em;color:var(--ink-3);border-top:1px solid var(--rule);padding-top:.95rem}
.vol .meta b{color:var(--ink-2);font-weight:500}

.fm{padding-top:3.2rem;border-top:1px solid var(--rule);margin-top:3.2rem}
.fm.lead{border-top:none;margin-top:0;padding-top:0}
.fm > h2{font-family:var(--f-display);font-weight:500;font-size:clamp(1.5rem,3vw,2rem);
 letter-spacing:-.017em;margin:0 0 .5rem;text-wrap:balance}
.fm > .lede{font-size:1.06rem;color:var(--ink-2);max-width:64ch;margin:0 0 1.8rem}
.fm h3{font-family:var(--f-mono);font-weight:600;font-size:.7rem;letter-spacing:.14em;
 text-transform:uppercase;color:var(--ink-3);margin:2.6rem 0 .9rem}
.fm p{max-width:var(--measure)}

/* invariants */
.inv{display:grid;grid-template-columns:repeat(auto-fit,minmax(19rem,1fr));gap:.9rem;
 margin:0 0 1.6rem;padding:0}
.inv li{list-style:none;background:var(--surface);border:1px solid var(--rule);
 border-inline-start:3px solid var(--rubric);border-radius:0 5px 5px 0;padding:1rem 1.15rem;
 box-shadow:var(--shadow);display:flex;flex-direction:column;gap:.4rem}
.inv .tag{font-family:var(--f-mono);font-size:.63rem;letter-spacing:.13em;font-weight:600;
 color:var(--rubric)}
.inv .rule{font-weight:700;font-size:.95rem;line-height:1.35}
.inv p{margin:0;font-size:.86rem;color:var(--ink-2);line-height:1.55}
.inv code{font-family:var(--f-mono);font-size:.86em;background:var(--surface-2);
 border:1px solid var(--rule);padding:.06em .34em;border-radius:3px}

.layer-rule{border-inline-start:3px solid var(--indigo);background:var(--surface);
 padding:1rem 1.15rem;border-radius:0 4px 4px 0;box-shadow:var(--shadow);max-width:var(--measure)}
.layer-rule p{margin:0;font-size:.93rem}

/* measured facts */
/* fixed 4 columns so the eight measured facts fill exactly two rows */
.facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;
 background:var(--rule);border:1px solid var(--rule);border-radius:5px;overflow:hidden;margin:0 0 1.4rem}
@media(max-width:900px){.facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:460px){.facts{grid-template-columns:1fr}}
.facts div{background:var(--surface);padding:.95rem 1.05rem;display:flex;flex-direction:column;gap:.25rem}
.facts .n{font-family:var(--f-mono);font-size:1.16rem;font-weight:600;color:var(--ink);
 font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.facts .l{font-size:.74rem;color:var(--ink-3);line-height:1.4}

/* contents register */
.band{margin:2.4rem 0 0}
.band .bh{display:flex;align-items:baseline;gap:.8rem;padding-bottom:.6rem;
 border-bottom:1px solid var(--rule-2);margin-bottom:.55rem;flex-wrap:wrap}
.band .bh .bt{font-family:var(--f-mono);font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;
 font-weight:600;color:var(--rubric)}
.band .bh .bd{font-size:.82rem;color:var(--ink-3)}
.toc{list-style:none;margin:0;padding:0}
.toc > li{border-bottom:1px solid var(--rule)}
.toc > li:last-child{border-bottom:none}
.toc-row{display:grid;grid-template-columns:4.6rem minmax(0,1fr) auto;gap:0 1.1rem;align-items:baseline;
 padding:.72rem 0;text-decoration:none;color:inherit}
.toc-row:hover .tt{color:var(--indigo)}
.toc-row .tn{font-family:var(--f-mono);font-size:.82rem;font-weight:600;color:var(--rubric);
 font-variant-numeric:tabular-nums}
.toc-row .tt{font-family:var(--f-display);font-size:1.07rem;font-weight:500;letter-spacing:-.01em;
 line-height:1.3}
.toc-row .ts{display:block;font-family:var(--f-body);font-size:.8rem;color:var(--ink-3);
 margin-top:.16rem;line-height:1.45;max-width:62ch}
.toc-row .tc{font-family:var(--f-mono);font-size:.66rem;color:var(--ink-3);white-space:nowrap;
 font-variant-numeric:tabular-nums}
@media(max-width:640px){.toc-row{grid-template-columns:3.4rem minmax(0,1fr)}.toc-row .tc{display:none}}
.toc-sub{margin:0 0 .8rem;padding:0 0 0 5.7rem;list-style:none;display:flex;flex-wrap:wrap;gap:.28rem .42rem}
.toc-sub a{font-family:var(--f-mono);font-size:.65rem;color:var(--ink-3);text-decoration:none;
 border:1px solid var(--rule);border-radius:3px;padding:.16rem .42rem;background:var(--surface)}
.toc-sub a:hover{color:var(--indigo);border-color:var(--rule-2)}
@media(max-width:640px){.toc-sub{padding-left:3.4rem}}

/* ---- part divider ------------------------------------------------------ */
.part{scroll-margin-top:calc(var(--bar) + 1rem)}
.pdiv{max-width:76rem;margin:0 auto;padding:4.6rem 1.5rem 0}
.pdiv-in{border-top:2px solid var(--ink);padding-top:1.5rem;
 display:grid;grid-template-columns:9.5rem minmax(0,1fr);gap:0 2.5rem}
.pdiv .num{font-family:var(--f-mono);font-size:clamp(2rem,4.4vw,2.9rem);font-weight:600;
 color:var(--rubric);line-height:.95;letter-spacing:-.03em;display:block}
.pdiv .role{font-family:var(--f-mono);font-size:.63rem;letter-spacing:.13em;text-transform:uppercase;
 color:var(--ink-3);display:block;margin-top:.7rem;line-height:1.6}
.pdiv h2{font-family:var(--f-display);font-weight:500;font-size:clamp(1.9rem,4vw,2.7rem);
 line-height:1.08;letter-spacing:-.02em;margin:0 0 .55rem;text-wrap:balance}
.pdiv .dek{font-family:var(--f-display);font-style:italic;font-size:clamp(1rem,2vw,1.18rem);
 color:var(--ink-2);max-width:60ch;margin:0 0 1.2rem}
.pdiv .meta{display:flex;flex-wrap:wrap;gap:.4rem 1.9rem;font-family:var(--f-mono);font-size:.68rem;
 letter-spacing:.04em;color:var(--ink-3);border-top:1px solid var(--rule);padding-top:.8rem;
 margin:0 0 .5rem}
.pdiv .meta b{color:var(--ink-2);font-weight:500}
.pdiv .back{font-family:var(--f-mono);font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;
 color:var(--ink-3);text-decoration:none;display:inline-block;margin-top:.4rem}
.pdiv .back:hover{color:var(--rubric)}
.pdiv .supersede{margin-top:1rem;border-inline-start:3px solid var(--warn);background:var(--surface);
 padding:.85rem 1.05rem;border-radius:0 4px 4px 0;max-width:var(--measure);font-size:.86rem;
 color:var(--ink-2)}
@media(max-width:880px){.pdiv-in{grid-template-columns:1fr;gap:.9rem}
 .pdiv .role{margin-top:.35rem}}

/* each part keeps its own document styles inside .pbody; only the pad is ours */
.pbody > .wrap{padding-top:.5rem}
.colophon{max-width:76rem;margin:4.5rem auto 0;padding:3.4rem 1.5rem 6rem;
 border-top:2px solid var(--ink)}
.colophon h2{font-family:var(--f-display);font-weight:500;font-size:1.5rem;margin:0 0 .8rem}
.colophon p{font-size:.87rem;color:var(--ink-3);max-width:66ch;margin:0 0 .85rem}
.colophon b{color:var(--ink-2);font-weight:600}
.colophon code{font-family:var(--f-mono);font-size:.86em;background:var(--surface-2);
 border:1px solid var(--rule);padding:.06em .34em;border-radius:3px}
"""

SPINE_JS = """
(function(){
  var parts = [].slice.call(document.querySelectorAll('.part[id]'));
  var links = {};
  [].forEach.call(document.querySelectorAll('.spine-list a'), function(a){
    links[a.getAttribute('href').slice(1)] = a;
  });
  if (!parts.length || !('IntersectionObserver' in window)) return;
  var current = null;
  function mark(id){
    if (id === current) return;
    if (current && links[current]) links[current].removeAttribute('aria-current');
    current = id;
    var a = links[id];
    if (!a) return;
    a.setAttribute('aria-current', 'true');
    var box = a.closest('.spine-scroll');
    if (box) {
      var l = a.offsetLeft - box.clientWidth / 2 + a.offsetWidth / 2;
      box.scrollTo({left: l, behavior: 'smooth'});
    }
  }
  var visible = new Set();
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (e.isIntersecting) visible.add(e.target.id); else visible.delete(e.target.id);
    });
    for (var i = 0; i < parts.length; i++) {
      if (visible.has(parts[i].id)) { mark(parts[i].id); return; }
    }
  }, {rootMargin: '-20% 0px -70% 0px'});
  parts.forEach(function(p){ io.observe(p); });
})();
"""
