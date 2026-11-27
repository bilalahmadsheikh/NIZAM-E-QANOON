import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../design/embroidery.dart';
import '../design/heritage_art.dart';
import '../domain/heritage.dart';
import '../state/library_state.dart';
import 'library.dart';

/// Heritage (D-077): Pakistan's places, region by region, and the law that protects them.
///
/// Each region shows a landmark and a craft (editorial context, domain/heritage.dart, every fact sourced) beside the
/// heritage laws the library holds for that jurisdiction and the questions people bring to heritage law, answered by
/// opening the law's own sections (nizam/api/collections.py). The two are kept visibly apart: the context never says
/// what the law requires; the law is the database's.
class HeritageScreen extends ConsumerStatefulWidget {
  /// The region to open on (`/heritage?region=sindh`); otherwise the reader's own territory, else Punjab.
  final String? region;
  const HeritageScreen({super.key, this.region});
  @override
  ConsumerState<HeritageScreen> createState() => _HeritageScreenState();
}

class _HeritageScreenState extends ConsumerState<HeritageScreen> {
  // a linked region first, then the reader's own territory, when they have chosen one
  late String region = heritageRegion(widget.region ?? '') != null
      ? widget.region!
      : heritageRegion(ref.read(territoryProvider)) == null
          ? 'punjab'
          : ref.read(territoryProvider);

  @override
  Widget build(BuildContext context) {
    final page = ref.watch(heritageProvider);
    final chosen = heritageRegion(region)!;
    final still = MediaQuery.disableAnimationsOf(context);
    return LibraryScaffold(
      title: 'Heritage',
      selected: 3,
      body: ReadingWidth(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(0, 24, 0, 120),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // the chosen region's craft as a patch beside the headline; it changes with the region (D-084)
                  PatchedHeader(
                    key: ValueKey('patch-$region'),
                    motif: chosen.crafts.isEmpty ? chosen.motif : chosen.crafts.first.motif,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Eyebrow('Places, crafts and the law that keeps them'),
                        const SizedBox(height: 14),
                        Text('Pakistan,\nregion by region.', style: Theme.of(context).textTheme.displaySmall),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'A landmark and a craft of each region, beside the heritage laws the library holds for it, and '
                    'the questions people bring to those laws.',
                    style: TextStyle(height: 1.5),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            _RegionPicker(selected: region, onSelected: (r) => setState(() => region = r)),
            const SizedBox(height: 20),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: AnimatedSwitcher(
                duration: Duration(milliseconds: still ? 0 : 220),
                switchInCurve: Curves.easeOutCubic,
                child: _RegionPanel(
                  key: ValueKey(region),
                  region: chosen,
                  laws: page.whenData((p) => p.regions.where((r) => r.jurisdiction == region).firstOrNull),
                  onRetry: () => ref.invalidate(heritageProvider),
                ),
              ),
            ),
            const SizedBox(height: 36),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: page.when(
                loading: () => const LoadingStructure(),
                error: (e, s) => const SizedBox.shrink(), // the region panel above already offers the retry
                // the chosen region's own law answers (D-078); switches with the region
                data: (p) => _Questions(
                  key: ValueKey('questions-$region'),
                  region: p.regions.where((r) => r.jurisdiction == region).firstOrNull,
                ),
              ),
            ),
            // the law that protects what Pakistan makes (D-079): federal, the same for every region
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: page.maybeWhen(
                data: (p) => p.makers.laws.isEmpty ? const SizedBox.shrink() : _Makers(makers: p.makers),
                orElse: () => const SizedBox.shrink(),
              ),
            ),
            const SizedBox(height: 36),
            const Padding(padding: EdgeInsets.symmetric(horizontal: 24), child: _ConstitutionalHeritage()),
            const SizedBox(height: 28),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24),
              child: Notice(
                'The notes on places and crafts are editorial context, each linked to its source. They do not say what '
                'the law requires; the laws and sections listed here are reproduced from the database.',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The eight regions as medallions: each one's landmark on the pine ground, its name below. Scrolls sideways.
class _RegionPicker extends StatelessWidget {
  final String selected;
  final ValueChanged<String> onSelected;
  const _RegionPicker({required this.selected, required this.onSelected});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 120,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: heritageRegions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, i) {
          final r = heritageRegions[i];
          final on = r.jurisdiction == selected;
          return Semantics(
            button: true,
            selected: on,
            label: jurisdictionName(r.jurisdiction),
            child: InkWell(
              borderRadius: BorderRadius.circular(18),
              onTap: () => onSelected(r.jurisdiction),
              child: SizedBox(
                width: 78,
                child: Column(
                  children: [
                    const SizedBox(height: 4),
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 160),
                      width: 60,
                      height: 60,
                      padding: const EdgeInsets.all(7),
                      decoration: BoxDecoration(
                        color: const Color(0xFF17352E),
                        shape: BoxShape.circle,
                        border: Border.all(color: on ? const Color(0xFFB8873C) : Colors.transparent, width: 2.5),
                      ),
                      child: LandmarkArt(r.landmark, size: 44),
                    ),
                    const SizedBox(height: 6),
                    ExcludeSemantics(
                      child: Text(
                        jurisdictionName(r.jurisdiction),
                        maxLines: 2,
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: on ? FontWeight.w700 : FontWeight.w500,
                          color: on ? scheme.onSurface : scheme.onSurface.withValues(alpha: .7),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

/// One region: its landmark scene and note, its craft, and the heritage laws the library holds for it.
class _RegionPanel extends ConsumerWidget {
  final HeritageRegion region;
  final AsyncValue<law.HeritageRegion?> laws;
  final VoidCallback onRetry;
  const _RegionPanel({super.key, required this.region, required this.laws, required this.onRetry});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LandmarkScene(region, height: 230),
        const SizedBox(height: 18),
        Eyebrow(jurisdictionName(region.jurisdiction)),
        const SizedBox(height: 8),
        Text(region.place, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 2),
        Text(region.location, style: TextStyle(color: scheme.secondary)),
        const SizedBox(height: 10),
        Text(region.note, style: const TextStyle(height: 1.55)),
        _Sources(urls: region.sources),
        if (region.crafts.isNotEmpty) ...[
          const SizedBox(height: 22),
          Text('Crafts and makers', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          for (final craft in region.crafts)
            Padding(padding: const EdgeInsets.only(bottom: 8), child: _CraftRow(craft: craft)),
        ],
        const SizedBox(height: 26),
        Text('The law that protects heritage here', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 10),
        laws.when(
          loading: () => const LoadingStructure(),
          error: (e, s) => LoadFailure(e, onRetry: onRetry),
          data: (r) {
            if (r == null || r.laws.isEmpty) {
              return Notice(
                'The library does not yet hold a heritage law of ${jurisdictionName(region.jurisdiction)}. '
                'That is not proof none exists.',
                icon: Icons.search_off,
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (r.laws_from != r.jurisdiction) ...[
                  Text(
                    '${jurisdictionName(r.jurisdiction)} Capital Territory is served federal law: these are the '
                    'federal heritage laws.',
                    style: const TextStyle(fontSize: 13, height: 1.45),
                  ),
                  const SizedBox(height: 10),
                ],
                for (final l in r.laws) _LawRow(item: l),
              ],
            );
          },
        ),
      ],
    );
  }
}

/// A craft of the region: its motif as a swatch, its name and town, one line, and where that was checked.
class _CraftRow extends StatelessWidget {
  final Craft craft;
  const _CraftRow({required this.craft});
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: solidTint(context),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            MotifSwatch(craft.motif, size: 44),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text((craft.town ?? 'Craft').toUpperCase(), style: TextStyle(fontSize: 10, letterSpacing: 1.6,
                      color: Theme.of(context).colorScheme.secondary, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 3),
                  Text(craft.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 3),
                  Text(craft.note, style: const TextStyle(fontSize: 13, height: 1.45)),
                  _Sources(urls: [craft.source]),
                ],
              ),
            ),
          ],
        ),
      );
}

/// Source links, each named by its site.
class _Sources extends ConsumerWidget {
  final List<String> urls;
  const _Sources({required this.urls});
  @override
  Widget build(BuildContext context, WidgetRef ref) => Wrap(
        spacing: 4,
        children: [
          for (final url in urls)
            TextButton.icon(
              style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 6),
                  visualDensity: VisualDensity.compact),
              onPressed: () async {
                if (!await ref.read(sourceActionsProvider).open(url) && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Unable to open $url')));
                }
              },
              icon: const Icon(Icons.open_in_new, size: 14),
              label: Text('Source: ${_sourceName(url, urls)}',
                  style: const TextStyle(fontSize: 12)),
            ),
        ],
      );
}

/// A source named by its site; where two sources share a site, by the page's own name instead
/// ('en.wikipedia.org' twice says nothing; 'Badshahi Mosque' and 'List of World Heritage Sites in Pakistan' do).
String _sourceName(String url, List<String> all) {
  final uri = Uri.parse(url);
  final host = uri.host.replaceFirst('www.', '');
  if (all.where((u) => Uri.parse(u).host == uri.host).length < 2 || uri.pathSegments.isEmpty) return host;
  final page = Uri.decodeComponent(uri.pathSegments.last).replaceAll('_', ' ');
  return page.length > 40 ? '${page.substring(0, 39)}…' : page;
}

/// A heritage law: its short name, full title and year, and its recorded standing; opens the law.
class _LawRow extends StatelessWidget {
  final law.HeritageLaw item;
  const _LawRow({required this.item});
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
                      const SizedBox(height: 4),
                      Text(instrumentWording(i).title,
                          style: TextStyle(fontSize: 12, color: scheme.secondary)),
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

/// Questions people bring to heritage law, each answered by the chosen region's own law, read in that region
/// (D-078). The culture right is the Constitution's, shown last under its own head where it is served. A region
/// whose law has no section on a question does not ask it; one with no heritage law asks nothing.
class _Questions extends StatelessWidget {
  final law.HeritageRegion? region;
  const _Questions({super.key, required this.region});
  @override
  Widget build(BuildContext context) {
    final questions = region?.questions ?? const <law.HeritageQuestion>[];
    final antiquities = questions.where((q) => q.key != 'culture_right').toList();
    final culture = questions.where((q) => q.key == 'culture_right').firstOrNull;
    // every antiquities question of a region comes from one law; name it once, by its record ('the' is the
    // sentence's own: 'in the Balochistan Antiquities Act, 2014', never 'in the The ...')
    final laws = {
      for (final q in antiquities) (q.instrument.title ?? '').replaceFirst(RegExp(r'^the\s+', caseSensitive: false), '')
    }..remove('');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (antiquities.isNotEmpty) ...[
          Text('Questions people ask', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            [
              'Each opens the sections that deal with it',
              if (laws.length == 1) ' in the ${laws.first}',
              if (region!.laws_from != region!.jurisdiction) ', the federal law that runs here',
              '. Read the section itself: a heading is only its name.',
            ].join(),
            style: const TextStyle(height: 1.45),
          ),
          const SizedBox(height: 14),
          for (final q in antiquities) _QuestionCard(question: q),
        ],
        if (culture != null) ...[
          const SizedBox(height: 22),
          Text('The Constitution on culture', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          _QuestionCard(question: culture),
        ],
      ],
    );
  }
}

class _QuestionCard extends StatelessWidget {
  final law.HeritageQuestion question;
  const _QuestionCard({required this.question});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        decoration: BoxDecoration(
          color: scheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: scheme.outline),
        ),
        padding: const EdgeInsets.fromLTRB(16, 14, 8, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Text(heritageQuestion(question.key),
                  style: const TextStyle(fontFamily: 'Spectral', fontSize: 18, height: 1.3)),
            ),
            const SizedBox(height: 6),
            for (final u in question.units)
              InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => context.push('/provision/${u.id}'),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // the citation and heading are records (INV-1); bidi-isolated so 's. 5A' stays whole
                            Text('${String.fromCharCode(0x2068)}${u.citation ?? ''}${String.fromCharCode(0x2069)}',
                                style: TextStyle(fontSize: 12, color: scheme.secondary, fontWeight: FontWeight.w600)),
                            if (u.heading != null)
                              Text(u.heading!, style: const TextStyle(fontSize: 14, height: 1.35))
                            // no printed heading (the Balochistan and AJK Acts): the section's own opening words,
                            // served text, set as a quotation so they are not read as a name
                            else if (u.preview != null)
                              Text('“${u.preview!}”', maxLines: 2, overflow: TextOverflow.ellipsis,
                                  style: TextStyle(fontSize: 13, height: 1.4, fontFamily: 'Spectral',
                                      color: scheme.onSurface.withValues(alpha: .8))),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, size: 20),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Protecting what Pakistan makes (D-079): the federal laws a maker of a craft or a regional product relies on, one
/// sourced fact about the first registered geographical indication, and the questions makers ask, answered by
/// sections. The fact is editorial context; the laws and sections are the database's.
class _Makers extends StatelessWidget {
  final law.HeritageMakers makers;
  const _Makers({required this.makers});
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 36),
        // the crafts' threads in one hem: what this law protects (D-082)
        const EmbroideredBorder(Motif.truckArt, height: 16),
        const SizedBox(height: 16),
        Text('Protecting what Pakistan makes', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 6),
        const Text(
          'A craft, a regional product or a workshop’s name can be protected by federal law: geographical '
          'indications, trade marks, designs and copyright.',
          style: TextStyle(height: 1.45),
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 10, 6),
          decoration: BoxDecoration(
            color: solidTint(context),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(giFirst.note, style: const TextStyle(fontSize: 13, height: 1.45)),
              _Sources(urls: [giFirst.source]),
            ],
          ),
        ),
        const SizedBox(height: 14),
        for (final l in makers.laws) _LawRow(item: l),
        const SizedBox(height: 10),
        for (final q in makers.questions) _QuestionCard(question: q),
      ],
    );
  }
}

/// The republic's own constitutional history, kept from the first Heritage page with its source.
class _ConstitutionalHeritage extends ConsumerWidget {
  const _ConstitutionalHeritage();
  static const source = 'https://na.gov.pk/en/content.php?id=75';
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('A republic, written over time', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 14),
        for (final (year, title, note) in const [
          ('1956', 'The first Constitution', 'Pakistan’s first Constitution established a parliamentary form of government.'),
          ('1962', 'A different design', 'The 1962 Constitution provided a presidential form of government.'),
          ('1973', 'A bicameral Parliament',
              'The 1973 Constitution established a parliamentary system with the National Assembly and Senate.'),
        ])
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(
                  width: 58,
                  child: Text(year, style: TextStyle(fontFamily: 'Spectral', fontSize: 20, color: scheme.secondary)),
                ),
                Container(width: 2, color: scheme.secondary.withValues(alpha: .25)),
                const SizedBox(width: 14),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                        const SizedBox(height: 4),
                        Text(note, style: const TextStyle(height: 1.5)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        const _Sources(urls: [source]),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: () => context.push('/constitution'),
          icon: const Icon(Icons.arrow_forward),
          label: const Text('The Constitution today'),
        ),
      ],
    );
  }
}
