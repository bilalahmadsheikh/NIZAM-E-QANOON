import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../domain/law_status.dart';
import '../state/library_state.dart';
import 'library.dart';

/// The library (D-075). One search box answers two questions -- "which law is called this?" and "which law deals
/// with this?" -- and every list puts first the laws the rest of the corpus relies on (how many other laws cite
/// them), so a reader browsing a province's Rules meets the ones practice turns on before the hundreds nothing cites.
class CatalogueScreen extends ConsumerStatefulWidget {
  final String initialQuery;
  final String initialJurisdiction;
  final String initialKind;
  const CatalogueScreen({super.key, this.initialQuery = '', this.initialJurisdiction = '', this.initialKind = ''});
  @override
  ConsumerState<CatalogueScreen> createState() => _CatalogueScreenState();
}

const _jurisdictions = ['', 'fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'];
const _kinds = {
  '': 'All kinds',
  'act': 'Acts',
  'ordinance': 'Ordinances',
  'rules': 'Rules',
  'regulation': 'Regulations',
  'order': 'Orders',
  'constitution': 'Constitutions',
  'sro': 'SROs',
  'notification': 'Notifications',
};
const _tries = ['robbery', 'bail', 'divorce', 'inheritance', 'rent', 'income tax', 'police', 'land acquisition'];

class _CatalogueScreenState extends ConsumerState<CatalogueScreen> {
  late final TextEditingController search = TextEditingController(text: widget.initialQuery);
  late String q = widget.initialQuery;
  late String jurisdiction = widget.initialJurisdiction;
  late String kind = widget.initialKind;

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  void _search(String value) => setState(() {
        q = value.trim();
        search.text = q;
      });

  String get _listTitle {
    final where = jurisdiction.isEmpty ? '' : '${jurisdictionName(jurisdiction)} ';
    final what = kind.isEmpty ? 'laws' : _kinds[kind]!.toLowerCase();
    return q.isEmpty ? '${where.isEmpty ? 'All ' : where}$what' : 'Titles with “$q”';
  }

  @override
  Widget build(BuildContext context) {
    final query = (q: q, jurisdiction: jurisdiction, kind: kind);
    final result = ref.watch(catalogueProvider(query));
    final scheme = Theme.of(context).colorScheme;
    return LibraryScaffold(
      title: 'The legal library',
      body: ReadingWidth(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 4),
              sliver: SliverToBoxAdapter(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Eyebrow('Find your way through the law'),
                    const SizedBox(height: 12),
                    Text('Every law.\nThe ones that matter, first.', style: Theme.of(context).textTheme.headlineMedium),
                    const SizedBox(height: 10),
                    const Text(
                      'Search a title, or what a law is about. Lists open with the laws other laws cite most — '
                      'the Codes and Acts practice turns on.',
                      style: TextStyle(height: 1.5),
                    ),
                    const SizedBox(height: 20),
                    TextField(
                      controller: search,
                      textInputAction: TextInputAction.search,
                      onSubmitted: _search,
                      decoration: InputDecoration(
                        hintText: 'A title or a subject — robbery, bail, rent…',
                        prefixIcon: const Icon(Icons.search),
                        filled: true,
                        fillColor: scheme.surface,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(28)),
                        suffixIcon: q.isEmpty
                            ? IconButton(tooltip: 'Search', onPressed: () => _search(search.text), icon: const Icon(Icons.arrow_forward))
                            : IconButton(tooltip: 'Clear the search', onPressed: () => _search(''), icon: const Icon(Icons.close)),
                      ),
                    ),
                    if (q.isEmpty) ...[
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text('Try', style: TextStyle(fontSize: 12, color: scheme.secondary)),
                          for (final t in _tries)
                            ActionChip(
                              label: Text(t, style: const TextStyle(fontSize: 13)),
                              visualDensity: VisualDensity.compact,
                              onPressed: () => _search(t),
                            ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 18),
                    _ChipRow(
                      label: 'Where',
                      values: [for (final j in _jurisdictions) (j, j.isEmpty ? 'Everywhere' : jurisdictionName(j))],
                      selected: jurisdiction,
                      onSelected: (v) => setState(() => jurisdiction = v),
                    ),
                    const SizedBox(height: 6),
                    _ChipRow(
                      label: 'Kind',
                      values: [for (final e in _kinds.entries) (e.key, e.value)],
                      selected: kind,
                      onSelected: (v) => setState(() => kind = v),
                    ),
                  ],
                ),
              ),
            ),
            // what the law says: laws whose sections are about the subject, with the sections themselves
            if (q.length >= 2) ...[
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(24, 24, 24, 10),
                sliver: SliverToBoxAdapter(
                  child: _SectionHead(
                    title: 'Laws that deal with “$q”',
                    note: 'From section headings: each law with the sections that say it, the most relied-on first.',
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                sliver: ref.watch(subjectProvider(query)).when(
                      loading: () => const SliverToBoxAdapter(child: LoadingStructure()),
                      error: (e, s) => SliverToBoxAdapter(
                        child: LoadFailure(e, onRetry: () => ref.invalidate(subjectProvider(query))),
                      ),
                      data: (page) => page.items.isEmpty
                          ? SliverToBoxAdapter(
                              child: Notice('No section heading mentions “$q”. Titles are listed below.'),
                            )
                          : SliverList.builder(
                              itemCount: page.items.length,
                              itemBuilder: (context, i) => Padding(
                                padding: const EdgeInsets.only(bottom: 12),
                                child: _SubjectCard(hit: page.items[i]),
                              ),
                            ),
                    ),
              ),
            ],
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 10),
              sliver: SliverToBoxAdapter(
                child: _SectionHead(
                  title: _listTitle,
                  note: q.isEmpty ? 'Most relied-on first: ordered by how many other laws cite them.' : null,
                ),
              ),
            ),
            result.when(
              loading: () => const SliverPadding(
                padding: EdgeInsets.symmetric(horizontal: 24),
                sliver: SliverToBoxAdapter(child: LoadingStructure()),
              ),
              error: (error, stack) => SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                sliver: SliverToBoxAdapter(
                  child: LoadFailure(error, onRetry: () => ref.invalidate(catalogueProvider(query))),
                ),
              ),
              data: (page) => page.items.isEmpty
                  ? SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      sliver: SliverToBoxAdapter(
                        child: Notice(q.isEmpty
                            ? 'No law of this kind is held for this jurisdiction. That is not proof none exists.'
                            : 'No title contains “$q”. Unavailable records are not proof that no such law exists.'),
                      ),
                    )
                  : SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      sliver: SliverList.builder(
                        itemCount: page.items.length,
                        itemBuilder: (context, index) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: InstrumentCard(page.items[index]),
                        ),
                      ),
                    ),
            ),
            if (result.valueOrNull case final page?)
              SliverToBoxAdapter(
                child: MoreButton(
                  page,
                  refresh: () => ref.invalidate(catalogueProvider(query)),
                  load: () => ref.read(catalogueProvider(query).notifier).more(),
                ),
              ),
            const SliverToBoxAdapter(child: SizedBox(height: 120)),
          ],
        ),
      ),
    );
  }
}

class _SectionHead extends StatelessWidget {
  final String title;
  final String? note;
  const _SectionHead({required this.title, this.note});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          if (note != null) ...[
            const SizedBox(height: 4),
            Text(note!, style: TextStyle(fontSize: 12.5, height: 1.4, color: Theme.of(context).colorScheme.secondary)),
          ],
        ],
      );
}

/// A one-tap filter: a labelled row of chips that scrolls sideways on a phone.
class _ChipRow extends StatelessWidget {
  final String label;
  final List<(String, String)> values;
  final String selected;
  final ValueChanged<String> onSelected;
  const _ChipRow({required this.label, required this.values, required this.selected, required this.onSelected});
  @override
  Widget build(BuildContext context) => Row(
        children: [
          SizedBox(
            width: 46,
            child: Text(label.toUpperCase(),
                style: TextStyle(fontSize: 10, letterSpacing: 1.2, color: Theme.of(context).colorScheme.secondary)),
          ),
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final (value, text) in values)
                    Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: ChoiceChip(
                        label: Text(text, style: const TextStyle(fontSize: 13)),
                        selected: selected == value,
                        visualDensity: VisualDensity.compact,
                        onSelected: (_) => onSelected(value),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      );
}

IconData _kindIcon(String kind) => switch (kind) {
      'constitution' => Icons.account_balance_outlined,
      'act' => Icons.gavel_outlined,
      'ordinance' => Icons.history_edu_outlined,
      'rules' || 'regulation' => Icons.rule_outlined,
      'order' => Icons.assignment_outlined,
      'sro' || 'notification' => Icons.campaign_outlined,
      _ => Icons.description_outlined,
    };

/// How much the corpus relies on a law, as a short meter: cited by N other laws, on a log scale to 2,500.
class _Reliance extends StatelessWidget {
  final int? cited;
  const _Reliance(this.cited);
  @override
  Widget build(BuildContext context) {
    final n = cited ?? 0;
    if (n == 0) return const SizedBox.shrink();
    final scheme = Theme.of(context).colorScheme;
    final share = (math.log(1 + n) / math.log(2500)).clamp(0.05, 1.0);
    return Row(
      children: [
        SizedBox(
          width: 64,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: share,
              minHeight: 5,
              backgroundColor: scheme.outline.withValues(alpha: .35),
              color: scheme.secondary,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Text('Cited in ${_count(n)} law${n == 1 ? '' : 's'}', style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}

String _count(int n) => n >= 1000 ? '${n ~/ 1000},${(n % 1000).toString().padLeft(3, '0')}' : '$n';

/// A law in a list: what it is, where, when, its standing, and how much the rest of the law relies on it.
class InstrumentCard extends StatelessWidget {
  final law.Instrument item;
  const InstrumentCard(this.item, {super.key});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final wording = instrumentWording(item);
    return Material(
      color: scheme.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: scheme.outline)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(item.kind == 'constitution' && item.document_id == 4419
            ? '/constitution'
            : '/instrument/${item.id}'),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 12, 16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(color: scheme.secondary.withValues(alpha: .1), shape: BoxShape.circle),
                child: Icon(_kindIcon(item.kind), size: 20, color: scheme.secondary),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Eyebrow('${jurisdictionName(item.jurisdiction)} · ${unitNoun('', item.kind)} · ${item.year_display}'),
                    const SizedBox(height: 6),
                    Text(item.title ?? 'Untitled source record',
                        style: const TextStyle(fontFamily: 'Spectral', fontSize: 19, height: 1.25)),
                    const SizedBox(height: 8),
                    Text(wording.title, style: const TextStyle(fontSize: 12)),
                    if ((item.cited_by_laws ?? 0) > 0) ...[
                      const SizedBox(height: 6),
                      _Reliance(item.cited_by_laws),
                    ],
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}

/// A law that deals with the subject searched, with the sections that say it -- each opens in the reader.
class _SubjectCard extends StatelessWidget {
  final law.SubjectHit hit;
  const _SubjectCard({required this.hit});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final item = hit.instrument;
    return Material(
      color: scheme.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: scheme.outline)),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => context.push('/instrument/${item.id}'),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 12, 10),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Eyebrow('${jurisdictionName(item.jurisdiction)} · ${item.year_display}'),
                        const SizedBox(height: 6),
                        Text(item.title ?? 'Untitled source record',
                            style: const TextStyle(fontFamily: 'Spectral', fontSize: 19, height: 1.25)),
                        const SizedBox(height: 6),
                        _Reliance(item.cited_by_laws),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right),
                ],
              ),
            ),
          ),
          Divider(height: 1, color: scheme.outline),
          for (final u in hit.units)
            InkWell(
              onTap: () => context.push('/provision/${u.id}'),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
                child: Row(
                  children: [
                    SizedBox(
                      width: 52,
                      child: Text(
                        printedLabel(u.kind, u.label),
                        style: TextStyle(fontFamily: 'Spectral', fontSize: 16, color: scheme.secondary),
                      ),
                    ),
                    Expanded(child: Text(u.heading ?? '', style: const TextStyle(fontSize: 14, height: 1.35))),
                    Icon(Icons.arrow_forward, size: 16, color: scheme.secondary),
                  ],
                ),
              ),
            ),
          if (hit.matches > hit.units.length)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 2, 16, 12),
              child: Text('${hit.matches - hit.units.length} more matching sections in this law',
                  style: TextStyle(fontSize: 12, color: scheme.secondary)),
            ),
        ],
      ),
    );
  }
}
