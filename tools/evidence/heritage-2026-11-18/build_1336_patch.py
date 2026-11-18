"""Build the delegated owner decision and the curation reading for doc 1336 (Sindh Cultural Heritage (Preservation)
Act, 1994): its printed contents runs one row behind its body from row 7, because the body prints a bare '7.'
after s.6(1) (p3) and continues s.6's sub-sections (2)-(4) under it (p4). Each contents row is linked to the body
section whose own printed margin note it repeats. Read from the page renders on 18 Nov 2026 (p1, p3, p4, p8)."""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
EXPORT = '.artifacts/decision-review/exports/decision-review-2026-11-18-delegated-1336.json'
DOC = 1336


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


# stored contents ordinal -> (printed row label, the body section whose margin note prints the row's words)
# rows 1-6 sit beside their own sections; row 7 'Acquisition of right in or guardianship...' is printed in the
# margin at body s.8 (p4), row 9 'Owners under disability.' at s.10 (p6), row 21 'Protection to the Person...' at
# s.22 (p8). Rows 14 and 15 print only a rule ('_____'), as do body ss.15 and 16 (no margin note); they keep the
# one-behind order of their neighbours 13 -> s.14 'Maintenance' and 16 -> s.17 'Relinquishment'.
LINKS = [(0, '1', '1'), (1, '2', '2'), (2, '3', '3'), (3, '4', '4'), (4, '5', '5'), (5, '6', '6'),
         (6, '7', '8'), (7, '8', '9'), (8, '9', '10'), (9, '11', '12'), (10, '12', '13'), (11, '13', '14'),
         (12, '14', '15'), (13, '15', '16'), (14, '16', '17'), (15, '17', '18'), (16, '18', '19'),
         (17, '19', '20'), (18, '20', '21'), (19, '21', '22')]

card = {
    'document_id': DOC, 'question_id': 'q1',
    'question': ('Document 1336 (Sindh Cultural Heritage (Preservation) Act, 1994) prints its contents one row behind '
                 'its body from row 7: the body prints a bare "7." after s.6(1) and s.6(2)-(4) under it, so contents '
                 'row 7 is printed as the margin note of s.8 and row 21 as that of s.22. The stored tree heads every '
                 'section from s.8 with the contents row of its own number (s.19 "Overriding effect" over the '
                 'penalty). How are the contents rows linked?'),
    'options': ['body: link each row to the body section whose own printed margin note repeats it (rows 1-6 to '
                'ss.1-6, rows 7-21 to ss.8-22; s.7 and s.11 print no note and take no row)',
                'number: keep linking each row to the section of its own number'],
    'recommended': 'body',
}
card['card_sha256'] = hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
# q2: contents row 7 wraps onto a second line ('...of the / Government.') and the stored row kept only the first,
# so the aligned s.8 would be headed '...of a protected heritage of the'. The body's margin note (p4, block 74276)
# prints the whole heading.
card2 = {
    'document_id': DOC, 'question_id': 'q2',
    'question': ('Contents row 7 of document 1336 wraps onto a second line and its stored words stop at "...of a '
                 'protected heritage of the". Section 8 prints its margin note in full on p4: "Acquisition of right '
                 'in or guardianship of a protected heritage of the government." Which heading does s.8 take?'),
    'options': ['printed: the margin note as printed beside s.8 (block 74276)',
                'contents: the stored contents words, cut at "of the"'],
    'recommended': 'printed',
}
card2['card_sha256'] = hashlib.sha256(json.dumps(card2, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
S8_HEADING = 'Acquisition of right in or guardianship of a protected heritage of the government.'
renders = {p: f'.artifacts/heritage-2026-11-18/renders/doc1336-p{p}.png' for p in (1, 3, 4, 8)}
export = {
    'schema': 'nizam.decision_review.v1',
    'reviewer_name': 'lead under owner chat delegation (standing since 25 Oct 2026)',
    'source': 'chat-delegation',
    'chat_quote': ("release fast what u can release making the decisons for me in that numbering the question u ask "
                   "me and choose the recommended choice in it without asking me not also don't choose keep it "
                   "unreleased or release only specific part"),
    'exported_at': '2026-11-18T12:30:00+00:00',
    'answer_count': 1,
    'answers': [{
        'document_id': DOC, 'question_id': 'q1', 'card': card, 'card_sha256': card['card_sha256'],
        'choice': 'body', 'reviewed_page_images': True,
        'note': ('The lead read the renders of p1 (contents: 21 rows, row 10 blank, rows 14-15 a rule), p3 (s.6(1) '
                 'then a bare "7."), p4 (s.6(2)-(4); s.8 margin "Acquisition of right in or guardianship of a '
                 'protected heritage of the government."; s.9 margin "Preservation of protected heritage.") and p8 '
                 '(s.18 "Right of access to certain Protected heritage.", s.19 "Penalty.", s.20 "Overriding effect.", '
                 's.21 "Rules.", s.22 "Protection to the Person; acting under this Act."). The recommended option '
                 'links each row to the section printing its words.'),
        'renders': {str(p): {'path': r, 'sha256': sha(r)} for p, r in renders.items()},
    }, {
        'document_id': DOC, 'question_id': 'q2', 'card': card2, 'card_sha256': card2['card_sha256'],
        'choice': 'printed', 'reviewed_page_images': True,
        'note': ('The lead read p4: the margin beside s.8(1) prints "Acquisition of right in / or guardianship of a / '
                 'protected heritage / of the government." in four lines; the recommended option heads s.8 with it.'),
        'renders': {'4': {'path': renders[4], 'sha256': sha(renders[4])}},
    }],
}
export['answer_count'] = len(export['answers'])
(ROOT / EXPORT).write_text(json.dumps(export, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')

decision = {'export': EXPORT, 'document_id': DOC, 'question_id': 'q1'}
reading = {
    'document_id': DOC, 'page_no': 1,
    'match_text': 'Acquisition of right in or guardianship', 'before_text': 'Acquisition of right in or guardianship',
    'after_text': 'Acquisition of right in or guardianship',
    'defect': ('contents rows linked by number although the contents runs one row behind the body from row 7; every '
               'section from s.8 carries the heading of the section before it'),
    'fixes': ('rule reviewed_contents_alignment: each contents row is linked to the body section printing its words '
              'as a margin note (profile unreleased-v4, whose margin_heading_blocks also lifts those notes out of '
              'the text they were read into)'),
    'observed': card['question'] + ' ' + export['answers'][0]['note'],
    'render': renders[1], 'render_sha256': sha(renders[1]),
    'additional_render': renders[8], 'additional_render_sha256': sha(renders[8]),
    'source_contents_row_links': [{'ordinal': o, 'printed_label': p, 'unit_label': u, 'owner_decision': decision}
                                  for o, p, u in LINKS],
}
(HERE / 'patch-1336.json').write_text(json.dumps([reading], indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
reading2 = {
    'document_id': DOC, 'page_no': 4,
    'match_text': 'Acquisition of right in', 'before_text': 'Acquisition of right in', 'after_text': 'Acquisition of right in',
    'defect': 's.8 headed by contents row 7, whose stored words stop at "of the" (the row wraps onto a second line)',
    'fixes': 'rule printed_heading_override: s.8 takes the margin note printed beside it in full (block 74276)',
    'observed': card2['question'] + ' ' + export['answers'][1]['note'],
    'render': renders[4], 'render_sha256': sha(renders[4]),
    'source_printed_headings': [{'label': '8', 'source_block_id': 74276, 'heading': S8_HEADING, 'use': 'heading',
                                 'owner_decision': {'export': EXPORT, 'document_id': DOC, 'question_id': 'q2'}}],
}
(HERE / 'patch-1336-s8.json').write_text(json.dumps([reading2], indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
print('wrote', EXPORT, 'and', HERE / 'patch-1336.json', HERE / 'patch-1336-s8.json')
