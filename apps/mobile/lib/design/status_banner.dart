import 'package:flutter/material.dart';
import '../domain/law_status.dart';

/// The StatusBanner of docs/08 and the nizam-client rules: above the text, never collapsible, and never styled as
/// an error -- a repealed law or a presumed status is an outcome the reader must see, not a failure. Standing is
/// carried by icon and words as well as colour (no information by colour alone).
class StatusBanner extends StatelessWidget {
  final StatusWording wording;
  final String? extra;
  const StatusBanner(this.wording, {super.key, this.extra});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (icon, tone) = switch (wording.standing) {
      Standing.inForce => (Icons.verified_outlined, scheme.primary),
      Standing.presumed => (Icons.help_outline, scheme.secondary),
      Standing.notLaw => (Icons.block, scheme.onSurface),
      Standing.historical => (Icons.history_edu_outlined, scheme.onSurface),
      Standing.unknown => (Icons.help_outline, scheme.onSurface),
    };
    final detail = [wording.detail, extra].whereType<String>().join(' ');
    return Semantics(
      container: true,
      label: 'Legal status: ${wording.title}. $detail',
      child: ExcludeSemantics(
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
          decoration: BoxDecoration(
            color: tone.withValues(alpha: .07),
            borderRadius: BorderRadius.circular(14),
            border: Border(left: BorderSide(color: tone, width: 4)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 22, color: tone),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      wording.title,
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: tone),
                    ),
                    if (detail.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(detail, style: const TextStyle(height: 1.45)),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
