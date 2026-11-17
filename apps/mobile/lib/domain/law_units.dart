/// How units of a law are named to a reader (client domain sublayer: pure, no widgets, no I/O).
///
/// The segmenter stores every numbered unit of a statute as `section`; a constitution numbers Articles, and the
/// instrument's stored kind (`constitution`) decides the word -- the same rule the server's citation renderer
/// follows (nizam/storage/library_read.py `render_citation`, DECISION-LOG D-070). Labels themselves always come from
/// the records (INV-1); only the noun around them is chosen here.
library;

const _nouns = {
  'section': 'Section',
  'article': 'Article',
  'rule': 'Rule',
  'regulation': 'Regulation',
  'preamble': 'Preamble',
  'part': 'Part',
  'chapter': 'Chapter',
  'schedule': 'Schedule',
  'annexure': 'Annex',
  'appendix': 'Appendix',
  'division': 'Division',
  'title': 'Title',
  'form': 'Form',
  'order': 'Order',
};

/// The noun for a unit of [provisionKind] in a law of [instrumentKind]: 'Article' for a constitution's sections.
String unitNoun(String instrumentKind, String provisionKind) {
  if (provisionKind == 'section' && instrumentKind == 'constitution') return 'Article';
  return _nouns[provisionKind] ??
      (provisionKind.isEmpty ? '' : provisionKind[0].toUpperCase() + provisionKind.substring(1));
}

/// The plural used for a law's served numbered units ('339 articles served').
String unitsNoun(String instrumentKind, int count) {
  final noun = instrumentKind == 'constitution' ? 'article' : 'section';
  return count == 1 ? noun : '${noun}s';
}

const _small = {'a', 'an', 'and', 'as', 'at', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with'};

/// A caption printed in capitals ('FUNDAMENTAL RIGHTS AND PRINCIPLES OF POLICY') shown in title case; a caption with
/// any lower-case letter is shown exactly as printed. Presentation only: the stored words are unchanged.
String captionCase(String caption) {
  final text = caption.trim();
  if (text.isEmpty || RegExp(r'[a-z]').hasMatch(text)) return text;
  var first = true;
  return text.split(RegExp(r'\s+')).map((word) {
    final lower = word.toLowerCase();
    final keepSmall = !first && _small.contains(lower);
    first = false;
    if (keepSmall) return lower;
    // Roman numerals and a word with digits stay as printed ('XII', '2A')
    if (RegExp(r'^[IVXLC]+[.,;:]?$').hasMatch(word) || RegExp(r'\d').hasMatch(word)) return word;
    final i = lower.indexOf(RegExp(r'[a-z]'));
    return i < 0 ? lower : lower.substring(0, i) + lower[i].toUpperCase() + lower.substring(i + 1);
  }).join(' ');
}

/// A division as a reader names it: 'Part II — Fundamental Rights and Principles of Policy', 'Annex', 'Preamble'.
/// The label is shown only when it adds to the noun (a stored label 'Preamble' or 'ANNEX' repeats it).
String divisionTitle(String instrumentKind, String kind, String? label, String? caption) {
  final noun = unitNoun(instrumentKind, kind);
  final l = (label ?? '').trim();
  final repeats = l.isEmpty || l.toLowerCase() == noun.toLowerCase() || l.toLowerCase() == kind.toLowerCase();
  final head = repeats ? noun : (kind == 'schedule' ? captionCase(l) : '$noun $l');
  final c = (caption ?? '').trim();
  return c.isEmpty ? head : '$head — ${captionCase(c)}';
}
