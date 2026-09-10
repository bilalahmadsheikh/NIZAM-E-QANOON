"""Catch the semantic SQL mistakes that return a plausible wrong number.

A syntax error announces itself. These do not:

    SELECT count(*) FROM instrument                      -- counts duplicates
    SELECT count(*) FROM provision                       -- counts retired revisions
    SELECT ... FROM text_block WHERE document_id = 4441  -- counts retired revisions
    SELECT text FROM provision                           -- there is no text column

Every one of those runs, returns a number, and the number is wrong. Over one
working day two coding agents made the third and fourth of them, and the wrong
answers looked entirely reasonable -- a search for theft sections returned every
section twice and nobody would have noticed from the output alone.

Documentation does not fix this, because the failure is forgetting rather than
not knowing. A check at the point of execution does. This module is deliberately
dependency-free and regex-based: it is a lint, not a parser, and it must never
be the reason a query cannot run. It WARNS; it never refuses.

    from sqlcheck import check
    for f in check(sql): print(f.severity, f.message)
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    severity: str          # 'error' -- the query cannot be right
                           # 'warn'  -- probably counts the wrong rows
                           # 'note'  -- a better relation exists
    rule: str
    message: str
    fix: str


def _strip(sql: str) -> str:
    """Remove strings and comments so their contents cannot trigger a rule."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"\$\$.*?\$\$", " 'x' ", sql, flags=re.S)
    sql = re.sub(r"'(?:[^']|'')*'", " 'x' ", sql)
    return sql


def _mentions(sql: str, table: str) -> bool:
    """Is this table actually referenced, rather than merely a substring?

    `provision` must not match `provision_version`, and `page` must not match
    `page_no` or `page_ocr_candidate` -- the reason this uses a boundary on both
    sides rather than a bare `in` test.
    """
    return re.search(rf"\b(from|join|update|into)\s+(?:only\s+)?\"?{table}\"?\b",
                     sql, re.I) is not None


def _has(sql: str, pattern: str) -> bool:
    return re.search(pattern, sql, re.I) is not None


# A live-state filter can be spelled several ways, and a lint that only knows one
# of them cries wolf. `d.is_active`, `is_active`, `AND i.is_active IS TRUE` and a
# join to a v_release_* or v_*_pending view all count as the caller having thought
# about it.
_ACTIVE = r"\bis_active\b|\bv_release_|\bv_active_|\bv_[a-z_]*pending\b"
_DUPLICATE = r"\bduplicate_of\b|\bv_release_"

RULES = [
    dict(rule="provision-has-no-text",
         severity="error",
         test=lambda s: _mentions(s, "provision")
                        and _has(s, r"\bp?\.?text\b")
                        and not _mentions(s, "provision_version"),
         message="`provision` has no text column — it carries structure "
                 "(label, path, heading) only.",
         fix="Join provision_version for the words. INV-5 means text is bounded "
             "by validity, so pick the version as at your date."),

    dict(rule="instrument-without-duplicate-filter",
         severity="warn",
         test=lambda s: _mentions(s, "instrument") and not _has(s, _DUPLICATE),
         message="`instrument` queried without `duplicate_of IS NULL` — exact "
                 "duplicates are linked, not removed, so counts come back inflated.",
         fix="Add `AND duplicate_of IS NULL`, or read v_release_instrument."),

    dict(rule="live-table-without-is-active",
         severity="warn",
         test=lambda s: any(_mentions(s, t) for t in
                            ("document", "instrument", "provision", "provision_version"))
                        and not _has(s, _ACTIVE),
         message="A revisioned table queried without `is_active` — the corpus is "
                 "append-only, so this counts every generation ever produced.",
         fix="Add `is_active`, or read one of the v_release_* views."),

    dict(rule="text-block-needs-document-join",
         severity="warn",
         test=lambda s: (_mentions(s, "text_block") or _mentions(s, "page"))
                        and not _mentions(s, "document"),
         message="`text_block` and `page` have no `is_active` of their own — the "
                 "flag lives on `document`, so this reads retired revisions too.",
         fix="JOIN document d ON d.id = <t>.document_id AND d.is_active."),

    dict(rule="ocr-candidate-joins-active-document",
         severity="note",
         test=lambda s: _mentions(s, "page_ocr_candidate")
                        and _has(s, r"\bd\.is_active\b|\bdocument\b.*\bis_active\b"),
         message="Candidates point at the revision they were proposed against, "
                 "which a promotion retires — joining `d.is_active` silently "
                 "returns nothing for every promoted document.",
         fix="Join on sha256, or read extractor_config->'ocr_promotion'."),

    dict(rule="unbounded-select-star",
         severity="note",
         test=lambda s: _has(s, r"select\s+\*")
                        and not _has(s, r"\blimit\b")
                        and any(_mentions(s, t) for t in
                                ("provision", "text_block", "provision_version",
                                 "provision_ancestor", "provision_block")),
         message="`SELECT *` over a large table with no LIMIT — provision and "
                 "text_block are hundreds of thousands of rows.",
         fix="Add a LIMIT, or select the columns you need."),

    dict(rule="counts-without-grouping-context",
         severity="note",
         test=lambda s: _has(s, r"\bcount\s*\(\s*\*\s*\)")
                        and _mentions(s, "provision")
                        and not _has(s, r"\bgroup\s+by\b"),
         message="A bare count over provisions mixes every instrument together; "
                 "520k live rows is rarely the answer to a real question.",
         fix="GROUP BY instrument_id or join instrument to scope it."),
]


def check(sql: str) -> list[Finding]:
    """Return findings, most severe first. Never raises: a lint must not block."""
    try:
        s = _strip(sql)
    except Exception:
        return []
    out = []
    for r in RULES:
        try:
            if r["test"](s):
                out.append(Finding(r["severity"], r["rule"], r["message"], r["fix"]))
        except Exception:
            continue                      # a broken rule must not break the query
    order = {"error": 0, "warn": 1, "note": 2}
    return sorted(out, key=lambda f: order.get(f.severity, 3))


def render(findings: list[Finding], width: int = 88) -> str:
    """A short block to put above a result set. Empty when the query looks sound."""
    if not findings:
        return ""
    mark = {"error": "ERROR", "warn": "WARN ", "note": "note "}
    lines = ["query check:"]
    for f in findings:
        lines.append(f"  {mark.get(f.severity, '     ')} [{f.rule}] {f.message}")
        lines.append(f"         → {f.fix}")
    return "\n".join(lines)


if __name__ == "__main__":                # a smoke test over the mistakes actually made
    CASES = [
        ("SELECT count(*) FROM instrument WHERE jurisdiction='sindh'", "instrument-without-duplicate-filter"),
        ("SELECT string_agg(text,' ') FROM text_block WHERE document_id=4441", "text-block-needs-document-join"),
        ("SELECT text FROM provision WHERE label='378'", "provision-has-no-text"),
        ("SELECT count(*) FROM v_release_instrument", None),
        ("SELECT i.id FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL", None),
    ]
    bad = 0
    for sql, expect in CASES:
        got = {f.rule for f in check(sql)}
        ok = (expect in got) if expect else not got
        bad += 0 if ok else 1
        print(("ok  " if ok else "FAIL"), f"{expect or '(clean)':38} {sorted(got)}")
    raise SystemExit(bad)
