import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../state/library_state.dart';
import 'package:go_router/go_router.dart';
import '../design/components.dart';
import '../design/monument.dart';
import '../design/theme.dart';

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
                        onPressed:
                            () => context.push(
                              '/library?q=Constitution%20of&jurisdiction=fed',
                            ),
                        icon: const Icon(Icons.arrow_forward),
                        label: const Text('Explore constitutional texts'),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Choose the exact instrument and source edition.',
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
          Row(
            children: [
              Expanded(
                child: Text(
                  'Choose a starting point',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton(
                tooltip: 'Open all instruments',
                onPressed: () => context.go('/library'),
                icon: const Icon(Icons.arrow_forward),
              ),
            ],
          ),
          const SizedBox(height: 16),
          PaperCard(
            onTap: () => context.go('/library'),
            child: const Row(
              children: [
                Icon(Icons.auto_stories_outlined, size: 30),
                SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Browse the library',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      SizedBox(height: 6),
                      Text(
                        'Acts, ordinances, rules and more.\nFilter by jurisdiction and instrument type.',
                        style: TextStyle(height: 1.5),
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right),
              ],
            ),
          ),
          const SizedBox(height: 16),
          PaperCard(
            onTap: () => context.push('/library?q=Economic%20Corridor'),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Eyebrow('Topic discovery'),
                SizedBox(height: 12),
                Text(
                  'CPEC & economic corridors',
                  style: TextStyle(fontFamily: 'Spectral', fontSize: 23),
                ),
                SizedBox(height: 8),
                Text(
                  'Search titles in the held corpus. This is not yet a curated or exhaustive collection of applicable laws.',
                  style: TextStyle(height: 1.5),
                ),
                SizedBox(height: 16),
                Row(
                  children: [
                    Text('Explore matching titles'),
                    Spacer(),
                    Icon(Icons.arrow_forward),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Notice(
            'Development preview: the corpus is still being qualified. A record passing current gates is not a legal accuracy certification. Always inspect its official source.',
          ),
          const SizedBox(height: 20),
        ],
      ),
    ),
  );
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
            onPressed:
                () => context.push(
                  '/library?q=Constitution%20of&jurisdiction=fed',
                ),
            child: const Text('Browse constitutional texts'),
          ),
          const SizedBox(height: 24),
        ],
      ),
    ),
  );
}
