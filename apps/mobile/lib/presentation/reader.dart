import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../design/status_banner.dart';
import '../domain/law_status.dart';
import '../state/library_state.dart';
import 'library.dart';
import 'statute_text.dart';

/// The reader. One request returns the opened unit and everything under it as operative_provision serves it at the
/// chosen date and territory (INV-5), so a section reads as the statute prints it -- not one tap per sub-section.
/// Order: where you are (the law, then each Part and Chapter by its printed title), what it is, its legal standing
/// (StatusBanner, above the text), the text, then the units either side and its source.
const _containers = {'part', 'chapter', 'schedule', 'division', 'title', 'appendix', 'annexure'};

class ProvisionScreen extends ConsumerWidget {
  final String id;
  const ProvisionScreen({super.key, required this.id});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(unitTextProvider(id));
    final size = ref.watch(readerSizeProvider);
    final unit = result.valueOrNull;
    return LibraryScaffold(
      title: 'Read the law',
      actions: [
        IconButton(
          tooltip: 'Reading settings',
          icon: const Icon(Icons.text_fields),
          onPressed: () => _settings(context),
        ),
      ],
      body: ReadingWidth(
        child: SelectionArea(
          child: CustomScrollView(
            slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(24, 16, 24, 8),
                sliver: SliverToBoxAdapter(
                  child: result.when(
                    loading: () => const LoadingStructure(),
                    error: (e, s) => LoadFailure(e, onRetry: () => ref.invalidate(unitTextProvider(id))),
                    data: (u) => _Header(unit: u),
                  ),
                ),
              ),
              if (unit != null && unit.nodes.isNotEmpty)
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 8, 24, 8),
                  sliver: StatuteText(nodes: unit.nodes, size: size + ref.watch(readingModeProvider).sizeDelta),
                ),
              // a Part, Chapter or Schedule -- or a unit too long to show whole -- also lists its sub-units, so the
              // reader can jump in rather than scroll hundreds of rows
              if (unit != null && (unit.truncated || _containers.contains(unit.item.kind)) && unit.item.has_children) ...[
                const SliverPadding(
                  padding: EdgeInsets.fromLTRB(24, 24, 24, 12),
                  sliver: SliverToBoxAdapter(child: Eyebrow('Within this unit')),
                ),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  sliver: ChildrenList(
                      instrument: unit.item.instrument_id, parent: id, instrumentKind: unit.item.instrument.kind),
                ),
              ],
              if (unit != null)
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
                  sliver: SliverToBoxAdapter(child: _Neighbours(id: id, instrumentKind: unit.item.instrument.kind)),
                ),
              if (unit != null)
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(24, 16, 24, 120),
                  sliver: SliverToBoxAdapter(child: _Footer(unit: unit, onSource: () => _source(context, unit, ref))),
                ),
            ],
          ),
        ),
      ),
    );
  }

  void _settings(BuildContext context) => showModalBottomSheet(
        context: context,
        showDragHandle: true,
        isScrollControlled: true,
        builder: (context) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Consumer(
              builder: (context, ref, child) => Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Make room to read', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 24),
                  Text('Text size · ${ref.watch(readerSizeProvider).round()}'),
                  Slider(
                    min: 15,
                    max: 29,
                    divisions: 7,
                    value: ref.watch(readerSizeProvider),
                    onChanged: (v) => ref.read(readerSizeProvider.notifier).state = v,
                  ),
                  const SizedBox(height: 16),
                  FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Continue reading')),
                ],
              ),
            ),
          ),
        ),
      );

  void _source(BuildContext context, law.UnitText unit, WidgetRef ref) {
    final item = unit.item;
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Eyebrow('Evidence, not an assertion'),
              const SizedBox(height: 12),
              Text('Source & edition', style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 20),
              SelectableText(item.instrument.title ?? 'Untitled source record'),
              const SizedBox(height: 16),
              Text(
                'PDF page: ${item.first_page ?? "not recorded"}\n'
                'Read as at: ${unit.as_of}'
                '${unit.territory == null ? "" : "\nTerritory: ${territoryName(unit.territory)}"}',
                style: const TextStyle(height: 1.8),
              ),
              const SizedBox(height: 16),
              const Text('Source SHA-256', style: TextStyle(fontWeight: FontWeight.bold)),
              SelectableText(item.instrument.source_hash, style: const TextStyle(fontSize: 12)),
              const SizedBox(height: 16),
              const Text('Provision identity', style: TextStyle(fontWeight: FontWeight.bold)),
              SelectableText(item.id, style: const TextStyle(fontSize: 12)),
              const SizedBox(height: 20),
              if (item.instrument.source_url case final url?) ...[
                SelectableText(url, style: const TextStyle(fontSize: 12)),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () async {
                    final opened = await ref.read(sourceActionsProvider).open(url, page: item.first_page);
                    if (!opened && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Could not open the source. You can copy its address.')),
                      );
                    }
                  },
                  icon: const Icon(Icons.open_in_new),
                  label: const Text('Open official source'),
                ),
                TextButton.icon(
                  onPressed: () async {
                    final copied = await ref.read(sourceActionsProvider).copy(url);
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                        content: Text(copied ? 'Source address copied.' : 'Clipboard unavailable. Select the address above.'),
                      ));
                    }
                  },
                  icon: const Icon(Icons.copy),
                  label: const Text('Copy source address'),
                ),
              ] else
                const Notice('No official source URL is recorded for this edition.'),
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
}

/// Judge mode: the records behind what is shown, as they stand -- the as-at date, the territory, the serving
/// record's codes and dates, the law's reach and how it was read. Nothing here is derived in the client.
class _RecordPanel extends StatelessWidget {
  final law.UnitText unit;
  const _RecordPanel({required this.unit});
  @override
  Widget build(BuildContext context) {
    final l = unit.law;
    final rows = <(String, String)>[
      ('Read as at', unit.as_of),
      ('Territory', unit.territory == null ? 'All (each law with its own reach)' : territoryName(unit.territory)),
      if (l != null) ...[
        ('Currency', '${l.currency}${l.currency_reason == null ? "" : " · ${l.currency_reason}"}'),
        if (l.enacted_on != null) ('Enacted', l.enacted_on!),
        if (l.commenced_on != null) ('Commenced', l.commenced_on!),
        if (l.repealed_on != null) ('Repealed', l.repealed_on!),
        if (l.not_current_from != null) ('Not current from', l.not_current_from!),
        ('Reach', l.territory_reach.isEmpty ? 'none recorded' : l.territory_reach.map(territoryName).join(', ')),
        if (l.extent_basis != null) ('Reach read from', l.extent_basis!),
      ] else
        ('Serving record', 'none: an as-made text served through its consolidated text'),
      if (unit.not_served != null) ('Not served because', unit.not_served!),
    ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outline),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Eyebrow('The record'),
          const SizedBox(height: 8),
          for (final (k, v) in rows)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(width: 128, child: Text(k, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600))),
                  Expanded(child: SelectableText(v, style: const TextStyle(fontSize: 13))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// The path to the opened unit: the law, then each enclosing Part / Chapter. Each step opens that level.
class _Trail extends StatelessWidget {
  final List<(String, VoidCallback)> steps;
  const _Trail({required this.steps});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 2,
      runSpacing: 2,
      children: [
        for (var i = 0; i < steps.length; i++) ...[
          if (i > 0) Icon(Icons.chevron_right, size: 16, color: scheme.secondary),
          InkWell(
            onTap: steps[i].$2,
            borderRadius: BorderRadius.circular(8),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 40),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
                child: Text(
                  '\u2068${steps[i].$1}\u2069',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.3,
                    color: scheme.primary,
                    fontWeight: i == 0 ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _Header extends ConsumerWidget {
  final law.UnitText unit;
  const _Header({required this.unit});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final item = unit.item;
    final lawStatus = unit.law;
    final wording = lawStatus == null
        ? instrumentWording(item.instrument)
        : lawStatusWording(
            currency: lawStatus.currency,
            reason: lawStatus.currency_reason,
            notCurrentFrom: lawStatus.not_current_from,
            repealedOn: lawStatus.repealed_on,
            commencedOn: lawStatus.commenced_on,
          );
    final survives = unit.nodes.any((n) => n.survives_repeal);
    final kind = item.instrument.kind;
    final numbered = const {'section', 'article', 'rule', 'regulation'}.contains(item.kind);
    final caption = item.heading ?? item.marginal_note;
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Trail(steps: [
          (item.instrument.title ?? 'This law', () => context.push('/instrument/${item.instrument_id}')),
          for (final a in item.ancestors)
            (divisionTitle(kind, a.kind, a.label, a.heading ?? a.caption), () => context.push('/provision/${a.id}')),
        ]),
        const SizedBox(height: 14),
        Eyebrow('${jurisdictionName(item.instrument.jurisdiction)} · ${unitNoun(kind, item.kind)}'
            '${numbered && item.label != null ? ' ${item.label}' : ''}',
            jurisdiction: item.instrument.jurisdiction),
        const SizedBox(height: 10),
        if (numbered)
          Text.rich(
            TextSpan(children: [
              TextSpan(
                text: '\u2068${printedLabel(item.kind, item.label)}\u2069  ',
                style: TextStyle(color: scheme.secondary),
              ),
              TextSpan(text: caption ?? ''),
            ]),
            style: Theme.of(context).textTheme.headlineMedium,
          )
        else
          Text(
            item.kind == 'preamble' ? 'Preamble' : divisionTitle(kind, item.kind, item.label, caption),
            style: Theme.of(context).textTheme.headlineMedium,
          ),
        const SizedBox(height: 16),
        StatusBanner(
          wording,
          compact: true,
          extra: survives ? 'This part is still law: the repeal of this law expressly excepts it.' : null,
        ),
        if (ref.watch(readingModeProvider).showTemporal) ...[
          const SizedBox(height: 12),
          _RecordPanel(unit: unit),
        ],
        if (unit.not_served case final code?) ...[
          const SizedBox(height: 12),
          Notice(
            notServedWording(code, from: unit.not_served_from, asOf: unit.as_of, territory: unit.territory),
            icon: Icons.event_busy_outlined,
          ),
        ],
        const SizedBox(height: 8),
      ],
    );
  }
}

/// The units either side of this one in the law's printed order, so a reader goes on to the next Article without
/// going back to the list. Fetched beside the text; while it loads, or for a unit that is not itself listed (a
/// sub-section, a Part), nothing is shown.
class _Neighbours extends ConsumerWidget {
  final String id;
  final String instrumentKind;
  const _Neighbours({required this.id, required this.instrumentKind});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final n = ref.watch(neighboursProvider(id)).valueOrNull;
    if (n == null || n.position == null) return const SizedBox.shrink();
    Widget card(law.SectionItem s, bool forward) {
      final scheme = Theme.of(context).colorScheme;
      final name = s.kind == 'preamble'
          ? 'Preamble'
          : const {'section', 'article', 'rule', 'regulation'}.contains(s.kind)
              ? '${unitNoun(instrumentKind, s.kind)} ${s.label ?? ''}'
              : divisionTitle(instrumentKind, s.kind, s.label, null);
      return Material(
        color: scheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: scheme.outline),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          // replace, so Back returns to the law rather than through every unit read on the way
          onTap: () => context.pushReplacement('/provision/${s.id}'),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: forward ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (!forward) Icon(Icons.arrow_back, size: 16, color: scheme.secondary),
                    Text(forward ? 'Next' : 'Previous', style: TextStyle(fontSize: 12, color: scheme.secondary)),
                    if (forward) Icon(Icons.arrow_forward, size: 16, color: scheme.secondary),
                  ],
                ),
                const SizedBox(height: 6),
                Text('\u2068$name\u2069',
                    textAlign: forward ? TextAlign.end : TextAlign.start,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                if ((s.heading ?? '').isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    s.heading!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    textAlign: forward ? TextAlign.end : TextAlign.start,
                    style: const TextStyle(fontSize: 13, height: 1.35),
                  ),
                ],
              ],
            ),
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${n.position} of ${n.total} in this law',
            style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.secondary)),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: n.previous == null ? const SizedBox.shrink() : card(n.previous!, false)),
            const SizedBox(width: 12),
            Expanded(child: n.next == null ? const SizedBox.shrink() : card(n.next!, true)),
          ],
        ),
      ],
    );
  }
}

class _Footer extends StatelessWidget {
  final law.UnitText unit;
  final VoidCallback onSource;
  const _Footer({required this.unit, required this.onSource});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (unit.truncated) ...[
            const Notice('This unit is long; the first part is shown. Open its sub-units from the law to read on.'),
            const SizedBox(height: 16),
          ],
          OutlinedButton.icon(
            onPressed: onSource,
            icon: const Icon(Icons.description_outlined),
            label: const Text('Source & edition'),
          ),
          const SizedBox(height: 20),
          const Notice(
            'Legal information, not advice. The text is reproduced from the database, not generated. Check the official source before relying on it.',
          ),
        ],
      );
}
