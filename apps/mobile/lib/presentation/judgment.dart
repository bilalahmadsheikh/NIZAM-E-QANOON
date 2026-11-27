import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart';
import '../design/components.dart';
import '../domain/law_units.dart';
import '../state/library_state.dart';
import 'precedent.dart';

/// A judgment, read whole (D-184). Order: what it is (court, parties as published, the citation, the decision date,
/// bench and outcome, all from records), why names are withheld where they are, the laws it cites -- each opening the
/// law at that unit -- then the text as the court printed it, then the cases around it: the cases it cites, the other
/// decisions in its case, the decision it heard on appeal, what the courts above did, and the later judgments citing
/// it. A machine-read reversal or negative treatment is withheld until a lawyer verifies it (PRECEDENT-MODEL §2).
class JudgmentScreen extends ConsumerWidget {
  final String id;
  final String? paragraph;   // the passage a search found, highlighted and shown first
  const JudgmentScreen({super.key, required this.id, this.paragraph});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(judgmentProvider(id));
    final page = result.valueOrNull;
    final size = ref.watch(readerSizeProvider) - 2;
    return LibraryScaffold(
      title: 'Judgment',
      selected: 2,
      body: ReadingWidth(
        child: SelectionArea(
          child: CustomScrollView(
            cacheExtent: 1200,
            slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(24, 20, 24, 8),
                sliver: SliverToBoxAdapter(
                  child: result.when(
                    loading: () => const LoadingStructure(),
                    error: (e, s) => LoadFailure(e, onRetry: () => ref.invalidate(judgmentProvider(id))),
                    data: (p) => _Head(page: p, found: paragraph),
                  ),
                ),
              ),
              if (page != null) ...[
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 16, 24, 8),
                  sliver: SliverToBoxAdapter(child: _LawsCited(items: page.statutes_cited)),
                ),
                const SliverPadding(
                  padding: EdgeInsets.fromLTRB(24, 28, 24, 12),
                  sliver: SliverToBoxAdapter(child: Eyebrow('The judgment')),
                ),
                if (page.paragraphs.isEmpty)
                  const SliverPadding(
                    padding: EdgeInsets.symmetric(horizontal: 24),
                    sliver: SliverToBoxAdapter(child: Notice('No text of this judgment is held; open its source.')),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    sliver: SliverList.builder(
                      itemCount: page.paragraphs.length,
                      itemBuilder: (context, i) => _ParagraphRow(
                        paragraph: page.paragraphs[i],
                        opinion: _opinionStarting(page, i),
                        size: size,
                        found: page.paragraphs[i].id == paragraph,
                      ),
                    ),
                  ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 0),
                  sliver: SliverToBoxAdapter(child: _CasesCited(items: page.cases_cited)),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 0),
                  sliver: SliverToBoxAdapter(child: _InThisCase(page: page)),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 0),
                  sliver: SliverToBoxAdapter(child: _History(id: id)),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 0),
                  sliver: SliverToBoxAdapter(child: _CitedBy(id: id)),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 28, 24, 120),
                  sliver: SliverToBoxAdapter(child: _Footer(page: page)),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  /// The opinion that starts at paragraph [i] (a dissent, a concurrence), when it is not the first paragraph's.
  static JudgmentOpinion? _opinionStarting(JudgmentPage page, int i) {
    final here = page.paragraphs[i].opinion;
    if (here == null || page.opinions.length < 2) return null;
    if (i > 0 && page.paragraphs[i - 1].opinion == here) return null;
    return page.opinions.where((o) => o.ordinal == here).firstOrNull;
  }
}

String _human(String code) => code.isEmpty ? code : (code[0].toUpperCase() + code.substring(1)).replaceAll('_', ' ');

class _Head extends StatelessWidget {
  final JudgmentPage page;
  final String? found;
  const _Head({required this.page, this.found});
  @override
  Widget build(BuildContext context) {
    final j = page.judgment;
    final scheme = Theme.of(context).colorScheme;
    final rows = <(String, String)>[
      ('Decided', decidedWording(decidedOn: j.decided_on, undated: j.undated, noLaterThan: j.decided_no_later_than)
          .replaceFirst('Decided ', '')),
      if (j.undated && j.undated_reason != null) ('Why no date', j.undated_reason!),
      if (j.hearing_on != null) ('Heard', j.hearing_on!),
      if (j.bench_printed.isNotEmpty) ('Bench', j.bench_printed.join('\n')),
      if (j.disposition_printed != null || j.disposition != null)
        ('Outcome', j.disposition_printed ?? _human(j.disposition!)),
      if (j.neutral_citation != null) ('Neutral citation', j.neutral_citation!),
      if (j.reported_flag == true) ('Reported', 'Marked for reporting by the court'),
    ];
    final hit = found == null ? null : page.paragraphs.where((p) => p.id == found).firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Eyebrow([j.court_name, if (j.case_type_name != null) j.case_type_name!].join(' · ')),
        const SizedBox(height: 12),
        Text('\u2068${j.parties_display ?? j.case_no_printed ?? 'Judgment'}\u2069',
            style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 10),
        Text('\u2068${page.citation}\u2069', style: TextStyle(fontSize: 14, height: 1.45, color: scheme.secondary)),
        const SizedBox(height: 18),
        for (final (k, v) in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(width: 120, child: Text(k, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700))),
                Expanded(child: Text(v, style: const TextStyle(fontSize: 14, height: 1.45))),
              ],
            ),
          ),
        if (page.privacy.names_withheld) ...[
          const SizedBox(height: 12),
          Notice(
            'Names are withheld in this judgment'
            '${page.privacy.categories.isEmpty ? '' : ': ${page.privacy.categories.map((c) => c.name ?? _human(c.code)).join(', ')}'}'
            '${page.privacy.categories.any((c) => c.basis != null) ? ' (${page.privacy.categories.map((c) => c.basis).whereType<String>().join('; ')})' : ''}.',
            icon: Icons.visibility_off_outlined,
          ),
        ],
        if (page.case_record.copy_of_judgment_id case final kept?) ...[
          const SizedBox(height: 12),
          _LinkNotice(
            text: 'This is a second copy of a decision. The copy kept is listed and cited instead.',
            action: 'Open the copy kept',
            onTap: () => context.pushReplacement('/judgment/$kept'),
          ),
        ],
        if (hit != null) ...[
          const SizedBox(height: 20),
          const Eyebrow('The passage your search found'),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(color: solidTint(context, .1), borderRadius: BorderRadius.circular(16)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(hit.text, style: const TextStyle(fontFamily: 'Spectral', fontSize: 17, height: 1.55)),
              const SizedBox(height: 8),
              Text('\u2068${hit.citation}\u2069', style: TextStyle(fontSize: 12, color: scheme.secondary)),
            ]),
          ),
        ],
      ],
    );
  }
}

class _LinkNotice extends StatelessWidget {
  final String text;
  final String action;
  final VoidCallback onTap;
  const _LinkNotice({required this.text, required this.action, required this.onTap});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Notice(text),
          TextButton.icon(onPressed: onTap, icon: const Icon(Icons.arrow_forward), label: Text(action)),
        ],
      );
}

/// The laws the judgment cites, by law, each unit opening the law there. A unit whose text changed since the
/// decision, or that is not served on the chosen date, says so beside it: the court read the law of its day.
class _LawsCited extends StatefulWidget {
  final List<CitedProvision> items;
  const _LawsCited({required this.items});
  @override
  State<_LawsCited> createState() => _LawsCitedState();
}

class _LawsCitedState extends State<_LawsCited> {
  bool all = false;
  @override
  Widget build(BuildContext context) {
    if (widget.items.isEmpty) {
      return const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Eyebrow('Laws this judgment cites'),
        SizedBox(height: 10),
        Text('No citation of a law held in the library was read in this judgment.', style: TextStyle(fontSize: 14)),
      ]);
    }
    final byLaw = <String, List<CitedProvision>>{};
    for (final c in widget.items) {
      byLaw.putIfAbsent('${c.law_title ?? 'A law'}${c.law_year == null ? '' : ', ${c.law_year}'}', () => []).add(c);
    }
    final laws = byLaw.entries.toList();
    final shown = all ? laws : laws.take(6).toList();
    final changed = widget.items.any((c) => c.status_now != 'same_text');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Eyebrow('Laws this judgment cites'),
        const SizedBox(height: 6),
        const Text('Open a provision to read the law as it stands on the chosen date.', style: TextStyle(fontSize: 13)),
        const SizedBox(height: 14),
        for (final e in shown) ...[
          Text(e.key, style: const TextStyle(fontFamily: 'Spectral', fontSize: 17, height: 1.35)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [for (final c in e.value) _UnitChip(item: c)],
          ),
          const SizedBox(height: 16),
        ],
        if (laws.length > shown.length)
          TextButton(onPressed: () => setState(() => all = true), child: Text('Show all ${laws.length} laws')),
        if (changed)
          const Notice(
            'Marked provisions have changed since the decision, or are not in force on the chosen date. The court read '
            'the law of its day: compare before relying on the judgment.',
            icon: Icons.history,
          ),
      ],
    );
  }
}

class _UnitChip extends StatelessWidget {
  final CitedProvision item;
  const _UnitChip({required this.item});
  @override
  Widget build(BuildContext context) {
    final noun = unitNoun(item.law_kind ?? '', item.kind ?? 'section');
    final label = item.label == null ? noun : '$noun ${item.label}';
    final mark = switch (item.status_now) {
      'amended_since' => (Icons.edit_note, 'amended since'),
      'not_operative' => (Icons.do_not_disturb_on_outlined, 'not in force on the chosen date'),
      'text_at_decision_not_held' => (Icons.help_outline, 'text at the decision date not held'),
      _ => null,
    };
    return Semantics(
      button: true,
      label: '${item.citation}${mark == null ? '' : ', ${mark.$2}'}. Opens the law.',
      excludeSemantics: true,
      child: ActionChip(
        avatar: mark == null ? null : Icon(mark.$1, size: 16),
        label: Text('\u2068$label\u2069${item.mentions > 1 ? ' · ${item.mentions}×' : ''}'),
        tooltip: mark?.$2,
        onPressed: () => context.push('/provision/${item.provision_id}'),
      ),
    );
  }
}

class _ParagraphRow extends StatelessWidget {
  final JudgmentParagraph paragraph;
  final JudgmentOpinion? opinion;
  final double size;
  final bool found;
  const _ParagraphRow({required this.paragraph, this.opinion, required this.size, this.found = false});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final footnote = paragraph.kind == 'footnote';
    final number = paragraph.printed_no;
    final text = Text(
      paragraph.text,
      style: TextStyle(fontFamily: 'Spectral', fontSize: footnote ? size - 3 : size, height: 1.6),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (opinion != null) ...[
          const SizedBox(height: 20),
          Text(
            [
              if (opinion!.kind != null) _human(opinion!.kind!),
              if (opinion!.author_printed != null) opinion!.author_printed!,
            ].join(' · '),
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: scheme.secondary),
          ),
          if (opinion!.heading_printed != null) ...[
            const SizedBox(height: 4),
            Text(opinion!.heading_printed!, style: const TextStyle(fontFamily: 'Spectral', fontSize: 17)),
          ],
          const SizedBox(height: 12),
        ],
        Container(
          margin: const EdgeInsets.only(bottom: 14),
          padding: found ? const EdgeInsets.all(12) : EdgeInsets.zero,
          decoration: found ? BoxDecoration(color: solidTint(context, .1), borderRadius: BorderRadius.circular(12)) : null,
          child: number == null
              ? (footnote
                  ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('Note  ', style: TextStyle(fontSize: 12, color: scheme.secondary)),
                      Expanded(child: text),
                    ])
                  : text)
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 40,
                      child: Text(
                        footnote ? '[$number]' : '$number.',
                        style: TextStyle(
                            fontFamily: 'Spectral', fontSize: footnote ? size - 4 : size - 2, color: scheme.secondary),
                      ),
                    ),
                    Expanded(child: text),
                  ],
                ),
        ),
      ],
    );
  }
}

class _CasesCited extends StatefulWidget {
  final List<CitedCase> items;
  const _CasesCited({required this.items});
  @override
  State<_CasesCited> createState() => _CasesCitedState();
}

class _CasesCitedState extends State<_CasesCited> {
  bool all = false;
  @override
  Widget build(BuildContext context) {
    final items = widget.items;
    if (items.isEmpty) return const SizedBox.shrink();
    final held = items.where((c) => c.judgment_id != null).length;
    final shown = all ? items : items.take(8).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Eyebrow('Cases this judgment cites'),
        const SizedBox(height: 6),
        Text('${items.length} cited · $held held in the library', style: const TextStyle(fontSize: 13)),
        const SizedBox(height: 10),
        for (final c in shown)
          ListTile(
            contentPadding: EdgeInsets.zero,
            minTileHeight: 48,
            leading: Icon(c.judgment_id == null ? Icons.remove : Icons.gavel_outlined, size: 20),
            title: Text('\u2068${c.raw}\u2069', style: const TextStyle(fontSize: 15)),
            subtitle: c.judgment_id == null ? const Text('Not held in the library', style: TextStyle(fontSize: 12)) : null,
            trailing: c.judgment_id == null ? null : const Icon(Icons.chevron_right),
            onTap: c.judgment_id == null ? null : () => context.push('/judgment/${c.judgment_id}'),
          ),
        if (items.length > shown.length)
          TextButton(onPressed: () => setState(() => all = true), child: Text('Show all ${items.length} cases')),
      ],
    );
  }
}

class _InThisCase extends StatelessWidget {
  final JudgmentPage page;
  const _InThisCase({required this.page});
  @override
  Widget build(BuildContext context) {
    final others = page.case_record.other_decisions;
    final below = page.appeal_from;
    if (others.isEmpty && below.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Eyebrow('In this case'),
        const SizedBox(height: 10),
        for (final d in others)
          ListTile(
            contentPadding: EdgeInsets.zero,
            minTileHeight: 48,
            leading: const Icon(Icons.description_outlined, size: 20),
            title: Text('\u2068${d.citation}\u2069', style: const TextStyle(fontSize: 14)),
            subtitle: const Text('Another decision in the same case', style: TextStyle(fontSize: 12)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/judgment/${d.judgment_id}'),
          ),
        for (final b in below)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Icon(Icons.subdirectory_arrow_right, size: 20),
              const SizedBox(width: 16),
              Expanded(
                child: Text(
                  'Heard from ${b.court_below ?? 'the court below'}'
                  '${b.case_below == null ? '' : ', ${b.case_below}'}'
                  '${b.decided_below == null ? '' : ', decided ${b.decided_below}'}'
                  '${b.outcome != null ? '. Outcome: ${_human(b.outcome!)}.' : b.outcome_withheld ? '. What this judgment did to that decision awaits a lawyer’s review.' : '.'}',
                  style: const TextStyle(fontSize: 14, height: 1.45),
                ),
              ),
            ]),
          ),
      ],
    );
  }
}

class _History extends ConsumerWidget {
  final String id;
  const _History({required this.id});
  @override
  Widget build(BuildContext context, WidgetRef ref) => ref.watch(historyProvider(id)).when(
        loading: () => const SizedBox.shrink(),
        error: (e, s) => const SizedBox.shrink(),
        data: (h) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Eyebrow('What the courts above did'),
            const SizedBox(height: 10),
            if (h.items.isEmpty)
              Text('No appeal from this decision is held. ${h.coverage_note}', style: const TextStyle(fontSize: 13, height: 1.45))
            else
              for (final x in h.items)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  minTileHeight: 48,
                  leading: const Icon(Icons.north_east, size: 20),
                  title: Text('\u2068${x.citation ?? x.court}\u2069', style: const TextStyle(fontSize: 14)),
                  subtitle: Text(
                    x.outcome_withheld
                        ? 'Outcome awaits a lawyer’s review'
                        : [
                            if (x.outcome != null) _human(x.outcome!),
                            if (x.source == 'court_record') 'as recorded by the court',
                            if (x.citation == null && x.decided_on != null) 'decided ${x.decided_on}',
                          ].join(' · '),
                    style: const TextStyle(fontSize: 12),
                  ),
                  trailing: x.judgment_id == null ? null : const Icon(Icons.chevron_right),
                  onTap: x.judgment_id == null ? null : () => context.push('/judgment/${x.judgment_id}'),
                ),
          ],
        ),
      );
}

class _CitedBy extends ConsumerWidget {
  final String id;
  const _CitedBy({required this.id});
  @override
  Widget build(BuildContext context, WidgetRef ref) => ref.watch(citedByProvider(id)).when(
        loading: () => const SizedBox.shrink(),
        error: (e, s) => const SizedBox.shrink(),
        data: (list) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Eyebrow('Later judgments citing this case'),
            const SizedBox(height: 10),
            if (list.items.isEmpty)
              Text('No later judgment held cites this case. ${list.coverage_note}',
                  style: const TextStyle(fontSize: 13, height: 1.45))
            else
              for (final item in list.items) JudgmentTile(item: item, showRoles: false),
          ],
        ),
      );
}

class _Footer extends ConsumerWidget {
  final JudgmentPage page;
  const _Footer({required this.page});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final url = page.judgment.source_url;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (url != null) ...[
          OutlinedButton.icon(
            onPressed: () async {
              final opened = await ref.read(sourceActionsProvider).open(url);
              if (!opened && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Could not open the source. You can copy its address.')),
                );
              }
            },
            icon: const Icon(Icons.open_in_new),
            label: const Text('Open the court’s published copy'),
          ),
          const SizedBox(height: 16),
        ],
        Notice(page.note),
      ],
    );
  }
}
