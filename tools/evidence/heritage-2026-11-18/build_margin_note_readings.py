"""Build the page-read readings that give the Balochistan Cultural Heritage Preservation Act 2010 (doc 4788), the
Balochistan Antiquities Act 2014 (doc 4986), the Khyber Pakhtunkhwa Antiquities Act 2016 (doc 5133) s.10 and the Sindh
Cultural Heritage Act 1994 (doc 1336) s.8 their printed margin headings (D-080).

Every pairing below was read from the page renders on 18 Nov 2026:
  4788: pp1-5, 7-10. The notes sit in a table's left column, in the row of the section they name.
  4986: pp4, 8, 10, 11, 16. Margin notes beside each section; s.20's and s.24's run across a page break.
  5133: p11. '2[10. Accidental discovery of antiquity to be reported to the Director.---(1) Whoever ...'.
  1336: p4. The note beside s.8 heads the block that also holds s.8(2)'s first words.
Headings are joined from the blocks' own text, so a heading is exactly what the blocks print."""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from nizam.storage.db import connect  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
RENDERS = '.artifacts/release-work-2026-09-24/claude/renders'
EXPORT = '.artifacts/decision-review/exports/decision-review-2026-11-18-delegated-5133.json'

# doc 4788: (label, opener block, [margin piece blocks]) -- pieces set aside as apparatus, joined as the heading
D4788_PIECES = [
    ('1', 987085, [987086, 987088, 987090]), ('3', 987119, [987120, 987122]),
    ('4', 987141, [987142, 987144, 987146, 987148, 987150]), ('5', 987151, [987152, 987154, 987156]),
    ('6', 987162, [987163, 987165, 987167]), ('7', 987184, [987185, 987187, 987189, 987191, 987193, 987194]),
    ('8', 987210, [987211, 987213, 987215, 987217]), ('9', 987257, [987258, 987260]),
    ('10', 987283, [987284, 987286, 987288, 987290, 987292, 987294]),
    ('11', 987304, [987305, 987307, 987309, 987311]), ('12', 987318, [987319, 987321, 987323]),
    ('13', 987335, [987336, 987338, 987340, 987342, 987344]), ('14', 987349, [987350, 987352, 987354, 987356]),
    ('16', 987368, [987369, 987371]),
]
# doc 4788: notes the text layer set at the head of the section's own block
D4788_LEADING = [('2', 987094, 'Definitions.'), ('15', 987361, 'Penalty.'), ('17', 987373, 'Rules'),
                 ('18', 987375, 'Indemnity.')]
# doc 4986: the sections the profile's margin rule leaves without their note (unreleased-v4 gives the other 37)
D4986_PIECES = [('4', 1009762, [1009763]), ('14', 1009811, [1009812]), ('24', 1009858, [1009859, 1009861]),
                ('41', 1009928, [1009929])]
# s.20: 'Restriction on' heads the law block (lifted), 'use of protected immovable antiquity.' is a margin block
D4986_S20 = ('20', 1009843, 'Restriction on', [1009845])


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def norm(s):
    return ' '.join((s or '').split())


with connect() as conn, conn.cursor() as cur:
    ids = [b for _l, o, ps in D4788_PIECES + D4986_PIECES for b in [o, *ps]] + \
          [b for _l, b, _n in D4788_LEADING] + [D4986_S20[1], *D4986_S20[3]]
    cur.execute('SELECT id, page_no, text FROM text_block WHERE id = ANY(%s)', (ids,))
    blocks = {i: (p, t) for i, p, t in cur.fetchall()}


def first_line(block):
    # the recorder locates a reading by a line of 12+ characters printed in a block on its page
    lines = [l.strip() for l in blocks[block][1].split('\n') if l.strip()]
    return next((l for l in lines if len(l) >= 12), ' '.join(lines))[:40]


def readings(doc, pieces, leading, s20=None):
    by_page = {}

    def page_of(page, locator):
        return by_page.setdefault(page, {'apparatus': [], 'pieces': [], 'leading': [], 'locator': locator})

    def aside(ps):
        # an apparatus block is named by the reading for its own page (a note across a page break: two readings)
        for b in ps:
            page_of(blocks[b][0], b)['apparatus'].append(b)
    for label, opener, ps in pieces:
        page_of(blocks[opener][0], opener)  # the law block locates the page's reading, before its margin pieces
        aside(ps)
        page_of(blocks[opener][0], opener)['pieces'].append(
            {'label': label, 'target_block_id': opener, 'source_block_ids': ps,
             'heading': norm(' '.join(blocks[b][1] for b in ps))})
    for label, block, note in leading:
        page_of(blocks[block][0], block)['leading'].append({'block_id': block, 'note': note, 'label': label})
    if s20:
        label, block, note, ps = s20
        r = page_of(blocks[block][0], block)
        r['leading'].append({'block_id': block, 'note': note, 'label': label})
        r['pieces'].append({'label': label, 'target_block_id': block, 'source_block_ids': [block, *ps],
                            'heading': norm(note + ' ' + ' '.join(blocks[b][1] for b in ps))})
        aside(ps)
    out = []
    # a page whose law blocks open alike ('Notwithstanding anything contained in any other law', 4986 ss.14 and 15)
    # is located by its note block instead
    unique = {(4986, 8): 1009812}
    for page, r in sorted(by_page.items()):
        render = f'{RENDERS}/doc{doc}-p{page}.png'
        loc = first_line(unique.get((doc, page), r['locator']))
        names = '; '.join([f"s.{p['label']} '{p['heading']}'" for p in r['pieces']]
                          + [f"s.{x['label']} '{x['note']}'" for x in r['leading']]
                          + ([f"the rest of a note begun on the page before ({', '.join(map(str, r['apparatus']))})"]
                             if r['apparatus'] and not r['pieces'] and not r['leading'] else []))
        reading = {
            'document_id': doc, 'page_no': page, 'match_text': loc, 'before_text': loc, 'after_text': loc,
            'defect': 'margin side notes read into the provision text, and the sections left without the heading '
                      'the page prints beside them',
            'fixes': 'rules reviewed_margin_note_pieces (pieces set aside as apparatus, joined as the heading) and '
                     'reviewed_leading_margin_note (a note heading the law block is lifted out of the text) (D-080)',
            'observed': f'Page {page} prints, in the margin beside each section: {names}. Read from the render.',
            'render': render, 'render_sha256': sha(render),
        }
        if r['apparatus']:
            reading['source_apparatus_blocks'] = sorted(set(r['apparatus']))
        if r['pieces']:
            reading['source_margin_note_pieces'] = r['pieces']
        if r['leading']:
            reading['source_leading_margin_notes'] = r['leading']
        out.append(reading)
    return out


r4788 = readings(4788, D4788_PIECES, D4788_LEADING)
r4986 = readings(4986, D4986_PIECES, [], D4986_S20)

# doc 5133 s.10 (KP Act XIV of 2022 substituted it): the '2[' before '10.' kept the body's bold heading in the text and
# the contents' 'Director.]' (with the Code's closing bracket) as the heading
card = {'document_id': 5133, 'question_id': 'q1',
        'question': ('KP Antiquities Act 2016 s.10 prints "2[10. Accidental discovery of antiquity to be reported to the '
                     'Director.---(1) Whoever ..." (p11, substituted by KP Act XIV of 2022). The stored heading is the '
                     'contents row "...to Director.]" with the Code\'s closing bracket, and the body heading stays in '
                     'the text. Which heading does s.10 take?'),
        'options': ['printed: the body\'s own heading, out of the text', 'contents: keep "...to Director.]"'],
        'recommended': 'printed'}
card['card_sha256'] = hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
p11 = f'{RENDERS}/doc5133-p11.png'
(ROOT / EXPORT).write_text(json.dumps({
    'schema': 'nizam.decision_review.v1',
    'reviewer_name': 'lead under owner chat delegation (standing since 25 Oct 2026)', 'source': 'chat-delegation',
    'chat_quote': ("release fast what u can release making the decisons for me in that numbering the question u ask "
                   "me and choose the recommended choice in it without asking me not also don't choose keep it "
                   "unreleased or release only specific part"),
    'exported_at': '2026-11-18T15:00:00+00:00', 'answer_count': 1,
    'answers': [{'document_id': 5133, 'question_id': 'q1', 'card': card, 'card_sha256': card['card_sha256'],
                 'choice': 'printed', 'reviewed_page_images': True,
                 'note': 'The lead read p11: the bold heading, then "---(1) Whoever"; the recommended option heads s.10 with it.',
                 'renders': {'11': {'path': p11, 'sha256': sha(p11)}}}]}, indent=1, ensure_ascii=False) + '\n',
    encoding='utf-8')
HEAD = 'Accidental discovery of antiquity to be reported to the Director.'
r5133 = [
    {'document_id': 5133, 'page_no': 11, 'match_text': 'the Director.---(1) Whoever',
     'before_text': 'the Director.---(1) Whoever', 'after_text': 'the Director.\n(1) Whoever',
     'defect': 'the bold heading of s.10 and its sub-section (1) are one line, so (1) did not open and the heading stayed text',
     'fixes': 'parser-input correction: the "---" separator the parser drops after every other heading becomes a line break',
     'observed': card['question'] + ' The page prints the heading in bold, then "---(1)".',
     'render': p11, 'render_sha256': sha(p11)},
    {'document_id': 5133, 'page_no': 11, 'match_text': 'Accidental discovery of antiquity to be',
     'before_text': 'Accidental discovery of antiquity to be', 'after_text': 'Accidental discovery of antiquity to be',
     'defect': 's.10 headed by the contents row with the Code\'s closing bracket; its printed heading in its text',
     'fixes': 'rule reviewed_heading_line: the printed heading leaves the text and becomes the heading',
     'observed': card['question'] + ' Read from the render of p11.',
     'render': p11, 'render_sha256': sha(p11),
     'source_heading_lines': [{'label': '10', 'source_block_id': 1039081, 'heading': HEAD,
                               'owner_decision': {'export': EXPORT, 'document_id': 5133, 'question_id': 'q1'}}]},
]

# doc 1336 s.8: the note lifted from the head of block 74276 (its printed heading reading, q2, names the same block)
p4 = '.artifacts/heritage-2026-11-18/renders/doc1336-p4.png'
r1336 = [{
    'document_id': 1336, 'page_no': 4, 'match_text': 'may accept the gift or bequest',
    'before_text': 'may accept the gift or bequest', 'after_text': 'may accept the gift or bequest',
    'defect': "s.8's margin note heads the block holding s.8(2)'s first words, so it closed s.8(1)'s text",
    'fixes': 'rule reviewed_leading_margin_note (D-080): the note leaves the text and marks s.8',
    'observed': ('Page 4 prints "Acquisition of right in / or guardianship of a / protected heritage / of the '
                 'government." in the margin beside s.8(1); the text layer set it at the head of the block that opens '
                 'with "(2) The Committee, may accept the gift or bequest". Read from the render.'),
    'render': p4, 'render_sha256': sha(p4),
    'source_leading_margin_notes': [{'block_id': 74276, 'label': '8',
                                     'note': 'Acquisition of right in or guardianship of a protected heritage of the government.'}],
}]

for name, rs in (('patch-4788n.json', r4788), ('patch-4986n.json', r4986), ('patch-5133h.json', r5133),
                 ('patch-1336n.json', r1336)):
    (HERE / name).write_text(json.dumps(rs, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(name, len(rs), 'reading(s)')
for r in r4788 + r4986:
    for p in r.get('source_margin_note_pieces', []):
        print(f"  {r['document_id']} p{r['page_no']} s.{p['label']}: {p['heading']}")
    for x in r.get('source_leading_margin_notes', []):
        print(f"  {r['document_id']} p{r['page_no']} s.{x['label']} (lifted): {x['note']}")
