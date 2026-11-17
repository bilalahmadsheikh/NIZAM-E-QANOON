import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../design/status_banner.dart';
import '../state/library_state.dart';
import 'library.dart';

/// The Constitution's page (D-070): the Constitution itself first -- its standing, where to start reading, its
/// Parts by their printed titles -- then the texts around it, each group saying how it relates. The server sends the
/// groups as codes with their members (nizam/api/collections.py); the words that explain them live here (docs/13).
class ConstitutionScreen extends ConsumerWidget {
  const ConstitutionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final page = ref.watch(constitutionProvider);
    return LibraryScaffold(
      title: 'The Constitution',
      selected: 0, // opened from Discover; the Library tab is the catalogue

      body: ReadingWidth(
        child: page.when(
          loading: () => const Padding(padding: EdgeInsets.all(24), child: LoadingStructure()),
          error: (e, s) => Padding(
            padding: const EdgeInsets.all(24),
            child: LoadFailure(e, onRetry: () => ref.invalidate(constitutionProvider)),
          ),
          data: (p) => p.constitution == null
              ? const Padding(
                  padding: EdgeInsets.all(24),
                  child: Notice('The Constitution is not available in the release for the chosen date.'),
                )
              : _Body(page: p, constitution: p.constitution!),
        ),
      ),
    );
  }
}

class _Body extends ConsumerWidget {
  final law.ConstitutionPage page;
  final law.Instrument constitution;
  const _Body({required this.page, required this.constitution});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final parts = ref.watch(childrenProvider((instrument: constitution.id, parent: null)));
    final top = parts.valueOrNull?.items ?? const <law.Node>[];
    final preamble = top.where((n) => n.kind == 'preamble').firstOrNull;
    final groups = {for (final g in page.groups) g.key: g.items};
    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
          sliver: SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Eyebrow('The supreme law of Pakistan'),
                const SizedBox(height: 12),
                Text(constitution.title ?? 'The Constitution', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 8),
                Text('${jurisdictionName(constitution.jurisdiction)} · ${constitution.year_display} · '
                    'the consolidated text as amended'),
                const SizedBox(height: 16),
                StatusBanner(instrumentWording(constitution), compact: true),
                const SizedBox(height: 20),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    FilledButton.icon(
                      onPressed: preamble == null ? null : () => context.push('/provision/${preamble.id}'),
                      icon: const Icon(Icons.menu_book_outlined),
                      label: const Text('Start with the Preamble'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => context.push('/instrument/${constitution.id}'),
                      icon: const Icon(Icons.view_agenda_outlined),
                      label: const Text('All Articles'),
                    ),
                  ],
                ),
                const SizedBox(height: 32),
                Text('Its Parts', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 6),
                const Text('The Constitution is arranged in twelve Parts. Open one to see its Chapters and Articles.',
                    style: TextStyle(height: 1.45)),
                const SizedBox(height: 14),
              ],
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          sliver: parts.when(
            loading: () => const SliverToBoxAdapter(child: LoadingStructure()),
            error: (e, s) => SliverToBoxAdapter(
              child: LoadFailure(e,
                  onRetry: () => ref.invalidate(childrenProvider((instrument: constitution.id, parent: null)))),
            ),
            data: (p) => SliverList.builder(
              itemCount: p.items.where((n) => n.kind != 'preamble').length,
              itemBuilder: (context, i) => _PartRow(node: p.items.where((n) => n.kind != 'preamble').elementAt(i)),
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(24, 32, 24, 120),
          sliver: SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (groups['amendments'] case final items?) _Amendments(items: items),
                if (groups['edition'] case final items?)
                  _Group(
                    title: 'An earlier edition',
                    explain: 'The Constitution as it stood on the date you chose, in the Punjab Code\'s compilation. '
                        'It is shown because that date falls within the period this edition was current.',
                    items: items,
                  ),
                if (groups['before_1973'] case final items?)
                  _Group(
                    title: 'Before 1973',
                    explain: 'The constitutional instruments under which Pakistan was governed before this '
                        'Constitution. They are history, not the Constitution in force today; open one to see the '
                        'status recorded for it.',
                    items: items,
                  ),
                if (groups['ajk'] case final items?)
                  _Group(
                    title: 'Azad Jammu and Kashmir',
                    explain: 'Azad Jammu and Kashmir is governed by its own Interim Constitution, not by this '
                        'Constitution. The library holds these Acts amending it; the Interim Constitution\'s own text '
                        'is not yet in the library.',
                    items: items,
                  ),
                const SizedBox(height: 8),
                const Notice(
                  'Legal information, not advice. Every text here is reproduced from the database and linked to its '
                  'official source.',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// One Part of the Constitution: its number and its printed title (the caption, D-070).
class _PartRow extends StatelessWidget {
  final law.Node node;
  const _PartRow({required this.node});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final named = node.kind == 'part';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: scheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: scheme.outline)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => context.push('/provision/${node.id}'),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
            child: Row(
              children: [
                SizedBox(
                  width: 58,
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      named ? '\u2068${node.label ?? ''}\u2069' : '',
                      maxLines: 1,
                      style: TextStyle(fontFamily: 'Spectral', fontSize: 24, color: scheme.secondary),
                    ),
                  ),
                ),
                Expanded(
                  child: Text(
                    named
                        ? captionCase(node.heading ?? node.caption ?? 'Part ${node.label ?? ''}')
                        : divisionTitle('constitution', node.kind, node.label, node.heading ?? node.caption),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, height: 1.35),
                  ),
                ),
                const Icon(Icons.chevron_right),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The amending Acts and Orders, newest first; the first few are shown and the rest open on request.
class _Amendments extends StatefulWidget {
  final List<law.FamilyItem> items;
  const _Amendments({required this.items});
  @override
  State<_Amendments> createState() => _AmendmentsState();
}

class _AmendmentsState extends State<_Amendments> {
  bool all = false;
  @override
  Widget build(BuildContext context) {
    final newest = widget.items.reversed.toList();
    final shown = all ? newest : newest.take(6).toList();
    final latest = newest.first;
    return Padding(
      padding: const EdgeInsets.only(bottom: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('How it has been amended', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            'Acts of Parliament and President\'s Orders that changed the Constitution\'s text. The text above already '
            'reads with their changes. Where the library has linked an amendment to the provisions it changed, the '
            'count is shown. The library holds ${widget.items.length} of these texts, up to the '
            '${latest.short_name} (${latest.instrument.year_display}); later amendments appear in the consolidated '
            'text, but their Acts are not yet held separately.',
            style: const TextStyle(height: 1.45),
          ),
          const SizedBox(height: 14),
          for (final item in shown) _FamilyRow(item: item),
          if (newest.length > shown.length || all)
            TextButton.icon(
              onPressed: () => setState(() => all = !all),
              icon: Icon(all ? Icons.expand_less : Icons.expand_more),
              label: Text(all ? 'Show fewer' : 'Show all ${newest.length}'),
            ),
        ],
      ),
    );
  }
}

class _Group extends StatelessWidget {
  final String title;
  final String explain;
  final List<law.FamilyItem> items;
  const _Group({required this.title, required this.explain, required this.items});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text(explain, style: const TextStyle(height: 1.45)),
            const SizedBox(height: 14),
            for (final item in items) _FamilyRow(item: item),
          ],
        ),
      );
}

/// A related text: its short name, its full title and year, and how many provisions of the Constitution the library
/// has linked it to (only when a link is recorded; no count is never read as "changes nothing").
class _FamilyRow extends StatelessWidget {
  final law.FamilyItem item;
  const _FamilyRow({required this.item});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final i = item.instrument;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: scheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: BorderSide(color: scheme.outline)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => context.push('/instrument/${i.id}'),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
            child: Row(
              children: [
                SizedBox(
                  width: 52,
                  child: Text(i.year_display,
                      style: TextStyle(fontFamily: 'Spectral', fontSize: 17, color: scheme.secondary)),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(item.short_name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                      const SizedBox(height: 2),
                      Text(i.title ?? '', style: const TextStyle(fontSize: 13, height: 1.35)),
                      if (item.amends_units > 0) ...[
                        const SizedBox(height: 4),
                        Text(
                          'Linked to ${item.amends_units} change${item.amends_units == 1 ? '' : 's'} in the Constitution',
                          style: TextStyle(fontSize: 12, color: scheme.secondary),
                        ),
                      ],
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, size: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
