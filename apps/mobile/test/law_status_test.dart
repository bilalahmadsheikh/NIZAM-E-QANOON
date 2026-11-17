import 'package:flutter_test/flutter_test.dart';
import 'package:nizam_app/domain/law_status.dart';

void main() {
  test('a presumed law is never worded as verified', () {
    final w = lawStatusWording(currency: 'current', reason: 'owner_presumption_in_force');
    expect(w.standing, Standing.presumed);
    expect(w.title, 'Treated as in force');
    expect(w.title.startsWith('In force'), isFalse);
  });

  test('established commencement says when', () {
    final w = lawStatusWording(
        currency: 'current', reason: 'commenced_on_established', commencedOn: '2022-03-01');
    expect(w.standing, Standing.inForce);
    expect(w.detail, contains('2022-03-01'));
  });

  test('a lapsed Ordinance and a dated repeal are not law, with their dates', () {
    expect(
      lawStatusWording(currency: 'not_current', reason: 'ordinance_lapsed', notCurrentFrom: '2002-11-15').detail,
      contains('2002-11-15'),
    );
    final r = lawStatusWording(currency: 'not_current', reason: 'repealed', repealedOn: '2016-08-22');
    expect(r.standing, Standing.notLaw);
    expect(r.detail, 'Repealed with effect from 2016-08-22.');
  });

  test('a repealed unit is an outcome with a way back to its earlier text', () {
    final s = notServedWording('unit_repealed', from: '2016-01-01', asOf: '2026-11-17');
    expect(s, contains('2016-01-01'));
    expect(s, contains('earlier date'));
  });

  test('a law outside the territory names the territory, not an error', () {
    expect(notServedWording('law_does_not_run_in_territory', asOf: '2026-11-17', territory: 'sindh'),
        'This law does not apply in Sindh.');
  });

  test('printed labels follow the statute', () {
    expect(printedLabel('subsection', '1'), '(1)');
    expect(printedLabel('clause', 'a'), '(a)');
    expect(printedLabel('clause', '(xix)'), '(xix)');
    expect(printedLabel('section', '302'), '302.');
    expect(printedLabel('proviso', 'Provided'), 'Provided');
    expect(printedLabel('section', null), '');
  });
}
