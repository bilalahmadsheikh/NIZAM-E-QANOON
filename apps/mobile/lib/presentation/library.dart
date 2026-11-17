import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../design/status_banner.dart';
import '../domain/law_status.dart';
import '../domain/law_units.dart';
import '../state/library_state.dart';
import 'sections.dart';
export '../domain/law_units.dart';

/// An instrument's standing from its serving record; an as-made text with none falls back to its stored status.
StatusWording instrumentWording(law.Instrument item) => item.currency != null
    ? lawStatusWording(currency: item.currency, reason: item.currency_reason)
    : lawStatusWording(
        currency: item.status == 'repealed' ? 'not_current' : null,
        reason: null,
      );

class CatalogueScreen extends ConsumerStatefulWidget {
  final String initialQuery;
  final String initialJurisdiction;
  final String initialKind;
  const CatalogueScreen({
    super.key,
    this.initialQuery = '',
    this.initialJurisdiction = '',
    this.initialKind = '',
  });
  @override
  ConsumerState<CatalogueScreen> createState() => _CatalogueScreenState();
}

class _CatalogueScreenState extends ConsumerState<CatalogueScreen> {
  late final TextEditingController search = TextEditingController(
    text: widget.initialQuery,
  );
  late String q = widget.initialQuery;
  late String jurisdiction = widget.initialJurisdiction;
  late String kind = widget.initialKind;
  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final query = (q: q, jurisdiction: jurisdiction, kind: kind);
    final result = ref.watch(catalogueProvider(query));
    return LibraryScaffold(
      title: 'The legal library',
      body: ReadingWidth(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 16),
              sliver: SliverToBoxAdapter(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Eyebrow('Find your way through the law'),
                    const SizedBox(height: 12),
                    Text(
                      'Every instrument.\nIts own story.',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Browse records available through the current release gates. Unavailable records are not proof that no such law exists.',
                      style: TextStyle(height: 1.5),
                    ),
                    const SizedBox(height: 24),
                    TextField(
                      controller: search,
                      textInputAction: TextInputAction.search,
                      onSubmitted: (value) => setState(() => q = value.trim()),
                      decoration: InputDecoration(
                        labelText: 'Search instrument titles',
                        hintText: 'Constitution, evidence, tenancy…',
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: IconButton(
                          tooltip: 'Search titles',
                          onPressed:
                              () => setState(() => q = search.text.trim()),
                          icon: const Icon(Icons.arrow_forward),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    LayoutBuilder(
                      builder: (context, constraints) {
                        final filters = [
                          _filter(
                            'Jurisdiction',
                            jurisdiction,
                            {
                              '': 'All jurisdictions',
                              for (final j in [
                                'fed',
                                'punjab',
                                'sindh',
                                'kp',
                                'balochistan',
                                'ict',
                                'ajk',
                                'gb',
                              ])
                                j: jurisdictionName(j),
                            },
                            (value) => setState(() => jurisdiction = value),
                          ),
                          _filter(
                            'Instrument type',
                            kind,
                            const {
                              '': 'All types',
                              'act': 'Acts',
                              'ordinance': 'Ordinances',
                              'constitution': 'Constitutions',
                              'rules': 'Rules',
                              'regulation': 'Regulations',
                              'order': 'Orders',
                              'sro': 'SROs',
                              'notification': 'Notifications',
                            },
                            (value) => setState(() => kind = value),
                          ),
                        ];
                        return constraints.maxWidth < 420
                            ? Column(
                              children: [
                                filters[0],
                                const SizedBox(height: 12),
                                filters[1],
                              ],
                            )
                            : Row(
                              children: [
                                Expanded(child: filters[0]),
                                const SizedBox(width: 16),
                                Expanded(child: filters[1]),
                              ],
                            );
                      },
                    ),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
            ),
            result.when(
              loading:
                  () => const SliverPadding(
                    padding: EdgeInsets.all(24),
                    sliver: SliverToBoxAdapter(child: LoadingStructure()),
                  ),
              error:
                  (error, stack) => SliverPadding(
                    padding: const EdgeInsets.all(24),
                    sliver: SliverToBoxAdapter(
                      child: LoadFailure(
                        error,
                        onRetry: () => ref.invalidate(catalogueProvider(query)),
                      ),
                    ),
                  ),
              data:
                  (page) =>
                      page.items.isEmpty
                          ? const SliverPadding(
                            padding: EdgeInsets.all(24),
                            sliver: SliverToBoxAdapter(
                              child: Notice(
                                'No matching instrument is available in this preview. Try a different title or remove filters.',
                              ),
                            ),
                          )
                          : SliverPadding(
                            padding: const EdgeInsets.symmetric(horizontal: 24),
                            sliver: SliverList.builder(
                              itemCount: page.items.length,
                              itemBuilder:
                                  (context, index) => Padding(
                                    padding: const EdgeInsets.only(bottom: 16),
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
                  load:
                      () => ref.read(catalogueProvider(query).notifier).more(),
                ),
              ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ),
      ),
    );
  }

  Widget _filter(
    String label,
    String value,
    Map<String, String> options,
    ValueChanged<String> changed,
  ) => DropdownButtonFormField<String>(
    value: value,
    isExpanded: true,
    decoration: InputDecoration(labelText: label),
    items:
        options.entries
            .map(
              (e) => DropdownMenuItem(
                value: e.key,
                child: Text(e.value, overflow: TextOverflow.ellipsis),
              ),
            )
            .toList(),
    onChanged: (v) => changed(v ?? ''),
  );
}

class InstrumentCard extends StatelessWidget {
  final law.Instrument item;
  const InstrumentCard(this.item, {super.key});
  @override
  Widget build(BuildContext context) => PaperCard(
    onTap: () => context.push('/instrument/${item.id}'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Eyebrow('${jurisdictionName(item.jurisdiction)} · ${item.kind}'),
        const SizedBox(height: 12),
        Text(
          item.title ?? 'Untitled source record',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(
              child: Text(
                instrumentWording(item).title,
                style: const TextStyle(fontSize: 12),
              ),
            ),
            const Icon(Icons.arrow_forward, size: 20),
          ],
        ),
      ],
    ),
  );
}

class ChildrenList extends ConsumerWidget {
  final String instrument;
  final String? parent;
  /// The law's stored kind, which names its units ('Article' in a constitution; domain/law_units.dart).
  final String instrumentKind;
  const ChildrenList({super.key, required this.instrument, this.parent, this.instrumentKind = ''});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = (instrument: instrument, parent: parent);
    return ref
        .watch(childrenProvider(query))
        .when(
          loading: () => const SliverToBoxAdapter(child: LoadingStructure()),
          error:
              (e, s) => SliverToBoxAdapter(
                child: LoadFailure(
                  e,
                  onRetry: () => ref.invalidate(childrenProvider(query)),
                ),
              ),
          data:
              (page) => SliverMainAxisGroup(
                slivers: [
                  if (page.items.isEmpty)
                    const SliverToBoxAdapter(
                      child: Notice('No child units are held for this node.'),
                    ),
                  SliverList.builder(
                    itemCount: page.items.length,
                    itemBuilder: (context, index) {
                      final node = page.items[index];
                      return Padding(
                        key: ValueKey('node/${node.id}'),
                        padding: const EdgeInsets.only(bottom: 12),
                        child: PaperCard(
                          onTap: () => context.push('/provision/${node.id}'),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              SizedBox(
                                width: 54,
                                // a long label ('XVIIA') shrinks to fit rather than wrap; an unnumbered unit
                                // whose label only repeats its kind ('Preamble') leaves the number slot empty,
                                // since the eyebrow beside it already names the kind
                                child: FittedBox(
                                  fit: BoxFit.scaleDown,
                                  alignment: Alignment.centerLeft,
                                  child: Text(
                                    (node.label ?? '').toLowerCase() ==
                                            node.kind.toLowerCase()
                                        ? ''
                                        : (node.label ?? '—'),
                                    maxLines: 1,
                                    style: TextStyle(
                                      fontFamily: 'Spectral',
                                      fontSize: 23,
                                      color: Theme.of(context)
                                          .colorScheme
                                          .secondary,
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      unitNoun(instrumentKind, node.kind).toUpperCase(),
                                      style: const TextStyle(
                                        fontSize: 10,
                                        letterSpacing: 1.3,
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    // the printed heading, else the division's printed title line (caption, D-070),
                                    // else the unit named by its kind -- never an empty card
                                    Text(
                                      node.heading ??
                                          node.marginal_note ??
                                          (node.caption == null ? null : captionCase(node.caption!)) ??
                                          (node.kind == 'preamble'
                                              ? 'The Preamble'
                                              : divisionTitle(instrumentKind, node.kind, node.label, null)),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        height: 1.4,
                                      ),
                                    ),
                                    if (node.has_children)
                                      const Padding(
                                        padding: EdgeInsets.only(top: 8),
                                        child: Text(
                                          'Contains further units',
                                          style: TextStyle(fontSize: 12),
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Icon(Icons.chevron_right),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                  SliverToBoxAdapter(
                    child: MoreButton(
                      page,
                      refresh: () => ref.invalidate(childrenProvider(query)),
                      load:
                          () =>
                              ref.read(childrenProvider(query).notifier).more(),
                    ),
                  ),
                ],
              ),
        );
  }
}

/// A law's page: its standing, then every served section (lazy, paged ahead of the scroll) -- or, switched, its
/// printed structure (Parts, Chapters) to walk down level by level.
class InstrumentScreen extends ConsumerStatefulWidget {
  final String id;
  const InstrumentScreen({super.key, required this.id});
  @override
  ConsumerState<InstrumentScreen> createState() => _InstrumentScreenState();
}

class _InstrumentScreenState extends ConsumerState<InstrumentScreen> {
  bool structure = false;
  String get id => widget.id;

  @override
  Widget build(BuildContext context) => LibraryScaffold(
    title: 'Law',
    body: ReadingWidth(
      child: CustomScrollView(
        // build rows well ahead of the viewport so a fast fling meets laid-out rows, not blank space
        cacheExtent: 1600,
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.all(24),
            sliver: SliverToBoxAdapter(
              child: ref
                  .watch(instrumentProvider(id))
                  .when(
                    loading: () => const LoadingStructure(),
                    error:
                        (e, s) => LoadFailure(
                          e,
                          onRetry: () => ref.invalidate(instrumentProvider(id)),
                        ),
                    data: (result) {
                      final item = result.item;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Eyebrow(
                            '${jurisdictionName(item.jurisdiction)} · ${item.kind}',
                          ),
                          const SizedBox(height: 16),
                          Text(
                            item.title ?? 'Untitled source record',
                            style: Theme.of(context).textTheme.headlineMedium,
                          ),
                          const SizedBox(height: 24),
                          StatusBanner(instrumentWording(item)),
                          const SizedBox(height: 20),
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  switch (ref.watch(sectionsHeadProvider(id))?.total) {
                                    null => captionCase(unitsNoun(item.kind, 2).toUpperCase()),
                                    final n => '$n ${unitsNoun(item.kind, n)} served on ${result.as_of}',
                                  },
                                  style: Theme.of(context).textTheme.titleLarge,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          SegmentedButton<bool>(
                            segments: [
                              ButtonSegment(
                                  value: false,
                                  icon: const Icon(Icons.view_agenda_outlined),
                                  label: Text(captionCase(unitsNoun(item.kind, 2).toUpperCase()))),
                              const ButtonSegment(
                                  value: true, icon: Icon(Icons.account_tree_outlined), label: Text('Structure')),
                            ],
                            selected: {structure},
                            onSelectionChanged: (s) => setState(() => structure = s.first),
                          ),
                          const SizedBox(height: 16),
                        ],
                      );
                    },
                  ),
            ),
          ),
          if (ref.watch(instrumentProvider(id)).valueOrNull case final result?)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 120),
              sliver: structure
                  ? ChildrenList(instrument: result.item.id, instrumentKind: result.item.kind)
                  : SectionList(instrument: result.item.id, instrumentKind: result.item.kind),
            ),
        ],
      ),
    ),
  );
}
