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

  test('a division is named by its noun, label and printed title, never repeating the noun', () {
    expect(divisionTitle('constitution', 'part', 'II', 'FUNDAMENTAL RIGHTS AND PRINCIPLES OF POLICY'),
        'Part II — Fundamental Rights and Principles of Policy');
    expect(divisionTitle('constitution', 'annexure', 'ANNEX', null), 'Annex');
    expect(divisionTitle('constitution', 'schedule', 'FIRST SCHEDULE', null), 'First Schedule');
    expect(divisionTitle('act', 'chapter', '1', null), 'Chapter 1');
  });
}
