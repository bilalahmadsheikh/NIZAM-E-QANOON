import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../state/library_state.dart';
import 'library.dart';

class ProvisionScreen extends ConsumerWidget {
  final String id;
  const ProvisionScreen({super.key, required this.id});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(provisionProvider(id));
    return LibraryScaffold(
      title: 'Read the source',
      actions: [
        IconButton(
          tooltip: 'Reading settings',
          icon: const Icon(Icons.text_fields),
          onPressed: () => _settings(context),
        ),
      ],
      body: ReadingWidth(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.all(24),
              sliver: SliverToBoxAdapter(
                child: result.when(
                  loading: () => const LoadingStructure(),
                  error:
                      (e, s) => LoadFailure(
                        e,
                        onRetry: () => ref.invalidate(provisionProvider(id)),
                      ),
                  data: (response) {
                    final item = response.item;
                    final urdu = ref.watch(urduContentProvider);
                    final text = urdu ? item.text_ur : item.text_en;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Wrap(
                          crossAxisAlignment: WrapCrossAlignment.center,
                          spacing: 4,
                          children: [
                            TextButton(
                              onPressed:
                                  () => context.push(
                                    '/instrument/${item.instrument_id}',
                                  ),
                              child: const Text('Instrument'),
                            ),
                            for (final ancestor in item.ancestors) ...[
                              const Icon(Icons.chevron_right, size: 14),
                              TextButton(
                                onPressed:
                                    () => context.push(
                                      '/provision/${ancestor.id}',
                                    ),
                                child: Text(
                                  '\u2068${ancestor.kind} ${ancestor.label ?? ""}\u2069',
                                ),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 16),
                        Eyebrow(
                          '${jurisdictionName(item.instrument.jurisdiction)} · ${item.kind}',
                        ),
                        const SizedBox(height: 12),
                        if (item.label != null)
                          Text(
                            '\u2068${item.label}\u2069',
                            style: TextStyle(
                              fontFamily: 'Spectral',
                              fontSize: 54,
                              height: 1.1,
                              color: Theme.of(context).colorScheme.secondary,
                            ),
                          ),
                        const SizedBox(height: 12),
                        Text(
                          item.heading ?? item.marginal_note ?? 'Source unit',
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          item.instrument.title ?? 'Untitled source record',
                          style: const TextStyle(fontSize: 14, height: 1.5),
                        ),
                        const SizedBox(height: 24),
                        StatusNote(item.instrument.status),
                        const SizedBox(height: 20),
                        if (item.operation == 'omitted')
                          const Padding(
                            padding: EdgeInsets.only(bottom: 20),
                            child: Notice(
                              'The stored version records an omission. This is not operative section text.',
                              icon: Icons.block,
                            ),
                          ),
                        PaperCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Expanded(
                                    child: Eyebrow('Stored source text'),
                                  ),
                                  IconButton(
                                    tooltip: 'Source and edition',
                                    onPressed:
                                        () => _source(
                                          context,
                                          item,
                                          response.as_of,
                                          ref,
                                        ),
                                    icon: const Icon(Icons.open_in_new),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              if (text != null && text.trim().isNotEmpty)
                                SelectableText(
                                  text,
                                  textDirection:
                                      urdu
                                          ? TextDirection.rtl
                                          : TextDirection.ltr,
                                  style: TextStyle(
                                    fontFamily:
                                        urdu
                                            ? 'Noto Nastaliq Urdu'
                                            : 'Spectral',
                                    fontSize:
                                        ref.watch(readerSizeProvider) +
                                        (urdu ? 2 : 0),
                                    height: urdu ? 2.1 : 1.7,
                                  ),
                                )
                              else
                                Text(
                                  urdu
                                      ? 'No Urdu source text is held for this unit. No translation has been substituted.'
                                      : item.has_children
                                      ? 'This structural unit has no separate text for the selected date. Read its child units below.'
                                      : 'No text version is held for the selected date. This does not establish that the provision did not exist.',
                                  style: const TextStyle(height: 1.6),
                                ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        OutlinedButton.icon(
                          onPressed:
                              () => _source(context, item, response.as_of, ref),
                          icon: const Icon(Icons.description_outlined),
                          label: const Text('Inspect source & edition'),
                        ),
                        const SizedBox(height: 24),
                        if (item.has_children) ...[
                          const Eyebrow('Within this unit'),
                          const SizedBox(height: 16),
                        ],
                        const SizedBox(height: 16),
                        const Notice(
                          'Legal information, not advice. Source text is reproduced from the database, not generated. Check the official PDF before relying on a citation.',
                        ),
                        const SizedBox(height: 24),
                      ],
                    );
                  },
                ),
              ),
            ),
            if (result.valueOrNull?.item.has_children == true)
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                sliver: ChildrenList(
                  instrument: result.value!.item.instrument_id,
                  parent: id,
                ),
              ),
          ],
        ),
      ),
    );
  }

  void _settings(BuildContext context) => showModalBottomSheet(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder:
        (context) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Consumer(
              builder:
                  (context, ref, child) => Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Make room to read',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Text size · ${ref.watch(readerSizeProvider).round()}',
                      ),
                      Slider(
                        min: 17,
                        max: 29,
                        divisions: 6,
                        value: ref.watch(readerSizeProvider),
                        onChanged:
                            (v) =>
                                ref.read(readerSizeProvider.notifier).state = v,
                      ),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Read held Urdu text'),
                        subtitle: const Text(
                          'Original source only, never automatic translation.',
                        ),
                        value: ref.watch(urduContentProvider),
                        onChanged:
                            (v) =>
                                ref.read(urduContentProvider.notifier).state =
                                    v,
                      ),
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Continue reading'),
                      ),
                    ],
                  ),
            ),
          ),
        ),
  );

  void _source(
    BuildContext context,
    law.Provision item,
    String asOf,
    WidgetRef ref,
  ) => showModalBottomSheet(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder:
        (context) => SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Eyebrow('Evidence, not an assertion'),
                const SizedBox(height: 12),
                Text(
                  'Source & edition',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 20),
                SelectableText(
                  item.instrument.title ?? 'Untitled source record',
                ),
                const SizedBox(height: 16),
                Text(
                  'PDF page: ${item.first_page ?? "not recorded"}\nSelected date: $asOf\nStored validity: ${item.valid_from ?? "not recorded"} → ${item.valid_to ?? "open end / not recorded"}',
                  style: const TextStyle(height: 1.8),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Source SHA-256',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                SelectableText(
                  item.instrument.source_hash,
                  style: const TextStyle(fontSize: 12),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Provision revision',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                SelectableText(item.id, style: const TextStyle(fontSize: 12)),
                const SizedBox(height: 20),
                if (item.instrument.source_url case final url?) ...[
                  SelectableText(url, style: const TextStyle(fontSize: 12)),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: () async {
                      final opened = await ref
                          .read(sourceActionsProvider)
                          .open(url, page: item.first_page);
                      if (!opened && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Could not open the source. You can copy its address.',
                            ),
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.open_in_new),
                    label: const Text('Open official source'),
                  ),
                  TextButton.icon(
                    onPressed: () async {
                      final copied = await ref
                          .read(sourceActionsProvider)
                          .copy(url);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              copied
                                  ? 'Source address copied.'
                                  : 'Clipboard unavailable. Select the address above.',
                            ),
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copy source address'),
                  ),
                ] else
                  const Notice(
                    'No official source URL is recorded for this edition.',
                  ),
                const SizedBox(height: 16),
                const Notice(
                  'This is a changing research corpus, not a pinned production release. Missing amendment history and source defects may remain.',
                ),
              ],
            ),
          ),
        ),
  );
}
