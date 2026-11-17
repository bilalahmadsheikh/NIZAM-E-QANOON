import 'package:flutter_test/flutter_test.dart';
import 'package:nizam_app/domain/law_units.dart';

void main() {
  test('a constitution numbers Articles; other laws keep the stored kind', () {
    expect(unitNoun('constitution', 'section'), 'Article');
    expect(unitNoun('act', 'section'), 'Section');
    expect(unitNoun('constitution', 'annexure'), 'Annex');
    expect(unitsNoun('constitution', 339), 'articles');
    expect(unitsNoun('act', 1), 'section');
  });

  test('a caption printed in capitals reads in title case; one with lower case is left as printed', () {
    expect(captionCase('FUNDAMENTAL RIGHTS AND PRINCIPLES OF POLICY'), 'Fundamental Rights and Principles of Policy');
    expect(captionCase('THE FEDERATION OF PAKISTAN'), 'The Federation of Pakistan');
    expect(captionCase('FINANCE, PROPERTY, CONTRACTS AND SUITS'), 'Finance, Property, Contracts and Suits');
    expect(captionCase('Of Abetment'), 'Of Abetment');
    expect(captionCase('PART XII'), 'Part XII');
  });

  test('a preamble reads as its printed recitals, every word kept, the printed head not repeated', () {
    const constitution = 'PREAMBLE WHEREAS sovereignty over the entire Universe belongs to Almighty Allah alone, and the '
        'authority to be exercised by the people of Pakistan within the limits prescribed by Him is a sacred trust; '
        'AND WHEREAS it is the will of the people of Pakistan to establish an order__ WHEREIN the State shall '
        'exercise its powers; WHEREIN the independence of the judiciary shall be fully secured; NOW, THEREFORE, we, '
        'the people of Pakistan, Conscious of our responsibility before Almighty Allah and men; Do hereby, through '
        'our representatives in the National Assembly, adopt, enact and give to ourselves, this Constitution.';
    final paras = preambleParagraphs(constitution);
    expect(paras.first, startsWith('WHEREAS sovereignty'));
    expect(paras.map((p) => p.split(' ').first).toList(),
        ['WHEREAS', 'AND', 'WHEREIN', 'WHEREIN', 'NOW,', 'Conscious', 'Do']);
    // every word but the printed head is kept, in order
    expect(paras.join(' ').replaceAll(RegExp(r'\s+'), ' '), constitution.substring('PREAMBLE '.length));
    // an ordinary Act: the recital, then the enacting words
    expect(preambleParagraphs('WHEREAS it is expedient to amend the Act; It is hereby enacted as follows:—'),
        ['WHEREAS it is expedient to amend the Act;', 'It is hereby enacted as follows:—']);
    // 'whereas' inside a sentence is not a recital
    expect(preambleParagraphs('WHEREAS the Board, whereas the Rules apply, shall act;').length, 1);
  });

  test('a division is named by its noun, label and printed title, never repeating the noun', () {
    expect(divisionTitle('constitution', 'part', 'II', 'FUNDAMENTAL RIGHTS AND PRINCIPLES OF POLICY'),
        'Part II — Fundamental Rights and Principles of Policy');
    expect(divisionTitle('constitution', 'annexure', 'ANNEX', null), 'Annex');
    expect(divisionTitle('constitution', 'schedule', 'FIRST SCHEDULE', null), 'First Schedule');
    expect(divisionTitle('act', 'chapter', '1', null), 'Chapter 1');
  });
}
