import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../domain/law_status.dart';
import '../state/library_state.dart';
import 'library.dart';

/// The home page's horizontal shelf of most-consulted laws (an editorial collection from the server, not a ranking
/// in law). One small request; cards are built lazily as the shelf scrolls, and opening one lands on a law whose
/// section index the server warmed at start-up.
class PopularCarousel extends ConsumerWidget {
  const PopularCarousel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final popular = ref.watch(popularProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Most consulted laws', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 6),
        const Text(
          'A starting shelf, not a ranking in law. Swipe for more.',
          style: TextStyle(fontSize: 13, height: 1.4),
        ),
        const SizedBox(height: 14),
        SizedBox(
          height: 184,
          child: popular.when(
            loading: () => ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: 3,
              separatorBuilder: (_, __) => const SizedBox(width: 12),
              itemBuilder: (_, __) => const _Placeholder(),
            ),
            error: (e, s) => LoadFailure(e, onRetry: () => ref.invalidate(popularProvider)),
            data: (page) => ListView.separated(
              scrollDirection: Axis.horizontal,
              // lay out a screen's worth beyond the edge so a swipe never meets an empty card
              cacheExtent: 600,
              itemCount: page.items.length,
              separatorBuilder: (_, __) => const SizedBox(width: 12),
              itemBuilder: (context, i) => _LawCard(entry: page.items[i]),
            ),
          ),
        ),
      ],
    );
  }
}

class _LawCard extends StatelessWidget {
  final law.CollectionItem entry;
  const _LawCard({required this.entry});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final item = entry.instrument;
    final wording = instrumentWording(item);
    return SizedBox(
      width: 210,
      child: Material(
        color: scheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: scheme.outline),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => context.push('/instrument/${item.id}'),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.short_name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontFamily: 'Spectral', fontSize: 26, color: scheme.secondary, height: 1.1),
                ),
                const SizedBox(height: 8),
                Text(
                  item.title ?? '',
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 14, height: 1.35, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                Text(
                  '${jurisdictionName(item.jurisdiction)} · ${item.year_display}',
                  style: const TextStyle(fontSize: 12),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(
                      wording.standing == Standing.inForce
                          ? Icons.verified_outlined
                          : wording.standing == Standing.presumed
                              ? Icons.help_outline
                              : Icons.block,
                      size: 14,
                      color: scheme.secondary,
                    ),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(wording.title, style: const TextStyle(fontSize: 12), overflow: TextOverflow.ellipsis),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder();
  @override
  Widget build(BuildContext context) => Container(
        width: 210,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: .25),
          borderRadius: BorderRadius.circular(20),
        ),
      );
}
