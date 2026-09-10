"""Find source-evidenced legal-instrument boundaries inside official PDFs.

The detector proposes review items; it never splits a PDF and never changes
source text.  A strong proposal needs a title/notification marker plus nearby
independent legal-form evidence (identity line, enactment/delegated-power
formula, or a section/rule 1 reset).  Repeated running headers, contents lines,
amendment footnotes and bare citations are excluded.

Run dry first, then persist the same source-anchored evidence::

    POSTGRES_DB=nizam_clean uv run python tools/detect_multi_instrument.py
    POSTGRES_DB=nizam_clean uv run python tools/detect_multi_instrument.py --apply
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass

from nizam.storage.db import connect

METHOD = "nizam.multi_instrument_detector/1"

KIND = re.compile(
    r"\b(CONSTITUTION|ACT|ORDINANCE|RULES?|REGULATIONS?|ORDER|NOTIFICATION|S\.?\s*R\.?\s*O\.?)\b",
    re.I,
)
YEAR = re.compile(r"\b(18\d{2}|19\d{2}|20[0-4]\d)\b")
IDENTITY = re.compile(
    r"\b(?:ACT|ORDINANCE)\s+(?:NO\.?\s*)?([IVXLCDM]+|\d{1,3})\s+OF\s+(18\d{2}|19\d{2}|20[0-4]\d)\b",
    re.I,
)
IDENTITY_LINE = re.compile(
    r"^\(?\s*(?:[A-Z][A-Z ]{2,40}\s+)?(?:ACT|ORDINANCE)\s+"
    r"(?:NO\.?\s*)?(?:[IVXLCDM]+|\d{1,3})\s+OF\s+"
    r"(?:18\d{2}|19\d{2}|20[0-4]\d)\s*\)?$",
    re.I,
)
FORMULA = re.compile(
    r"\b(?:it\s+is\s+hereby\s+enacted|whereas\s+it\s+is\s+expedient|"
    r"in\s+exercise\s+of\s+(?:(?:the|all)\s+)?powers?|governor[^\n.]{0,100}\bpleased|"
    r"\bhas\s+made\s+(?:the\s+following\s+)?rules)\b",
    re.I,
)
RESET = re.compile(
    r"(?:^|\n)\s*(?:section\s+|rule\s+|regulation\s+)?1\s*[.()\-—:]\s*"
    r"(?:\(\s*1\s*\)\s*)?"
    r"(?:short\s+title|these\s+(?:rules|regulations)|this\s+(?:act|ordinance|order)|definitions?)\b",
    re.I,
)
RESET_HEADING = re.compile(
    r"(?:^|\n)\s*(?:section\s+|rule\s+|regulation\s+)?1\s*[.()\-â€”:]\s*"
    r"(?:\(\s*1\s*\)\s*)?(?:short\s+title|definitions?)\b",
    re.I,
)
CALLED_TITLE = re.compile(
    # PDF text blocks frequently wrap the self-name across visual lines.
    # Keep the capture bounded, but allow those embedded newlines.
    r"\b(?:(?:may|shall)\s+be\s+called\s*,?|may\s+be\s+cited\s+as)\s+"
    r"(?:the\s+)?([\s\S]{5,180}?\b"
    r"(?:Act|Ordinance|Rules?|Regulations?|Order)\s*[,\-]?\s*(?:18\d{2}|19\d{2}|20[0-4]\d))\b",
    re.I,
)
FOOTNOTE = re.compile(
    r"\b(?:substituted|inserted|amended|omitted|repealed)\s+by\b|"
    r"\b(?:section|article|rule)\s+\d+[A-Z-]*\s+of\s+(?:the\s+)?[^\n]{0,100}\b(?:act|ordinance|rules?)\b",
    re.I,
)
DOT_LEADER = re.compile(r"\.{4,}\s*\d{1,4}\s*$")
SPACE = re.compile(r"\s+")
TERMINAL_KIND = re.compile(
    r"\b(Act|Ordinance|Rules?|Regulations?|Order|Notification)\b"
    r"\s*,?\s*(?:18\d{2}|19\d{2}|20[0-4]\d)?\s*[.)\]]*\s*$",
    re.I,
)
COMPILATION_TITLE = re.compile(
    r"\b(?:estacode|compendium|compilation|guide\s*book|manual|rules\s*&\s*regulations)\b",
    re.I,
)


@dataclass(frozen=True)
class Proposal:
    block_id: int
    page: int
    title: str
    kind: str
    year: int | None
    number: str | None
    confidence: float
    evidence: dict


def _normalise(value: str) -> str:
    return SPACE.sub(" ", value).strip().casefold()


def _title_tokens(value: str) -> set[str]:
    stop = {"the", "of", "and", "a", "an", "no", "act", "ordinance",
            "rule", "rules", "regulation", "regulations", "notification"}
    tokens = set()
    for word in re.findall(r"[A-Za-z]{3,}", value):
        word = word.casefold()
        if word.endswith("s") and len(word) > 4:
            word = word[:-1]
        if word not in stop:
            tokens.add(word)
    return tokens


def _same_title(candidate: str, outer: str | None) -> bool:
    if not outer:
        return False
    candidate_years = set(YEAR.findall(candidate))
    outer_years = set(YEAR.findall(outer))
    if candidate_years and outer_years and candidate_years.isdisjoint(outer_years):
        return False
    candidate_kind = KIND.search(candidate)
    outer_kind = KIND.search(outer)
    if candidate_kind and outer_kind:
        ck = candidate_kind.group(1).lower().rstrip("s")
        ok = outer_kind.group(1).lower().rstrip("s")
        if ck != ok:
            return False
    a, b = _title_tokens(candidate), _title_tokens(outer)
    if a and b and len(a & b) / min(len(a), len(b)) >= 0.70:
        return True
    # Portal metadata and OCR disagree on small spellings (Shaeed/Shaheed,
    # Bakhsh/Bakksh).  With the same year and terminal legal form, a high fuzzy
    # title ratio identifies the outer opening without treating a cited base
    # Act as the amendment instrument.
    left = " ".join(sorted(a))
    right = " ".join(sorted(b))
    return bool(left and right and difflib.SequenceMatcher(None,left,right).ratio() >= 0.78)


def _uppercase_ratio(value: str) -> float:
    letters = [c for c in value if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def _kind_from_title(title: str) -> str:
    """Return the instrument's terminal legal form, not a subject reference.

    ``Constitution (Second Amendment) Order, 1979`` is an Order, while a plain
    ``Constitution of Pakistan`` is a constitution.  Taking the first legal
    noun misclassified every constitutional amendment instrument.
    """
    terminal = TERMINAL_KIND.search(SPACE.sub(" ", title).strip())
    match = terminal or KIND.search(title)
    value = (match.group(1) if match else "unknown").lower().replace(".", "").replace(" ", "")
    return {"rule": "rules", "rules": "rules",
            "regulations": "regulation"}.get(value, value)


def _candidate_line(text: str) -> str | None:
    for raw in text.splitlines() or [text]:
        line = SPACE.sub(" ", raw).strip(" -–—\t")
        if not 12 <= len(line) <= 320 or not KIND.search(line):
            continue
        # An identity line supports the preceding title; by itself it is not
        # a second title/boundary (for example ``ACT IX OF 1974``).
        if IDENTITY.fullmatch(line) or IDENTITY_LINE.fullmatch(line):
            continue
        if re.fullmatch(
            r"\(?\s*\d*\[?[A-Z ]+\]?\s+(?:ACT|ORDINANCE|REGULATION)\s+"
            r"NO\.?\s*(?:[IVXLCDM]+|\d{1,3})\s+OF\s+\d{4}\s*\)?\.?",
            line, re.I):
            continue
        if len(KIND.findall(line)) > 1:
            continue
        if line.rstrip().endswith("&"):
            continue
        if DOT_LEADER.search(line) or FOOTNOTE.search(line):
            continue
        # A bare cross-reference is not a title.  Legal titles normally have
        # at least three alphabetic words and either title-like casing or a
        # year/notification marker.
        words = re.findall(r"[A-Za-z]{2,}", line)
        if len(words) < 3:
            continue
        title_form = re.sub(r"^\s*(?:\d+(?:\.\d+)*\s+|\d+(?=[A-Z]))", "", line)
        notification = re.search(r"^(?:GOVERNMENT\s+OF\s+\S+\s+)?(?:NOTIFICATION|S\.?\s*R\.?\s*O)", title_form, re.I)
        years = list(YEAR.finditer(line))
        if not years and not notification:
            continue
        if years and len(line) - years[-1].end() > 45:
            continue
        if re.match(r"^\d+[A-Z]?\.\s+", line) and len(line) > 180:
            continue
        if _uppercase_ratio(title_form) < 0.45 and not re.match(r"^(?:THE\s+)?(?:[A-Z][\w'()-]+\s+){2,}", title_form):
            continue
        # Compilation item numbers (``33.1 The ... Act``) locate the source;
        # they are not part of the instrument's legal short title.
        return re.sub(r"^\s*\d+(?:\.\d+)+\s+", "", line)
    return None


def detect(blocks: list[dict], outer_title: str | None = None,
           body_starts_page: int | None = None) -> list[Proposal]:
    """Return conservative internal-boundary proposals for one document."""
    title_rows: list[tuple[int, str]] = []
    for index, block in enumerate(blocks):
        line = _candidate_line(block["text"] or "")
        if line:
            title_rows.append((index, line))
    frequencies = Counter(_normalise(line) for _, line in title_rows)

    proposals: list[Proposal] = []
    accepted_titles: set[str] = set()
    for index, title in title_rows:
        block = blocks[index]
        page = int(block["page_no"])
        # A compilation-level contents parser can place ``body_starts_page``
        # after its first embedded instrument (PEF was measured as page 10 even
        # though independently self-naming Rules begin on page 6).  The legal
        # formula + section/rule-1 reset below is the boundary proof; an outer
        # TOC estimate must never veto it.
        if page <= 1 or (page <= 2 and not COMPILATION_TITLE.search(outer_title or "")):
            continue
        norm_title = _normalise(title)
        if (not COMPILATION_TITLE.search(outer_title or "")
                and _same_title(title, outer_title)):
            continue
        # A line repeated three or more times is almost always a running
        # header.  It can still be a boundary once, but only with both an
        # enactment formula and a numbered reset immediately following it.
        window = blocks[index:min(len(blocks), index + 10)]
        context = "\n".join((row["text"] or "") for row in window)
        identity_at = next((n for n, row in enumerate(window)
                            if IDENTITY.search(row["text"] or "")), None)
        formula_at = next((n for n, row in enumerate(window)
                           if FORMULA.search(row["text"] or "")), None)
        reset_at = next((n for n, row in enumerate(window)
                         if RESET.search(row["text"] or "")), None)
        identity = IDENTITY.search(context)
        formula = FORMULA.search(context)
        reset = RESET.search(context)
        self_named = CALLED_TITLE.search(context)
        following_rule_two = re.search(r"(?:^|\n)\s*2\s*[.()\-â€”:]",context,re.I)
        compilation_omitted_formula = bool(
            COMPILATION_TITLE.search(outer_title or "")
            and re.match(r"^\s*\d{1,2}\.\d{1,2}\s+",block["text"] or "")
            and reset and self_named and following_rule_two)
        repeated_header = frequencies[norm_title] >= 3
        if repeated_header and not (formula and reset):
            continue
        if norm_title in accepted_titles:
            continue
        accepted_titles.add(norm_title)

        score = 0.25
        rules = ["instrument_title_or_notification_marker"]
        if _uppercase_ratio(title) >= 0.72:
            score += 0.10
            rules.append("title_case_geometry")
        if identity:
            score += 0.20
            rules.append("nearby_act_or_ordinance_identity")
        if formula:
            score += 0.25
            rules.append("nearby_enactment_or_delegated_power_formula")
        if reset:
            score += 0.15
            rules.append("nearby_section_or_rule_one_reset")
        if compilation_omitted_formula:
            score += 0.35
            rules.append("compilation_title_self_name_and_rule_two_sequence")
        prior_citable = sum(bool(row.get("citable_start")) for row in blocks[:index])
        if prior_citable >= 2:
            score += 0.05
            rules.append("substantive_material_precedes_marker")
        if repeated_header:
            score -= 0.05
            rules.append("repeated_title_retained_only_with_dual_proof")
        score = min(1.0, max(0.0, score))
        # An internal instrument is a new legal-form sequence, not merely a
        # title/citation near the outer instrument's own opening formula.
        ordered_legal_form = ((formula_at is not None and reset_at is not None
                               and formula_at <= 7
                               and formula_at <= reset_at <= formula_at + 4)
                              or compilation_omitted_formula)
        prior_required = 0 if COMPILATION_TITLE.search(outer_title or "") else 2
        if score < 0.75 or not ordered_legal_form or prior_citable < prior_required:
            continue

        kind = _kind_from_title(title)
        year_match = YEAR.search(title) or (YEAR.search(identity.group(0)) if identity else None)
        number = identity.group(1) if identity else None
        support = []
        for row in window:
            t = row["text"] or ""
            if row is block or IDENTITY.search(t) or FORMULA.search(t) or RESET.search(t):
                support.append({
                    "block_id": row["id"],
                    "page": row["page_no"],
                    "sha256": hashlib.sha256(t.encode("utf-8")).hexdigest(),
                    "preview": SPACE.sub(" ", t).strip()[:240],
                })
        proposals.append(Proposal(
            block_id=block["id"], page=page, title=title, kind=kind,
            year=int(year_match.group(1)) if year_match else None,
            number=number, confidence=round(score, 4),
            evidence={
                "rules": rules,
                "formula_block_distance": formula_at,
                "reset_block_distance": reset_at,
                "title_frequency": frequencies[norm_title],
                "supporting_blocks": support,
                "window_end_block_id": window[-1]["id"],
                "window_end_page": window[-1]["page_no"],
            },
        ))
    # A few enacted schedules omit a stand-alone printed title but contain a
    # fresh long-title/Bill marker followed by an enactment formula and a
    # self-naming section 1.  Detect that independent sequence directly.
    covered_formula_blocks = {
        support["block_id"]
        for proposal in proposals
        for support in proposal.evidence["supporting_blocks"]
        if FORMULA.search(next((b["text"] for b in blocks
                                if b["id"] == support["block_id"]), ""))
    }
    for formula_index, formula_block in enumerate(blocks):
        formula_text = formula_block["text"] or ""
        if not FORMULA.search(formula_text) or formula_block["id"] in covered_formula_blocks:
            continue
        # Layout extraction may split the formula, ``1. Short title`` marginal
        # heading and the self-name across several blocks.  Eight blocks is
        # still local on this corpus, while four missed formally enacted items
        # in Estacode and the FPSC Ordinance appendix.
        reset_index = next((j for j in range(formula_index, min(len(blocks), formula_index + 9))
                            if (RESET.search(blocks[j]["text"] or "")
                                or RESET_HEADING.search(blocks[j]["text"] or ""))), None)
        if reset_index is None:
            continue
        called_end = min(len(blocks), reset_index + 4)
        reset_text = "\n".join((blocks[j]["text"] or "")
                               for j in range(reset_index, called_end))
        called = CALLED_TITLE.search(reset_text)
        if (not called
                or (not COMPILATION_TITLE.search(outer_title or "")
                    and _same_title(called.group(1), outer_title))):
            continue
        prior_citable = sum(bool(row.get("citable_start")) for row in blocks[:formula_index])
        page = int(formula_block["page_no"])
        prior_required = 0 if COMPILATION_TITLE.search(outer_title or "") else 2
        if (prior_citable < prior_required or page <= 1
                or (page <= 2 and not COMPILATION_TITLE.search(outer_title or ""))):
            continue
        marker_index = next((j for j in range(formula_index - 1, max(-1, formula_index - 5), -1)
                             if re.search(r"\b(?:AN?\s+ACT|AN?\s+BILL|AN?\s+ORDINANCE)\b",
                                          blocks[j]["text"] or "", re.I)), formula_index)
        start = blocks[marker_index]
        title = SPACE.sub(" ", called.group(1)).strip(" \"'‘’")
        year_match = YEAR.search(title)
        support_rows = blocks[marker_index:called_end]
        proposals.append(Proposal(
            block_id=start["id"], page=start["page_no"], title=title,
            kind=_kind_from_title(title),
            year=int(year_match.group(1)) if year_match else None,
            number=None, confidence=0.85,
            evidence={
                "rules": ["enactment_formula", "section_one_self_names_instrument",
                          "substantive_material_precedes_marker"],
                "title_frequency": 1,
                "formula_block_distance": formula_index - marker_index,
                "reset_block_distance": reset_index - marker_index,
                "supporting_blocks": [{
                    "block_id": row["id"], "page": row["page_no"],
                    "sha256": hashlib.sha256((row["text"] or "").encode("utf-8")).hexdigest(),
                    "preview": SPACE.sub(" ", row["text"] or "").strip()[:240],
                } for row in support_rows],
                "window_end_block_id": blocks[reset_index]["id"],
                "window_end_page": blocks[reset_index]["page_no"],
            },
        ))

    # Official compilations sometimes omit the gazette notification/formula
    # while printing the complete Rules from their numbered editorial heading.
    # A numbered title followed by Rule 1 self-naming the same instrument and
    # Rule 2 is still direct source evidence; a bare citation cannot satisfy
    # this three-part sequence.
    if COMPILATION_TITLE.search(outer_title or ""):
        for index,block in enumerate(blocks):
            raw = block["text"] or ""
            if not re.match(r"^\s*\d{1,2}\.\d{1,2}\s+",raw):
                continue
            title = _candidate_line(raw)
            if not title:
                continue
            window = blocks[index:min(len(blocks),index+7)]
            context = "\n".join(row["text"] or "" for row in window)
            reset = RESET.search(context)
            called = CALLED_TITLE.search(context)
            rule_two = re.search(r"(?:^|\n)\s*2\s*[.()\-â€”:]",context,re.I)
            if not (reset and called and rule_two):
                continue
            if not _same_title(title,called.group(1)):
                continue
            if any(p.block_id == block["id"] or _same_title(p.title,title)
                   for p in proposals):
                continue
            called_title = SPACE.sub(" ",called.group(1)).strip(" \"'‘’")
            year_match = YEAR.search(called_title)
            proposals.append(Proposal(
                block_id=block["id"],page=block["page_no"],title=called_title,
                kind=_kind_from_title(called_title),
                year=int(year_match.group(1)) if year_match else None,
                number=None,confidence=0.85,
                evidence={
                    "rules":["numbered_compilation_title","rule_one_self_names_instrument",
                             "rule_two_sequence","source_formula_omitted_by_compilation"],
                    "title_frequency":1,"formula_block_distance":None,
                    "reset_block_distance":next(
                        n for n,row in enumerate(window)
                        if RESET.search(row["text"] or "")),
                    "supporting_blocks":[{
                        "block_id":row["id"],"page":row["page_no"],
                        "sha256":hashlib.sha256((row["text"] or "").encode("utf-8")).hexdigest(),
                        "preview":SPACE.sub(" ",row["text"] or "").strip()[:240],
                    } for row in window if (row is block or RESET.search(row["text"] or "")
                                             or CALLED_TITLE.search(row["text"] or "")
                                             or re.search(r"(?:^|\n)\s*2\s*[.()\-â€”:]",
                                                          row["text"] or ""))],
                    "window_end_block_id":window[-1]["id"],
                    "window_end_page":window[-1]["page_no"],
                }))

    # Several blocks can point to the same downstream formula/reset. Prefer the
    # section-1 self-name because it is the instrument's own identity claim,
    # not a nearby reference. Shared support blocks, rather than page proximity,
    # define one signal so adjacent short instruments are never collapsed.
    collapsed: list[Proposal] = []
    for proposal in proposals:
        support = {row["block_id"] for row in proposal.evidence["supporting_blocks"]}
        overlapping = [
            i for i, old in enumerate(collapsed)
            if support & {row["block_id"] for row in old.evidence["supporting_blocks"]}
            and any(FORMULA.search(next((b["text"] for b in blocks if b["id"] == bid), ""))
                    for bid in support & {row["block_id"] for row in old.evidence["supporting_blocks"]})
        ]
        if not overlapping:
            collapsed.append(proposal)
            continue
        index = overlapping[-1]
        old = collapsed[index]
        proposal_self_named = "section_one_self_names_instrument" in proposal.evidence["rules"]
        old_self_named = "section_one_self_names_instrument" in old.evidence["rules"]
        if (proposal_self_named, proposal.confidence, len(proposal.title)) > (
                old_self_named, old.confidence, len(old.title)):
            collapsed[index] = proposal
    return collapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--document", type=int)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument("--summary-only", action="store_true",
                        help="print counts only; evidence is unchanged")
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        document_filter = "" if args.document is None else "AND i.document_id=%s"
        params = () if args.document is None else (args.document,)
        cur.execute(f"""
            SELECT i.id::text,i.source_observation_id,i.document_id,i.short_title,
                   run.body_starts_page,
                   b.id,b.page_no,b.reading_order,b.text,
                   EXISTS (SELECT 1 FROM provision p WHERE p.instrument_id=i.id
                            AND p.first_block=b.id AND p.kind IN
                                ('section','article')) AS citable_start
              FROM instrument i
              JOIN text_block source_start ON source_start.id=i.source_start_block_id
              JOIN text_block source_end ON source_end.id=i.source_end_block_id
              JOIN text_block b ON b.document_id=i.document_id
                               AND b.reading_order BETWEEN source_start.reading_order
                                                       AND source_end.reading_order
              LEFT JOIN LATERAL (
                    SELECT r.body_starts_page FROM segmentation_run r
                     WHERE r.instrument_id=i.id
                     ORDER BY r.run_at DESC,r.id DESC LIMIT 1
              ) run ON true
             WHERE i.is_active AND i.duplicate_of IS NULL
               {document_filter}
             ORDER BY i.document_id,b.reading_order
        """, params)
        documents: dict[tuple, list[dict]] = {}
        for iid, oid, did, outer_title, body_page, bid, page, order, value, citable_start in cur.fetchall():
            key = (iid, oid, did, outer_title, body_page)
            documents.setdefault(key, []).append({
                "id": bid, "page_no": page, "reading_order": order,
                "text": value or "", "citable_start": citable_start,
            })

        rows: list[tuple] = []
        report: list[dict] = []
        for (iid, oid, did, outer_title, body_page), blocks in documents.items():
            for proposal in detect(blocks, outer_title, body_page):
                if proposal.confidence < args.min_confidence:
                    continue
                evidence = dict(proposal.evidence)
                evidence["outer_instrument_title"] = outer_title
                rows.append((iid, oid, did, proposal.block_id, proposal.page,
                             proposal.title, proposal.kind, proposal.year,
                             proposal.number, proposal.confidence, METHOD,
                             json.dumps(evidence, ensure_ascii=False)))
                report.append({
                    "document_id": did, "source_observation_id": oid,
                    "outer_title": outer_title, "source_page": proposal.page,
                    "start_block_id": proposal.block_id,
                    "detected_title": proposal.title,
                    "confidence": proposal.confidence,
                    "rules": proposal.evidence["rules"],
                })

        if args.apply and rows:
            cur.executemany("""
                INSERT INTO segmentation_boundary_candidate
                    (instrument_id,source_observation_id,document_id,start_block_id,
                     source_page,detected_title,detected_kind,detected_year,
                     detected_number,confidence,method,evidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING
            """, rows)

    print(json.dumps({
        "method": METHOD, "documents_scanned": len(documents),
        "proposals": len(report), "documents_with_proposals": len({r['document_id'] for r in report}),
        "applied": args.apply, "items": [] if args.summary_only else report,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
