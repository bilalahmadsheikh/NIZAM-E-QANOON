"""Build the page-read readings for D-083 (18 Nov 2026):

AJK Antiquities Act 1986 (doc 10935): its sections print their headings inline, bold and underlined, closed by '.-'
('5. Custody, preservation, etc. of certain antiquities.- (1) where ...'). Under unreleased-v4 most are split; eight are
not (the split stops at the abbreviation 'etc.' or at an amendment marker '4[Director General]') and s.4's is lost.
Those take rule reviewed_heading_line; ss.15 and 22, whose v4 heading keeps a line break, take the printed heading
whole. Pages read: 4, 6, 9, 12, 13, 14, 18.

Sindh Cultural Heritage (Preservation) Act 1994 (doc 1336): the second running-head line 'THE SINDH CULTURAL
HERITAGE (PERSERVATION) ACT, 1994' heads pages 3-8. Alone in its block on pp3 and 8 it is set aside; fused with the
law below on pp4-7 it is cut and the law kept. s.22's margin note 'Protection to the Person; acting under this Act.'
is a block of its own read into the text: set aside (the contents give s.22 the same words as its heading). Pages
read: 3-8."""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
R = '.artifacts/release-work-2026-09-24/claude/renders'
EXPORT = '.artifacts/decision-review/exports/decision-review-2026-11-18-delegated-10935.json'


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- AJK 10935
HEAD_LINES = [  # (label, page, opener block, heading as printed, without its closing '.-')
    ('4', 4, 2814853, 'Dispute as to whether any product, etc. is an antiquity.'),
    ('5', 4, 2814854, 'Custody, preservation, etc. of certain antiquities'),
    ('6', 4, 2814856, 'Accidental discovery of antiquity to be reported to 4[Director General]'),
    ('9', 6, 2814878, 'Purchase, taking lease, etc. of antiquity'),
    ('20', 12, 2814953, 'Prohibition of destruction, damage etc. of protected antiquities'),
    ('21', 12, 2814956, 'Restriction on repairs, renovation, etc. of protected immovable antiquity'),
    ('25', 14, 2814974, 'Penalty for counterfeiting etc. of antiquity'),
    ('36', 18, 2815023, 'Confiscated antiquities to be made over to 2[Director General]'),
]
WHOLE = [  # (label, page, opener block, heading) -- v4's heading keeps a line break; the printed words, whole
    ('15', 9, 2814919, 'Application of endowment for maintenance and preservation of antiquity'),
    ('22', 13, 2814962, 'Direction to the owner to take measures for preservation of antiquity'),
]
card = {'document_id': 10935, 'question_id': 'q1',
        'question': ('The AJK Antiquities Act 1986 (doc 10935) prints each heading inline, bold and underlined, closed '
                     'by ".-". Ten sections are left without it or with a line break inside it. Which heading does each '
                     'take?'),
        'options': ['printed: the bold heading as printed, without its closing ".-"', 'none: leave them headingless'],
        'recommended': 'printed'}
card['card_sha256'] = hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
pages = sorted({p for _l, p, _b, _h in HEAD_LINES + WHOLE})
(ROOT / EXPORT).write_text(json.dumps({
    'schema': 'nizam.decision_review.v1',
    'reviewer_name': 'lead under owner chat delegation (standing since 25 Oct 2026)', 'source': 'chat-delegation',
    'chat_quote': ("release fast what u can release making the decisons for me in that numbering the question u ask "
                   "me and choose the recommended choice in it without asking me not also don't choose keep it "
                   "unreleased or release only specific part"),
    'exported_at': '2026-11-18T18:00:00+00:00', 'answer_count': 1,
    'answers': [{'document_id': 10935, 'question_id': 'q1', 'card': card, 'card_sha256': card['card_sha256'],
                 'choice': 'printed', 'reviewed_page_images': True,
                 'note': f'The lead read pages {pages}: each heading is bold, underlined and closed by ".-".',
                 'renders': {str(p): {'path': f'{R}/doc10935-p{p}.png', 'sha256': sha(f'{R}/doc10935-p{p}.png')}
                             for p in pages}}]}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
od = {'export': EXPORT, 'document_id': 10935, 'question_id': 'q1'}
ajk = []
for p in pages:
    lines = [{'label': l, 'source_block_id': b, 'heading': h, 'owner_decision': od}
             for l, pg, b, h in HEAD_LINES if pg == p]
    whole = [{'label': l, 'source_block_id': b, 'heading': h, 'use': 'heading', 'owner_decision': od}
             for l, pg, b, h in WHOLE if pg == p]
    first = (lines or whole)[0]['heading'][:30]
    r = {'document_id': 10935, 'page_no': p, 'match_text': first, 'before_text': first, 'after_text': first,
         'defect': 'printed inline headings left in the text (or broken by a line break) instead of heading the section',
         'fixes': 'rules reviewed_heading_line (heading closed by its ".-", D-083) and printed_heading_override',
         'observed': 'Page %d prints, bold and underlined: %s.' % (
             p, '; '.join(f"s.{x['label']} '{x['heading']}'" for x in lines + whole)),
         'render': f'{R}/doc10935-p{p}.png', 'render_sha256': sha(f'{R}/doc10935-p{p}.png')}
    if lines:
        r['source_heading_lines'] = lines
    if whole:
        r['source_printed_headings'] = whole
    ajk.append(r)

# ---------------------------------------------------------------- Sindh 1336
TITLE = 'THE SINDH CULTURAL HERITAGE (PERSERVATION) ACT, 1994'
DEF = ("the Sindh Code's running head (the law's title under its citation at the head of each page) read into a "
       "provision's text")
sindh = []
for p, block in ((3, 74257), (8, 74325)):
    sindh.append({'document_id': 1336, 'page_no': p, 'match_text': TITLE, 'before_text': TITLE, 'after_text': TITLE,
                  'source_apparatus_blocks': [block] + ([74339] if p == 8 else []),
                  'defect': DEF + (" and s.22's margin note read into its text" if p == 8 else ''),
                  'fixes': 'rule reviewed_apparatus_block: the running-head block' +
                           (" and s.22's margin-note block are" if p == 8 else ' is') + ' set aside',
                  'observed': (f"Page {p} prints the running head 'SINDH ACT No.XII OF 1994 / {TITLE}' at its head"
                               + ("; and beside s.22 the margin note 'Protection to the Person; acting under this "
                                  "Act.', which the contents give s.22 as its heading" if p == 8 else '')),
                  'render': f'{R}/doc1336-p{p}.png', 'render_sha256': sha(f'{R}/doc1336-p{p}.png')})
for p in (4, 5, 6, 7):
    sindh.append({'document_id': 1336, 'page_no': p, 'match_text': TITLE, 'before_text': TITLE, 'after_text': ' ',
                  'defect': DEF + ', in the same block as the law below it',
                  'fixes': 'parser-input correction: the running-head line is cut from the block; the law after it is '
                           'kept as printed',
                  'observed': f"Page {p} prints the running head 'SINDH ACT No.XII OF 1994 / {TITLE}' at its head; the "
                              "same head opens the document's other pages",
                  'render': f'{R}/doc1336-p{p}.png', 'render_sha256': sha(f'{R}/doc1336-p{p}.png')})

for name, rs in (('patch-10935h.json', ajk), ('patch-1336r.json', sindh)):
    (HERE / name).write_text(json.dumps(rs, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(name, len(rs), 'reading(s)')
