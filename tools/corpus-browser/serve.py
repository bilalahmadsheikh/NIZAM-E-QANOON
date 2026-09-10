"""A read-only corpus browser: the source PDF and what we extracted, side by side.

pgAdmin is the right tool for inspecting a schema and the wrong one for reading a
statute. It shows one line of a multi-line cell, has no idea that page 106 of a
PDF is the thing you want to compare against, and cannot show you both at once.

This serves three things and nothing else:

    /                     every document, searchable, with quality and lane
    /doc/<id>             the PDF on the left, the extracted text on the right
    /doc/<id>.txt         the whole document as plain text, for diffing or printing
    /schema               every table, column, key, index, view and enum, read live
                          from the catalog -- the shape shown is the shape that exists
    /tables               every table and view with its size and row count
    /table/<name>         the rows themselves: sortable columns, per-column filter,
                          pagination -- the thing pgAdmin makes you write SQL for
    /sql                  a SELECT console that renders its result as a table

READ-ONLY IS ENFORCED, NOT ASSUMED. /sql accepts one statement, it must begin
SELECT or WITH, and it runs inside a READ ONLY transaction with a statement
timeout. Postgres rejects a write inside such a transaction even if the parser
here were fooled, so the guarantee does not rest on the regex.

Everything comes from PostgreSQL on each request. There is no cache and no file
fallback: change a row in the database and the next reload shows it.

It is a TOOL, not product code -- it lives under tools/, imports nothing from
`nizam`, and is read-only by construction: every query is a SELECT and the page
sends nothing back. Doc 09a §2's rule about pgAdmin applies here just as much:
this is for inspection, never a way to change what is stored.

    ./nz browse                    then open http://localhost:5055
    python tools/corpus-browser/serve.py --port 5055
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys

import psycopg
import psycopg.sql          # relied on for identifier quoting; do not import implicitly

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sqlcheck             # noqa: E402  the same lint the MCP server applies

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/e/nizam-data"))


def load_env() -> None:
    env = Path(__file__).resolve().parents[2] / "infra" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def dsn() -> str:
    load_env()
    return (f"host={os.environ.get('POSTGRES_HOST','localhost')} "
            f"port={os.environ.get('POSTGRES_PORT','5433')} "
            # nizam_clean, not nizam: the old database was dropped once the clean
            # rebuild became the corpus, and this default silently pointed the
            # browser at a database that no longer exists.
            f"dbname={os.environ.get('POSTGRES_DB','nizam_clean')} "
            f"user={os.environ.get('POSTGRES_USER','nizam')} "
            f"password={os.environ.get('POSTGRES_PASSWORD','')}")


def q(sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(dsn()) as c, c.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


CSS = """
:root{--parchment:#F7F4EC;--card:#fff;--ink:#141917;--ink-2:#5A625C;--ink-3:#8A9491;
      --pine:#17352E;--brass:#B8873C;--oxide:#9E3B2F;--rule:#E3DFD4}
@media(prefers-color-scheme:dark){:root{--parchment:#121916;--card:#1a2320;--ink:#EDE8DC;
      --ink-2:#AAA99E;--ink-3:#797E76;--pine:#D9E4DF;--rule:#29322E}}
*{box-sizing:border-box}
body{margin:0;background:var(--parchment);color:var(--ink);
     font:15px/1.55 -apple-system,"Segoe UI",system-ui,sans-serif}
a{color:var(--brass);text-decoration:none}a:hover{text-decoration:underline}
header{background:var(--pine);color:var(--parchment);padding:14px 20px;
       display:flex;gap:18px;align-items:center;position:sticky;top:0;z-index:5}
@media(prefers-color-scheme:dark){header{background:#0c110f;color:var(--ink)}}
header b{font-size:16px;letter-spacing:.02em}
header a{color:inherit;opacity:.85}
.wrap{padding:20px;max-width:1500px;margin:auto}
input[type=search],select{font:inherit;padding:7px 10px;border:1px solid var(--rule);
     border-radius:8px;background:var(--card);color:var(--ink)}
table{border-collapse:collapse;width:100%;background:var(--card);
      border:1px solid var(--rule);border-radius:10px;overflow:hidden}
th{text-align:left;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
   color:var(--ink-3);padding:9px 12px;border-bottom:1px solid var(--rule)}
td{padding:8px 12px;border-bottom:1px solid var(--rule);vertical-align:top}
tr:last-child td{border-bottom:0}
tr:hover td{background:rgba(184,135,60,.07)}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{font-size:11px;padding:2px 7px;border-radius:20px;border:1px solid var(--rule);
     color:var(--ink-2);white-space:nowrap}
.e4{border-color:var(--brass);color:var(--brass)}
.low{border-color:var(--oxide);color:var(--oxide)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:14px;height:calc(100vh - 130px)}
@media(max-width:900px){.split{grid-template-columns:1fr;height:auto}}
.pane{background:var(--card);border:1px solid var(--rule);border-radius:10px;
      overflow:auto;position:relative}
.pane h3{position:sticky;top:0;margin:0;padding:9px 14px;background:var(--card);
         border-bottom:1px solid var(--rule);font-size:12px;letter-spacing:.08em;
         text-transform:uppercase;color:var(--ink-3)}
iframe{width:100%;height:100%;border:0;display:block}
.blk{padding:9px 16px;border-bottom:1px dotted var(--rule);white-space:pre-wrap;
     font:15px/1.6 Georgia,"Times New Roman",serif}
.blk:target{background:rgba(184,135,60,.16)}
.meta{font:11px/1 ui-monospace,monospace;color:var(--ink-3);display:block;margin-bottom:4px}
.pg{background:var(--pine);color:var(--parchment);padding:5px 16px;font:11px/1.4 ui-monospace,monospace;
    position:sticky;top:34px;letter-spacing:.08em}
@media(prefers-color-scheme:dark){.pg{background:#0c110f;color:var(--brass)}}
.hint{color:var(--ink-2);font-size:13px;margin:0 0 14px}
.rtl{direction:rtl;text-align:right;font-family:"Noto Nastaliq Urdu",serif;line-height:2.1}

/* --- data browser: a table view worth using instead of pgAdmin ---
   dsplit, not split: .split already means the PDF-beside-text layout on
   /doc/<id>, and redefining it here silently collapsed that page to one pane. */
.dsplit{display:grid;grid-template-columns:250px 1fr;gap:0;height:calc(100vh - 34px)}
@media(max-width:820px){.dsplit{grid-template-columns:1fr;height:auto}}
.side{border-right:1px solid var(--rule);overflow:auto;background:var(--card)}
.side h4{margin:0;padding:9px 14px;font:11px/1 ui-monospace,monospace;letter-spacing:.09em;
   text-transform:uppercase;color:var(--ink-3);background:var(--parchment);
   border-bottom:1px solid var(--rule);position:sticky;top:0}
.side a{display:flex;justify-content:space-between;gap:8px;padding:6px 14px;
   border-bottom:1px solid var(--rule);text-decoration:none;color:var(--ink);font-size:13px}
.side a:hover{background:var(--parchment)}
.side a.on{background:var(--pine);color:var(--parchment)}
.side a i{font-style:normal;color:var(--ink-3);font:11px/1.5 ui-monospace,monospace}
.side a.on i{color:var(--brass)}
.main{overflow:auto;padding:0}
.grid{border-collapse:separate;border-spacing:0;width:100%;font:12.5px/1.45 ui-monospace,SFMono-Regular,monospace}
.grid th{position:sticky;top:0;background:var(--parchment);border-bottom:1px solid var(--rule);
   border-right:1px solid var(--rule);text-align:left;padding:6px 10px;white-space:nowrap;z-index:2}
.grid th a{color:var(--ink);text-decoration:none}
.grid th a:hover{color:var(--brass)}
.grid th small{display:block;font-weight:400;color:var(--ink-3);font-size:10px;letter-spacing:.04em}
.grid td{border-bottom:1px solid var(--rule);border-right:1px solid var(--rule);
   padding:5px 10px;vertical-align:top;max-width:420px;overflow:hidden;text-overflow:ellipsis;
   white-space:nowrap}
.grid td.wrap{white-space:pre-wrap;word-break:break-word}
.grid tr:nth-child(even) td{background:rgba(0,0,0,.02)}
@media(prefers-color-scheme:dark){.grid tr:nth-child(even) td{background:rgba(255,255,255,.03)}}
.grid td.null{color:var(--ink-3);font-style:italic}
.bar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;padding:9px 14px;
   border-bottom:1px solid var(--rule);background:var(--card);position:sticky;top:0;z-index:3}
.bar input,.bar select,.bar textarea{font:12.5px ui-monospace,monospace;padding:5px 8px;
   border:1px solid var(--rule);border-radius:3px;background:var(--parchment);color:var(--ink)}
.bar textarea{flex:1;min-width:260px;min-height:64px;resize:vertical;white-space:pre}
.bar button{font:12.5px ui-monospace,monospace;padding:5px 12px;border:1px solid var(--pine);
   background:var(--pine);color:var(--parchment);border-radius:3px;cursor:pointer}
.bar button:hover{opacity:.87}
.bar .sp{margin-left:auto;color:var(--ink-3);font:11.5px ui-monospace,monospace}
.err{margin:14px;padding:11px 14px;border-left:3px solid var(--oxide);background:var(--card);
   color:var(--oxide);font:12.5px/1.5 ui-monospace,monospace;white-space:pre-wrap}
.pgr{display:flex;gap:8px;align-items:center;padding:10px 14px;font-size:12.5px;color:var(--ink-2)}
.pgr a{color:var(--pine);text-decoration:none;border:1px solid var(--rule);padding:4px 10px;border-radius:3px}
.pgr a:hover{border-color:var(--pine)}
@media(prefers-color-scheme:dark){.pgr a{color:var(--brass)}}
/* the query lint sits above the result, in brass rather than oxide: it is a
   caution about what the number means, not a failure to produce one */
.lint{margin:12px 14px;padding:10px 13px;border-left:3px solid var(--brass);
   background:var(--card);color:var(--ink-2);font:12px/1.55 ui-monospace,monospace;
   white-space:pre-wrap}
"""

HEAD = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style>
<header><b>Nizam-e-Qanoon corpus</b>
<a href="/">all documents</a> <a href="/tables">data</a> <a href="/sql">sql</a>
<a href="/schema">schema</a>{extra}</header>"""


def page(title: str, body: str, extra: str = "") -> bytes:
    return (HEAD.format(title=html.escape(title), css=CSS, extra=extra)
            + body).encode("utf-8")


def index(query: str, lane: str, source: str) -> bytes:
    where, params = ["1=1"], []
    if query:
        where.append("coalesce(v.title,'') ILIKE %s")
        params.append(f"%{query}%")
    if lane:
        where.append("v.lane = %s")
        params.append(lane)
    if source:
        where.append("v.source_id = %s")
        params.append(source)
    rows = q(f"""SELECT v.document_id, coalesce(v.title,'(untitled)'), v.year, v.source_id,
                        v.page_count, v.char_count, v.lane, v.printable_ratio
                   FROM v_document v WHERE {' AND '.join(where)}
                  ORDER BY v.page_count DESC LIMIT 400""", tuple(params))
    total = q("SELECT count(*) FROM v_document")[0][0]
    sources = [r[0] for r in q("SELECT DISTINCT source_id FROM blob ORDER BY 1")]

    opts = "".join(f'<option{" selected" if s==source else ""}>{s}</option>' for s in sources)
    lanes = "".join(f'<option{" selected" if l==lane else ""}>{l}</option>' for l in ("E2","E3","E4"))
    out = [f"""<div class=wrap>
      <form class=hint style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <input type=search name=q placeholder="search titles…" value="{html.escape(query)}" size=34>
        <select name=source><option value="">every jurisdiction</option>{opts}</select>
        <select name=lane><option value="">every lane</option>{lanes}</select>
        <button style="padding:7px 14px">filter</button>
        <span>{len(rows)} shown of {total:,} documents</span>
      </form>
      <table><tr><th>#</th><th>title</th><th>year</th><th>source</th>
      <th class=num>pages</th><th class=num>chars</th><th>lane</th><th class=num>quality</th></tr>"""]
    for did, title, year, src, pages, chars, ln, ratio in rows:
        r = float(ratio or 0)
        cls = "tag e4" if ln == "E4" else "tag"
        if ln == "E4" and r < 0.70:
            cls = "tag low"
        out.append(f"""<tr><td class=num>{did}</td>
          <td><a href="/doc/{did}">{html.escape(title[:96])}</a></td>
          <td>{html.escape(str(year or ''))}</td><td>{html.escape(src)}</td>
          <td class=num>{pages:,}</td><td class=num>{chars:,}</td>
          <td><span class="{cls}">{ln}</span></td>
          <td class=num>{r:.3f}</td></tr>""")
    out.append("</table></div>")
    return page("Corpus", "".join(out))


def document(did: int) -> bytes:
    meta = q("""SELECT coalesce(v.title,'(untitled)'), v.page_count, v.char_count, v.lane,
                       v.printable_ratio, v.sha256, v.source_id, v.canonical_url, v.language
                  FROM v_document v WHERE v.document_id = %s""", (did,))
    if not meta:
        return page("Not found", "<div class=wrap><p>No such document.</p></div>")
    title, pages, chars, lane, ratio, sha, src, url, langu = meta[0]
    blocks = q("""SELECT page_no, reading_order, text, confidence, script
                    FROM text_block WHERE document_id = %s ORDER BY reading_order""", (did,))

    right, seen = [], None
    for pno, order, text, conf, script in blocks:
        if pno != seen:
            right.append(f'<div class=pg id="p{pno}">page {pno} of {pages}</div>')
            seen = pno
        c = ""
        if conf is not None:
            colour = "var(--oxide)" if float(conf) < 0.70 else "var(--ink-3)"
            c = f'<span class=meta style="color:{colour}">ocr confidence {float(conf):.2f}</span>'
        cls = "blk rtl" if script == "arabic" else "blk"
        right.append(f'<div class="{cls}" id="b{order}">{c}{html.escape(text)}</div>')

    conf_note = ""
    if lane == "E4":
        conf_note = (f' &middot; <b style="color:var(--brass)">OCR</b>, mean confidence '
                     f'{float(ratio or 0):.3f} — compare every line against the scan')
    src_link = f' &middot; <a href="{html.escape(url)}" target=_blank>official source</a>' if url else ""

    body = f"""<div class=wrap>
      <p class=hint><b style="font-size:16px;color:var(--ink)">{html.escape(title)}</b><br>
      document {did} &middot; {src} &middot; {pages} pages &middot; {chars:,} characters
      &middot; lane {lane}{conf_note}{src_link}<br>
      <a href="/doc/{did}.txt">download full text</a> &middot;
      <a href="/blob/{sha}" target=_blank>open the PDF alone</a> &middot;
      jump to page <input id=jump type=number min=1 max={pages} style="width:80px"
        onkeydown="if(event.key==='Enter')go()"> <button onclick="go()">go</button></p>
      <div class=split>
        <div class=pane><h3>source PDF</h3><iframe id=pdf src="/blob/{sha}#page=1"></iframe></div>
        <div class=pane><h3>extracted text — what is in the database</h3>{''.join(right)}</div>
      </div></div>
      <script>
      function go(){{const n=document.getElementById('jump').value;if(!n)return;
        document.getElementById('pdf').src='/blob/{sha}#page='+n;
        const t=document.getElementById('p'+n); if(t) t.scrollIntoView();}}
      </script>"""
    return page(title, body, f' <a href="/doc/{did}.txt">plain text</a>')


def plain(did: int) -> bytes:
    rows = q("""SELECT page_no, text FROM text_block
                 WHERE document_id=%s ORDER BY reading_order""", (did,))
    meta = q("SELECT coalesce(title,'(untitled)'), page_count FROM v_document WHERE document_id=%s",
             (did,))
    title, pages = meta[0] if meta else ("(unknown)", 0)
    out, seen = [f"{title}\ndocument {did} - {pages} pages\n{'='*72}\n"], None
    for pno, text in rows:
        if pno != seen:
            out.append(f"\n\n{'-'*72}\n[page {pno}]\n{'-'*72}\n")
            seen = pno
        out.append(text)
    return "".join(out).encode("utf-8")


# The identity ladder from Document 02 §7, drawn from the tables that actually
# exist. Shown on /schema so the relationship between them is visible without
# having to reconstruct it from foreign keys.
LADDER = """source_observation   what a portal exposed, and when      (many rows per file)
        |  sha256
        v
      blob           bytes, identified by SHA-256          (one row per distinct file)
        |  sha256
        v
    document         a blob read as text, in one language  (one per extractor run)
        |  id                                                lane E2 / E3 / E4
        +--&gt; page          per page: size, chars, lane
        |       |  (document_id, page_no)
        |       v
        +--&gt; text_block    THE LAW: text + {page, bbox, reading_order, script, confidence}

 extraction_attempt  every attempt, successful or not -- the OCR backlog is a query on it

 not yet built:  instrument -&gt; provision -&gt; provision_version   (doc 03 §2)
                 provisions are the citable unit (INV-4), versioned by date (INV-5)"""


def schema() -> bytes:
    """The live catalogue -- not a diagram someone drew once and let rot."""
    tables = q("""
        SELECT c.relname, obj_description(c.oid),
               pg_size_pretty(pg_total_relation_size(c.oid)), c.relkind
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind IN ('r','v')
         ORDER BY c.relkind DESC, c.relname""")

    counts = {}
    for name, _, _, kind in tables:
        if kind == "r":
            try:
                counts[name] = q('SELECT count(*) FROM "%s"' % name)[0][0]
            except Exception:
                counts[name] = None

    cols = q("""
        SELECT c.table_name, c.column_name, c.data_type, c.is_nullable, c.column_default,
               col_description(pc.oid, c.ordinal_position)
          FROM information_schema.columns c
          JOIN pg_class pc ON pc.relname = c.table_name
          JOIN pg_namespace n ON n.oid = pc.relnamespace AND n.nspname = 'public'
         WHERE c.table_schema = 'public'
         ORDER BY c.table_name, c.ordinal_position""")

    keys = q("""
        SELECT tc.table_name, kcu.column_name, tc.constraint_type,
               ccu.table_name, ccu.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = 'public'
          LEFT JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = 'public'
         WHERE tc.table_schema = 'public'
           AND tc.constraint_type IN ('PRIMARY KEY','FOREIGN KEY')""")
    pk, fk = {}, []
    for t, col, kind, ft, fc in keys:
        if kind == "PRIMARY KEY":
            pk.setdefault(t, set()).add(col)
        else:
            fk.append((t, col, ft, fc))

    idx = q("SELECT tablename, indexdef FROM pg_indexes WHERE schemaname='public'"
            " ORDER BY tablename, indexname")
    enums = q("""SELECT t.typname, string_agg(e.enumlabel, ', ' ORDER BY e.enumsortorder)
                   FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
                   JOIN pg_namespace n ON n.oid = t.typnamespace AND n.nspname = 'public'
                  GROUP BY t.typname ORDER BY t.typname""")
    exts = q("SELECT extname, extversion FROM pg_extension ORDER BY extname")
    try:
        mig = q("SELECT version, to_char(applied_at,'YYYY-MM-DD HH24:MI')"
                " FROM schema_migration ORDER BY version")
    except Exception:
        mig = []

    o = ["<div class=wrap>"]
    o.append("<p class=hint><b style=\"font-size:16px;color:var(--ink)\">How the tables relate</b>"
             "<br>Doc 02 &sect;7's identity ladder, one rung per table. Each is a different thing, "
             "and conflating them is the mistake that cannot be undone later.</p>"
             "<pre style=\"background:var(--card);border:1px solid var(--rule);border-radius:10px;"
             "padding:16px;overflow:auto;font:12.5px/1.7 ui-monospace,monospace\">" + LADDER + "</pre>")

    o.append("<p class=hint><b style=\"font-size:16px;color:var(--ink)\">Extensions</b> &mdash; "
             + ", ".join("%s %s" % (html.escape(a), html.escape(b)) for a, b in exts)
             + "<br><b style=\"color:var(--ink)\">Migrations applied</b> &mdash; "
             + (", ".join("%s (%s)" % (html.escape(v), d) for v, d in mig) or "none") + "</p>")

    if enums:
        o.append("<p class=hint><b style=\"font-size:16px;color:var(--ink)\">Enumerated types</b>"
                 "</p><table><tr><th>type</th><th>values</th></tr>")
        for n, vals in enums:
            o.append("<tr><td><code>%s</code></td><td>%s</td></tr>"
                     % (html.escape(n), html.escape(vals)))
        o.append("</table>")

    for name, comment, size, kind in tables:
        n = counts.get(name)
        meta = ("%s rows &middot; %s" % (format(n, ","), size)) if n is not None else size
        o.append("<p class=hint style=\"margin-top:26px\">"
                 "<b style=\"font-size:16px;color:var(--ink)\">%s</b> "
                 "<span class=tag>%s</span> %s%s</p>"
                 % (html.escape(name), "view" if kind == "v" else "table", meta,
                    "<br>" + html.escape(comment) if comment else ""))
        o.append("<table><tr><th>column</th><th>type</th><th>null</th>"
                 "<th>key</th><th>note</th></tr>")
        for t, col, typ, nullable, default, ccomment in cols:
            if t != name:
                continue
            marks = []
            if col in pk.get(name, ()):
                marks.append("<span class=tag>PK</span>")
            for a, b, tt, tc in fk:
                if a == name and b == col:
                    marks.append("<span class=\"tag e4\">FK &rarr; %s.%s</span>"
                                 % (html.escape(tt), html.escape(tc)))
            note = ccomment or ("" if default is None else "default " + str(default))
            o.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td>"
                     "<td>%s</td></tr>"
                     % (html.escape(col), html.escape(typ),
                        "yes" if nullable == "YES" else "no",
                        " ".join(marks), html.escape(str(note)[:90])))
        o.append("</table>")

        mine = [d for tn, d in idx if tn == name]
        if mine:
            o.append("<p class=hint style=\"margin:8px 0 0\">indexes</p><table>")
            for d in mine:
                o.append("<tr><td><code style=\"font-size:12px\">%s</code></td></tr>"
                         % html.escape(d))
            o.append("</table>")

    o.append("</div>")
    return page("Schema", "".join(o))


MAX_ROWS = 200          # one screenful of evidence, not a data export
SQL_TIMEOUT_MS = 15000


def q_ro(sql: str, params: tuple = ()) -> tuple[list[str], list[tuple]]:
    """Run one statement inside a READ ONLY transaction, and return names + rows.

    The read-only guarantee is Postgres's, not this module's: a write inside a
    READ ONLY transaction is rejected by the server even if the check in
    sql_console() were somehow bypassed. The timeout stops a careless join from
    holding a connection open for the rest of the afternoon.
    """
    with psycopg.connect(dsn()) as c:
        c.read_only = True
        with c.cursor() as cur:
            cur.execute(f"SET statement_timeout = {SQL_TIMEOUT_MS}")
            cur.execute(sql, params)
            cols = [d.name for d in (cur.description or [])]
            return cols, cur.fetchall()


def relations() -> list[tuple]:
    """Every table and view, with size and an estimated row count.

    reltuples is an estimate maintained by ANALYZE, which is what makes this
    list instant on a 4 GB database. The exact count is computed on the table
    page itself, where one count is affordable and the number matters.
    """
    return q("""
        SELECT c.relname,
               CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view'
                              WHEN 'm' THEN 'matview' ELSE c.relkind::text END AS kind,
               CASE WHEN c.relkind = 'r'
                    THEN pg_size_pretty(pg_total_relation_size(c.oid)) ELSE '' END AS size,
               CASE WHEN c.relkind = 'r' THEN greatest(c.reltuples, 0)::bigint END AS est_rows
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m')
         ORDER BY c.relkind, c.relname
    """)


def _human(n) -> str:
    if n is None:
        return ""
    n = int(n)
    return f"{n/1e6:.1f}M" if n >= 1e6 else (f"{n/1e3:.0f}k" if n >= 1000 else str(n))


def sidebar(current: str = "") -> str:
    rows = relations()
    out = []
    for kind in ("table", "view", "matview"):
        group = [r for r in rows if r[1] == kind]
        if not group:
            continue
        out.append(f"<h4>{html.escape(kind)}s &middot; {len(group)}</h4>")
        for name, _k, size, est in group:
            on = " class=on" if name == current else ""
            note = size or (_human(est) if est else "")
            out.append(f'<a href="/table/{urllib.parse.quote(name)}"{on}>'
                       f'<span>{html.escape(name)}</span><i>{html.escape(note)}</i></a>')
    return "".join(out)


def grid(cols: list[str], rows: list[tuple], types: dict | None = None,
         sort_base: str = "", sort: str = "", desc: bool = False) -> str:
    """Render rows as a table. Long text wraps; NULL is shown as NULL, not blank."""
    if not cols:
        return '<p class="hint" style="padding:14px">No columns.</p>'
    head = []
    for c in cols:
        label = html.escape(c)
        if sort_base:
            nxt = f"{sort_base}sort={urllib.parse.quote(c)}&desc={'0' if (sort == c and not desc) else '1'}"
            arrow = " &darr;" if (sort == c and desc) else (" &uarr;" if sort == c else "")
            label = f'<a href="{html.escape(nxt)}">{label}{arrow}</a>'
        t = (types or {}).get(c, "")
        head.append(f"<th>{label}<small>{html.escape(t)}</small></th>")
    body = []
    for r in rows:
        cells = []
        for v in r:
            if v is None:
                cells.append('<td class="null">NULL</td>')
                continue
            s = str(v)
            cls = " class=wrap" if len(s) > 90 else ""
            if len(s) > 4000:
                s = s[:4000] + " …"
            cells.append(f"<td{cls}>{html.escape(s)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return ('<table class=grid><thead><tr>' + "".join(head) + "</tr></thead><tbody>"
            + "".join(body) + "</tbody></table>")


def tables_page() -> bytes:
    rows = relations()
    tbl = [r for r in rows if r[1] == "table"]
    body = ('<div class=dsplit><nav class=side>' + sidebar() + '</nav><div class=main>'
            '<div class=bar><b>Every relation in the database</b>'
            f'<span class=sp>{len(tbl)} tables &middot; {len(rows)-len(tbl)} views</span></div>'
            + grid(["relation", "kind", "size on disk", "rows (estimate)"],
                   [(n, k, s, _human(e)) for n, k, s, e in rows])
            + '</div></div>')
    return page("data · Nizam-e-Qanoon", body)


def table_page(name: str, params: dict) -> bytes:
    # The name is checked against the catalog rather than escaped: an identifier
    # cannot be parameterised, so the only safe move is to accept only names
    # Postgres itself reports.
    known = {r[0] for r in relations()}
    if name not in known:
        return page("unknown", '<p class="err">No such table or view.</p>')

    cols_rows = q("""SELECT column_name, data_type FROM information_schema.columns
                      WHERE table_schema='public' AND table_name=%s
                      ORDER BY ordinal_position""", (name,))
    colnames = [c for c, _ in cols_rows]
    types = dict(cols_rows)

    sort = params.get("sort", [""])[0]
    sort = sort if sort in colnames else ""
    desc = params.get("desc", ["0"])[0] == "1"
    fcol = params.get("fcol", [""])[0]
    fcol = fcol if fcol in colnames else ""
    fval = params.get("f", [""])[0]
    try:
        offset = max(0, int(params.get("offset", ["0"])[0]))
    except ValueError:
        offset = 0

    where, args = "", []
    if fcol and fval:
        where = f' WHERE {psycopg.sql.Identifier(fcol).as_string(None)}::text ILIKE %s'
        args.append(f"%{fval}%")
    order = (f' ORDER BY {psycopg.sql.Identifier(sort).as_string(None)}'
             f'{" DESC" if desc else ""} NULLS LAST') if sort else ""
    rel = psycopg.sql.Identifier(name).as_string(None)

    total = q(f"SELECT count(*) FROM {rel}{where}", tuple(args))[0][0]
    _c, rows = q_ro(f"SELECT * FROM {rel}{where}{order} LIMIT {MAX_ROWS} OFFSET {offset}",
                    tuple(args))

    base = f"/table/{urllib.parse.quote(name)}?"
    if fcol and fval:
        base += f"fcol={urllib.parse.quote(fcol)}&f={urllib.parse.quote(fval)}&"
    opts = "".join(f'<option value="{html.escape(c)}"{" selected" if c == fcol else ""}>'
                   f'{html.escape(c)}</option>' for c in colnames)
    pager = ""
    if total > MAX_ROWS:
        prev = f'<a href="{base}sort={urllib.parse.quote(sort)}&desc={int(desc)}&offset={max(0, offset-MAX_ROWS)}">&larr; previous</a>' if offset else ""
        nxt = f'<a href="{base}sort={urllib.parse.quote(sort)}&desc={int(desc)}&offset={offset+MAX_ROWS}">next &rarr;</a>' if offset + MAX_ROWS < total else ""
        pager = (f'<div class=pgr>{prev}<span>rows {offset+1:,}–'
                 f'{min(offset+MAX_ROWS, total):,} of {total:,}</span>{nxt}</div>')

    body = ('<div class=dsplit><nav class=side>' + sidebar(name) + '</nav><div class=main>'
            f'<form class=bar method=get action="/table/{urllib.parse.quote(name)}">'
            f'<b>{html.escape(name)}</b>'
            f'<select name=fcol>{opts}</select>'
            f'<input name=f placeholder="contains…" value="{html.escape(fval)}">'
            '<button>filter</button>'
            f'<span class=sp>{total:,} rows &middot; {len(colnames)} columns</span></form>'
            + pager
            + grid(colnames, rows, types, base, sort, desc)
            + pager + '</div></div>')
    return page(f"{name} · data", body)


SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.I)


def sql_page(sql: str) -> bytes:
    result, err, took, lint = "", "", "", ""
    if sql.strip():
        stripped = sql.strip().rstrip(";")
        if ";" in stripped:
            err = "One statement at a time. Semicolons are not accepted."
        elif not SELECT_ONLY.match(stripped):
            err = "Only SELECT and WITH are accepted. This console is read-only."
        else:
            # Lint before running: the caveat has to arrive before the number.
            lint = sqlcheck.render(sqlcheck.check(stripped))
            import time
            t0 = time.time()
            try:
                cols, rows = q_ro(f"SELECT * FROM ({stripped}) _q LIMIT {MAX_ROWS}")
                took = f"{(time.time()-t0)*1000:.0f} ms · {len(rows)} row(s)"
                if len(rows) == MAX_ROWS:
                    took += f" (capped at {MAX_ROWS})"
                result = grid(cols, rows)
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"

    body = ('<div class=dsplit><nav class=side>' + sidebar() + '</nav><div class=main>'
            '<form class=bar method=get action="/sql">'
            f'<textarea name=q placeholder="SELECT jurisdiction, count(*) FROM v_release_instrument '
            f'GROUP BY 1 ORDER BY 2 DESC">{html.escape(sql)}</textarea>'
            f'<button>run</button><span class=sp>{html.escape(took)}</span></form>'
            + (f'<div class=err>{html.escape(err)}</div>' if err else "")
            + (f'<div class=lint>{html.escape(lint)}</div>' if lint else "")
            + (result or ('<p class="hint" style="padding:14px">'
                          'SELECT or WITH only, one statement, read-only transaction, '
                          f'{SQL_TIMEOUT_MS//1000}s timeout, {MAX_ROWS} rows max.</p>'))
            + '</div></div>')
    return page("sql · Nizam-e-Qanoon", body)


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p, params = u.path, urllib.parse.parse_qs(u.query)
        try:
            if p == "/":
                return self._send(index(params.get("q", [""])[0],
                                        params.get("lane", [""])[0],
                                        params.get("source", [""])[0]))
            if p == "/schema":
                return self._send(schema())
            if p == "/tables":
                return self._send(tables_page())
            if p == "/sql":
                return self._send(sql_page(params.get("q", [""])[0]))
            m = re.fullmatch(r"/table/([A-Za-z0-9_]+)", p)
            if m:
                return self._send(table_page(m.group(1), params))
            m = re.fullmatch(r"/doc/(\d+)", p)
            if m:
                return self._send(document(int(m.group(1))))
            m = re.fullmatch(r"/doc/(\d+)\.txt", p)
            if m:
                return self._send(plain(int(m.group(1))), "text/plain; charset=utf-8")
            m = re.fullmatch(r"/blob/([0-9a-f]{64})", p)
            if m:
                sha = m.group(1)
                rows = q("SELECT object_key FROM blob WHERE sha256=%s", (sha,))
                if not rows:
                    return self._send(b"unknown blob", "text/plain")
                f = CORPUS_ROOT / rows[0][0]
                if not f.exists():
                    return self._send(b"blob missing from the store", "text/plain")
                # inline so the browser renders it in the iframe next to the text
                return self._send(f.read_bytes(), "application/pdf",
                                  {"Content-Disposition": f'inline; filename="{sha[:12]}.pdf"'})
            self.send_error(404)
        except Exception as exc:                      # a browser tab must not kill the server
            self._send(f"<pre>{html.escape(type(exc).__name__ + ': ' + str(exc))}</pre>".encode(),
                       "text/html; charset=utf-8")

    def log_message(self, *a):                        # quiet
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only corpus browser")
    ap.add_argument("--port", type=int, default=5055)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    n = q("SELECT count(*) FROM v_document")[0][0]
    print(f"corpus browser: {n:,} documents")
    print(f"  http://localhost:{a.port}")
    print("  read-only; Ctrl-C to stop")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
