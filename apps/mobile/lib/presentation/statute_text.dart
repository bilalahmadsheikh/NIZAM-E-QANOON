import 'package:flutter/material.dart';
import '../contracts/library_models.g.dart' as law;
import '../domain/law_status.dart';

/// A unit read the way the statute prints it: the opened unit's own words, then every served sub-unit in printed
/// order, indented by depth, each with its printed label -- '(1)', '(a)', 'Provided that'. A lazy sliver: a long
/// section (or a whole Part) costs only the rows on screen.
class StatuteText extends StatelessWidget {
  final List<law.UnitNode> nodes;
  final double size;
  const StatuteText({super.key, required this.nodes, required this.size});

  @override
  Widget build(BuildContext context) => SliverList.builder(
        itemCount: nodes.length,
        itemBuilder: (context, i) => _NodeRow(node: nodes[i], size: size, first: i == 0),
      );
}

/// An amendment footnote marker -- the '2' of '2[Balochistan]' -- is part of the printed consolidated text and is
/// kept, never stripped (the words are the law's); it is set as a small raised numeral so it reads as a footnote
/// mark instead of a number in the sentence. Same opening shape as nzq_amendment_marks (migration 0099).
// '2[Balochistan]' (an amendment) and '4* * *' (an omission) -- the footnote number opens either
final _marker = RegExp(r'(?<![0-9.,\w])([0-9]{1,2})(?=\s*(?:\[|\*\s*\*\s*\*))');

/// The Pakistan Code PDFs print a dash after 'Whoever,' or a heading as a small double-dash glyph that their text layer
/// gives as two underscores ('committed by__', 'Explanation.__'). Page-checked on the PPC (p. 30, 17 Nov 2026). It is
/// shown as the dash it is; the stored text stays verbatim. Longer runs ('______', a blank to fill in) are untouched.
final _dashGlyph = RegExp(r'(?<!_)__(?!_)');

String printedDashes(String text) => text.replaceAll(_dashGlyph, '—');

List<InlineSpan> markedSpans(String raw, TextStyle body) {
  final text = printedDashes(raw);
  final spans = <InlineSpan>[];
  var at = 0;
  for (final m in _marker.allMatches(text)) {
    if (m.start > at) spans.add(TextSpan(text: text.substring(at, m.start)));
    spans.add(TextSpan(
      text: m.group(1),
      // Spectral carries real superscript numerals ('sups'); scaling them down as well made them a dot
      style: body.copyWith(
        fontFeatures: const [FontFeature.superscripts()],
        color: body.color?.withValues(alpha: .75),
      ),
    ));
    at = m.end;
  }
  if (at < text.length) spans.add(TextSpan(text: text.substring(at)));
  return spans;
}

class _NodeRow extends StatelessWidget {
  final law.UnitNode node;
  final double size;
  final bool first;
  const _NodeRow({required this.node, required this.size, required this.first});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final urdu = node.text_language == 'ur' || node.text_language == 'sd';
    final text = (urdu ? node.text_ur : node.text_en)?.trim();
    final omitted = node.operation == 'omitted';
    // indentation steps flatten after four levels so deep clauses stay readable on a phone
    final indent = (node.depth.clamp(0, 4)) * 18.0;
    final label = node.depth == 0 ? '' : printedLabel(node.kind, node.label);
    final showHeading = node.depth > 0 && (node.heading ?? '').trim().isNotEmpty;
    final body = TextStyle(
      fontFamily: urdu ? 'Noto Nastaliq Urdu' : 'Spectral',
      fontSize: size + (urdu ? 2 : 0),
      height: urdu ? 2.1 : 1.65,
      color: omitted ? scheme.onSurface.withValues(alpha: .55) : scheme.onSurface,
    );
    if ((text == null || text.isEmpty) && !showHeading && label.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: EdgeInsetsDirectional.only(start: indent, top: first ? 0 : 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (showHeading)
            Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 4),
              child: Text(
                // U+2068/U+2069: a label beside a heading keeps its digits and brackets in place in either script
                '\u2068${label.isEmpty ? '' : '$label '}\u2069${printedDashes(node.heading!.trim())}',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: size - 1, height: 1.4),
              ),
            ),
          if (text != null && text.isNotEmpty)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              textDirection: urdu ? TextDirection.rtl : TextDirection.ltr,
              children: [
                if (label.isNotEmpty && !showHeading)
                  ConstrainedBox(
                    constraints: BoxConstraints(minWidth: size * 2.2),
                    child: Padding(
                      padding: const EdgeInsetsDirectional.only(end: 8),
                      child: Text(
                        '\u2068$label\u2069',
                        style: body.copyWith(fontWeight: FontWeight.w600, fontFamily: 'Spectral'),
                      ),
                    ),
                  ),
                Expanded(
                  child: Text.rich(
                    TextSpan(children: markedSpans(omitted ? '[Omitted] $text' : text, body)),
                    textDirection: urdu ? TextDirection.rtl : TextDirection.ltr,
                    style: body,
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }
}
