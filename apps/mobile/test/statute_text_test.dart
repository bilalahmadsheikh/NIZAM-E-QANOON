import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nizam_app/presentation/statute_text.dart';

String spansText(List<InlineSpan> spans) => spans.map((s) => (s as TextSpan).text).join();

void main() {
  test('the source dash glyph read as two underscores is shown as a dash', () {
    expect(printedDashes('apply also to any offence committed by__'), 'apply also to any offence committed by—');
    expect(printedDashes('Whoever,__ (a) by words'), 'Whoever,— (a) by words');
    expect(printedDashes('Explanation.__ It does not amount'), 'Explanation.— It does not amount');
  });

  test('a blank to fill in and a single underscore are left as printed', () {
    expect(printedDashes('Name of the accused ________ son of ______'), 'Name of the accused ________ son of ______');
    expect(printedDashes('file_name'), 'file_name');
  });

  test('amendment and omission markers stay raised after the dash is shown', () {
    const style = TextStyle(fontSize: 16);
    final spans = markedSpans('committed by__ 4* * * throughout 5[Pakistan]', style);
    expect(spansText(spans), 'committed by— 4* * * throughout 5[Pakistan]');
    final raised = spans.where((s) => (s as TextSpan).style?.fontFeatures?.isNotEmpty == true).map((s) => (s as TextSpan).text);
    expect(raised, ['4', '5']);
  });
}
