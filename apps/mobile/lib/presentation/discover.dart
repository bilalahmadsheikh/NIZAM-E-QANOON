import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../state/library_state.dart';
import 'package:go_router/go_router.dart';
import '../design/components.dart';
import '../design/monument.dart';
import '../design/theme.dart';
import 'popular.dart';

class DiscoverScreen extends StatelessWidget {
  const DiscoverScreen({super.key});
  @override
  Widget build(BuildContext context) => LibraryScaffold(
    title: 'Nizam-e-Qanoon',
    selected: 0,
    body: ReadingWidth(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Eyebrow('A living library of Pakistani law'),
          const SizedBox(height: 16),
          Text(
            'The law.\nA little closer.',
            style: Theme.of(context).textTheme.displaySmall,
          ),
          const SizedBox(height: 16),
          Text(
            'Find the instrument. Follow its structure. Read the source.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 28),
          Container(
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              color: Stamp.pine,
              borderRadius: BorderRadius.circular(28),
            ),
            child: Column(
              children: [
                const SizedBox(
                  height: 230,
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: 300 / 280,
                      child: MonumentScene(),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'BEGIN WITH THE CONSTITUTION',
                        style: TextStyle(
                          color: Color(0xFFD4A557),
                          fontSize: 10,
                          letterSpacing: 1.7,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'The foundations\nof our republic.',
                        style: TextStyle(
                          fontFamily: 'Spectral',
                          fontSize: 30,
                          height: 1.15,
                          color: Stamp.parchment,
                        ),
                      ),
                      const SizedBox(height: 18),
                      FilledButton.icon(
                        style: FilledButton.styleFrom(
                          backgroundColor: Stamp.parchment,
                          foregroundColor: Stamp.pine,
                        ),
                        onPressed: () => context.push('/constitution'),
                        icon: const Icon(Icons.arrow_forward),
                        label: const Text('Explore constitutional texts'),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'The Constitution, its Parts and amendments, and the constitutions before it, on one page.',
                        style: TextStyle(
                          color: Color(0xFFD2DBD3),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),
          const PopularCarousel(),
          const SizedBox(height: 36),
          const _FindByTitle(),
          const SizedBox(height: 36),
          Text('Browse by jurisdiction', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          const Text(
            'Federal law applies across Pakistan; each province and territory also makes its own.',
            style: TextStyle(fontSize: 13, height: 1.4),
          ),
          const SizedBox(height: 14),
          LayoutBuilder(
            builder: (context, box) {
              final columns = box.maxWidth >= 640 ? 4 : 2;
              final width = (box.maxWidth - 12 * (columns - 1)) / columns;
              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  for (final (key, note) in const [
                    ('fed', 'Acts of Parliament, Ordinances, Orders'),
                    ('punjab', 'Provincial Assembly'),
                    ('sindh', 'Provincial Assembly'),
                    ('kp', 'Provincial Assembly'),
                    ('balochistan', 'Provincial Assembly'),
                    ('ict', 'Islamabad Capital Territory'),
                    ('ajk', 'Azad Jammu and Kashmir'),
                    ('gb', 'Gilgit-Baltistan'),
                  ])
                    SizedBox(width: width, child: _Tile(jurisdiction: key, note: note)),
                ],
              );
            },
          ),
          const SizedBox(height: 36),
          Text('Browse by kind of law', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final (kind, label) in const [
                ('act', 'Acts'),
                ('ordinance', 'Ordinances'),
                ('order', 'Orders'),
                ('rules', 'Rules'),
                ('regulation', 'Regulations'),
                ('notification', 'Notifications'),
              ])
                ActionChip(
                  label: Text(label),
                  onPressed: () => context.push('/library?kind=$kind'),
                ),
            ],
          ),
          const SizedBox(height: 36),
          Text('Topics', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          const Text(
            'Each topic searches law titles. It is a way in, not a complete list of the laws that apply.',
            style: TextStyle(fontSize: 13, height: 1.4),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final (q, label) in const [
                ('Family', 'Family'),
                ('Rent', 'Rent and tenancy'),
                ('Land Revenue', 'Land revenue'),
                ('Police', 'Police'),
                ('Income Tax', 'Income tax'),
                ('Labour', 'Labour'),
                ('Consumer', 'Consumers'),
                ('Economic Corridor', 'CPEC'),
              ])
                ActionChip(
                  avatar: const Icon(Icons.search, size: 16),
                  label: Text(label),
                  onPressed: () => context.push('/library?q=${Uri.encodeQueryComponent(q)}'),
                ),
            ],
          ),
          const SizedBox(height: 32),
          const Notice(
            'Development preview: the corpus is still being qualified. A record passing current gates is not a legal accuracy certification. Always inspect its official source.',
          ),
          const SizedBox(height: 20),
        ],
      ),
    ),
  );
}

/// Search law titles from the home page; the library opens with the query.
class _FindByTitle extends StatefulWidget {
  const _FindByTitle();
  @override
  State<_FindByTitle> createState() => _FindByTitleState();
}

class _FindByTitleState extends State<_FindByTitle> {
  final _query = TextEditingController();
  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  void _go() {
    final q = _query.text.trim();
    context.push(q.isEmpty ? '/library' : '/library?q=${Uri.encodeQueryComponent(q)}');
  }

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Find a law by its title', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          TextField(
            controller: _query,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _go(),
            decoration: InputDecoration(
              hintText: 'Penal code, tenancy, evidence…',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: IconButton(tooltip: 'Search titles', onPressed: _go, icon: const Icon(Icons.arrow_forward)),
            ),
          ),
        ],
      );
}

/// A jurisdiction: its name and what its laws are, opening the library filtered to it.
class _Tile extends StatelessWidget {
  final String jurisdiction;
  final String note;
  const _Tile({required this.jurisdiction, required this.note});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: scheme.outline)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push('/library?jurisdiction=$jurisdiction'),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 14, 10, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(jurisdictionName(jurisdiction),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontFamily: 'Spectral', fontSize: 19, height: 1.2)),
              const SizedBox(height: 4),
              Text(note, maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 12, height: 1.35, color: scheme.onSurface.withValues(alpha: .75))),
            ],
          ),
        ),
      ),
    );
  }
}

class HeritageScreen extends ConsumerWidget {
  const HeritageScreen({super.key});
  static final source = Uri.parse('https://na.gov.pk/en/content.php?id=75');
  @override
  Widget build(BuildContext context, WidgetRef ref) => LibraryScaffold(
    title: 'Heritage & the law',
    selected: 2,
    body: ReadingWidth(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Eyebrow('Places, people, institutions'),
          const SizedBox(height: 16),
          Text(
            'A republic,\nwritten over time.',
            style: Theme.of(context).textTheme.displaySmall,
          ),
          const SizedBox(height: 24),
          Container(
            height: 260,
            decoration: BoxDecoration(
              color: Stamp.pine,
              borderRadius: BorderRadius.circular(28),
            ),
            child: const Center(
              child: AspectRatio(
                aspectRatio: 300 / 280,
                child: MonumentScene(mausoleum: true),
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Mazar-e-Quaid · stylised architectural illustration',
            style: TextStyle(fontSize: 12),
          ),
          const SizedBox(height: 28),
          const Notice(
            'Historical context, separate from operative law. These short editorial notes do not determine the legal status of a provision.',
          ),
          const SizedBox(height: 24),
          for (final entry in const [
            (
              '1956',
              'The first Constitution',
              'Pakistan’s first Constitution established a parliamentary form of government.',
            ),
            (
              '1962',
              'A different constitutional design',
              'The 1962 Constitution provided a presidential form of government.',
            ),
            (
              '1973',
              'A bicameral Parliament',
              'The 1973 Constitution established a parliamentary system with the National Assembly and Senate.',
            ),
          ]) ...[
            PaperCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Eyebrow(entry.$1),
                  const SizedBox(height: 12),
                  Text(entry.$2, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 12),
                  Text(entry.$3, style: const TextStyle(height: 1.6)),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          OutlinedButton.icon(
            onPressed: () async {
              if (!await ref
                      .read(sourceActionsProvider)
                      .open(source.toString()) &&
                  context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'Unable to open the source. Visit na.gov.pk, Parliamentary History.',
                    ),
                  ),
                );
              }
            },
            icon: const Icon(Icons.open_in_new),
            label: const Text('Source: National Assembly history'),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () => context.push('/constitution'),
            child: const Text('Browse constitutional texts'),
          ),
          const SizedBox(height: 24),
        ],
      ),
    ),
  );
}
