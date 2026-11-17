import 'package:flutter/material.dart';
import '../domain/law_status.dart';

/// The StatusBanner of docs/08 and the nizam-client rules: above the text, never collapsible, and never styled as
/// an error -- a repealed law or a presumed status is an outcome the reader must see, not a failure. Standing is
/// carried by icon and words as well as colour (no information by colour alone).
class StatusBanner extends StatelessWidget {
  final StatusWording wording;
  final String? extra;
  /// Tighter type for the reader, where the text is the point. Applies only to a law in force or presumed in force:
  /// a repealed, lapsed or historical standing always shows in full (client rules: StatusBanner).
  final bool compact;
  const StatusBanner(this.wording, {super.key, this.extra, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final tight = compact && (wording.standing == Standing.inForce || wording.standing == Standing.presumed);
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
          padding: tight ? const EdgeInsets.fromLTRB(12, 10, 12, 10) : const EdgeInsets.fromLTRB(16, 14, 16, 14),
          decoration: BoxDecoration(
            color: tone.withValues(alpha: .07),
            borderRadius: BorderRadius.circular(14),
            border: Border(left: BorderSide(color: tone, width: 4)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: tight ? 18 : 22, color: tone),
              SizedBox(width: tight ? 10 : 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      wording.title,
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: tight ? 14 : 16, color: tone),
                    ),
                    if (detail.isNotEmpty) ...[
                      SizedBox(height: tight ? 2 : 4),
                      Text(detail, style: TextStyle(height: tight ? 1.35 : 1.45, fontSize: tight ? 12.5 : null)),
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
