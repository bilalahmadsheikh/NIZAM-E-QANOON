"""A read-only MCP server over the corpus database.

WHY THIS EXISTS RATHER THAN AN OFF-THE-SHELF PACKAGE. The obvious choice,
`@modelcontextprotocol/server-postgres`, is deprecated on npm -- "Package no
longer supported" -- and the surviving alternatives are third-party. An MCP
server receives the database credentials and can issue any statement the role
permits, so for a corpus where every write is supposed to be an append-only,
audited revision, handing that to unaudited code is the wrong trade. This is
~150 lines, it reads the same `infra/.env` the rest of the project uses, and it
cannot write.

READ-ONLY IS THE SERVER'S, NOT THE CALLER'S. Every query runs inside a
`READ ONLY` transaction with a statement timeout, so Postgres itself refuses a
write even if the SELECT-only check here were bypassed. That is the same pair of
guarantees the corpus browser uses, and it is deliberate duplication: the rule in
doc 09a §2 -- inspection tools never become a way to change what is stored --
has to hold at every door, not just the one people remember.

Registered by .mcp.json in the repository root. The connection string is never
written to that file: this reads infra/.env, which is gitignored.

    tools:  query · list_tables · describe_table
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sqlcheck                      # noqa: E402  same directory, no package

ROOT = Path(__file__).resolve().parents[1]
MAX_ROWS = 500
TIMEOUT_MS = 20000
SELECT_ONLY = re.compile(r"^\s*(select|with|explain|show|table)\b", re.I)


def load_env() -> None:
    env = ROOT / "infra" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def dsn() -> str:
    load_env()
    return (f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
            f"port={os.environ.get('POSTGRES_PORT', '5433')} "
            f"dbname={os.environ.get('POSTGRES_DB', 'nizam_clean')} "
            f"user={os.environ.get('POSTGRES_USER', 'nizam')} "
            f"password={os.environ.get('POSTGRES_PASSWORD', '')}")


def run(sql: str, params: tuple = ()) -> tuple[list[str], list[tuple]]:
    with psycopg.connect(dsn()) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {TIMEOUT_MS}")
            cur.execute(sql, params)
            cols = [d.name for d in (cur.description or [])]
            return cols, cur.fetchall()


def as_table(cols: list[str], rows: list[tuple]) -> str:
    """Markdown, because that is what renders usefully in a transcript."""
    if not cols:
        return "(no columns)"
    if not rows:
        return "(0 rows)"
    def cell(v):
        if v is None:
            return "NULL"
        s = " ".join(str(v).split())
        return s[:300] + " …" if len(s) > 300 else s
    body = [[cell(v) for v in r] for r in rows]
    widths = [min(60, max(len(c), *(len(r[i]) for r in body))) for i, c in enumerate(cols)]
    out = ["| " + " | ".join(c[:w].ljust(w) for c, w in zip(cols, widths)) + " |",
           "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    for r in body:
        out.append("| " + " | ".join(v[:w].ljust(w) for v, w in zip(r, widths)) + " |")
    return "\n".join(out)


TOOLS = [
    {"name": "query",
     "description": "Run one read-only SQL query against the Nizam-e-Qanoon corpus "
                    "(nizam_clean) and return the rows as a table. SELECT, WITH, "
                    "EXPLAIN, SHOW and TABLE only; writes are refused by the server. "
                    "Remember most tables keep retired revisions: filter is_active "
                    "for the live corpus.",
     "inputSchema": {"type": "object",
                     "properties": {"sql": {"type": "string",
                                            "description": "One SQL statement, no semicolon."}},
                     "required": ["sql"]}},
    {"name": "list_tables",
     "description": "Every table and view in the corpus database with its size and "
                    "estimated row count.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "describe_table",
     "description": "Columns, types, nullability and indexes for one table or view.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"}},
                     "required": ["name"]}},
]


def call_tool(name: str, args: dict) -> str:
    if name == "query":
        sql = (args.get("sql") or "").strip().rstrip(";")
        if not sql:
            return "No SQL given."
        if ";" in sql:
            return "One statement at a time; semicolons are not accepted."
        if not SELECT_ONLY.match(sql):
            return ("Refused: this server is read-only. Only SELECT, WITH, EXPLAIN, "
                    "SHOW and TABLE are accepted.")
        # Lint BEFORE running, and prepend it whatever happens. Two reasons: a
        # caller who reads the number first and the caveat second has already
        # believed the number; and a query that ERRORS deserves the lint most of
        # all, since the lint often explains the error. It never blocks.
        warn = sqlcheck.render(sqlcheck.check(sql))
        head = warn + "\n\n" if warn else ""
        try:
            cols, rows = run(f"SELECT * FROM ({sql}) _q LIMIT {MAX_ROWS}")
        except Exception as exc:
            return head + f"{type(exc).__name__}: {exc}"
        note = (f"\n\n({len(rows)} rows"
                + (f", capped at {MAX_ROWS}" if len(rows) == MAX_ROWS else "") + ")")
        return head + as_table(cols, rows) + note

    if name == "list_tables":
        cols, rows = run("""
            SELECT c.relname AS relation,
                   CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view'
                                  WHEN 'm' THEN 'matview' END AS kind,
                   CASE WHEN c.relkind='r'
                        THEN pg_size_pretty(pg_total_relation_size(c.oid)) END AS size,
                   CASE WHEN c.relkind='r' THEN greatest(c.reltuples,0)::bigint END AS est_rows
              FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relkind IN ('r','v','m')
             ORDER BY c.relkind, c.relname""")
        return as_table(cols, rows)

    if name == "describe_table":
        t = args.get("name", "")
        cols, rows = run("""
            SELECT column_name, data_type, is_nullable, column_default
              FROM information_schema.columns
             WHERE table_schema='public' AND table_name=%s
             ORDER BY ordinal_position""", (t,))
        if not rows:
            return f"No such table or view: {t}"
        icols, irows = run("SELECT indexname, indexdef FROM pg_indexes "
                           "WHERE schemaname='public' AND tablename=%s ORDER BY indexname", (t,))
        return (f"### {t}\n\n" + as_table(cols, rows)
                + ("\n\n### indexes\n\n" + as_table(icols, irows) if irows else ""))

    return f"Unknown tool: {name}"


def reply(rid, result=None, error=None) -> None:
    msg = {"jsonrpc": "2.0", "id": rid}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, rid = req.get("method"), req.get("id")

        if method == "initialize":
            # Echo the client's protocol version rather than pinning one here:
            # the negotiated version is the client's to choose, and hard-coding
            # a guess is how a server stops working after an upgrade.
            ver = (req.get("params") or {}).get("protocolVersion", "2025-06-18")
            reply(rid, {"protocolVersion": ver,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "nizam-db", "version": "1.0.0"}})
        elif method in ("notifications/initialized", "initialized"):
            continue                                   # a notification takes no reply
        elif method == "tools/list":
            reply(rid, {"tools": TOOLS})
        elif method == "tools/call":
            p = req.get("params") or {}
            try:
                text = call_tool(p.get("name", ""), p.get("arguments") or {})
                reply(rid, {"content": [{"type": "text", "text": text}]})
            except Exception as exc:                   # a bad query must not kill the server
                reply(rid, {"content": [{"type": "text",
                                         "text": f"{type(exc).__name__}: {exc}"}],
                            "isError": True})
        elif method == "ping":
            reply(rid, {})
        elif rid is not None:
            reply(rid, error={"code": -32601, "message": f"method not found: {method}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
