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
  'notification': 'Notification', // an unnumbered notification's one unit (DECISION-LOG D-115)
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

// A recital opens where the preamble prints one: after a stop (';', ':', '—', '.', ',') or at the start, in the
// capitals or the capitalised words the statute itself uses (DECISION-LOG D-073).
final _recital = RegExp(
    r'(?<=^|[;:—.,]\s{0,3}|_{2}\s{0,3})(?=(?:AND\s+WHEREAS|WHEREAS|WHEREIN|NOW,?\s+THEREFORE|Now,?\s+therefore|'
    r'And\s+whereas|So\s+that\s|Conscious\s+of|Cognisant\s+of|Faithful\s+to|Dedicated\s+to|Inspired\s+by|'
    r'Do\s+hereby|It\s+is\s+hereby\s+enacted)\b)');
final _printedHead = RegExp(r'^\s*PREAMBLE\.?\s+(?=\S)');

/// A preamble's served words as the paragraphs the statute prints. The stored text joins its printed recitals with
/// spaces, so the reader breaks it where a recital opens; the printed head 'PREAMBLE' above the first recital is
/// not repeated under a title that already says Preamble. No word is changed, added or dropped beyond that head.
List<String> preambleParagraphs(String text) {
  final body = text.replaceFirst(_printedHead, '');
  final cuts = _recital.allMatches(body).map((m) => m.start).where((i) => i > 0).toList();
  final parts = <String>[];
  var at = 0;
  for (final c in cuts) {
    parts.add(body.substring(at, c).trim());
    at = c;
  }
  parts.add(body.substring(at).trim());
  return parts.where((p) => p.isNotEmpty).toList();
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
