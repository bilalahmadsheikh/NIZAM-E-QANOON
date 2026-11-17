/// How a law's serving record is worded to a reader (client domain sublayer: pure, no widgets, no I/O).
///
/// The server sends codes (mv_instrument_serving.currency / currency_reason, and a `not_served` code for a unit
/// that is not law at the chosen date); the words live here so every screen says the same thing. The rule from
/// docs/13: never overstate. A law in force only by the owner's presumption is "treated as in force", never
/// "in force"; a unit that is not law at the date is an outcome, not an error.
library;

enum Standing { inForce, presumed, notLaw, historical, unknown }

class StatusWording {
  final Standing standing;
  final String title;
  final String? detail;
  const StatusWording(this.standing, this.title, [this.detail]);
}

String _on(String? date) => date == null ? '' : ' on $date';

StatusWording lawStatusWording({
  required String? currency,
  required String? reason,
  String? notCurrentFrom,
  String? repealedOn,
  String? commencedOn,
}) {
  switch (currency) {
    case 'current':
      switch (reason) {
        case 'owner_presumption_in_force':
          return const StatusWording(
            Standing.presumed,
            'Treated as in force',
            'No repeal, lapse or expiry is recorded for this law, but its force has not been verified against an '
                'official status source.',
          );
        case 'commenced_on_established':
          return StatusWording(
            Standing.inForce,
            'In force',
            commencedOn == null ? 'Its commencement is recorded.' : 'In force since $commencedOn.',
          );
        case 'commences_at_once':
          return const StatusWording(Standing.inForce, 'In force', 'It came into force on enactment.');
        case 'general_clauses_silent_act':
          return const StatusWording(
            Standing.inForce,
            'In force',
            'It names no commencement, so it came into force under the General Clauses Act.',
          );
        default:
          return const StatusWording(Standing.inForce, 'In force');
      }
    case 'not_current':
      final from = repealedOn ?? notCurrentFrom;
      switch (reason) {
        case 'ordinance_lapsed':
          return StatusWording(Standing.notLaw, 'Lapsed', 'This Ordinance lapsed${_on(from)} and is not law.');
        case 'replaced_by_later_act':
        case 'superseded_by_later_instrument':
          return StatusWording(Standing.notLaw, 'Replaced', 'A later law replaced it${_on(from)}.');
        case 'repealed_in_each_territory':
          return StatusWording(
              Standing.notLaw, 'Repealed', 'It has been repealed in every territory it applied to${_on(from)}.');
        case 'repealed_date_not_established':
          return const StatusWording(
              Standing.notLaw, 'Repealed', 'A later law repeals it. The date of the repeal is not established.');
        default:
          return StatusWording(Standing.notLaw, 'Repealed', from == null ? null : 'Repealed$_onPrefix$from.');
      }
    case 'historical':
      return const StatusWording(
        Standing.historical,
        'Historical text',
        'This is a text of the past, not current law.',
      );
    default:
      return const StatusWording(Standing.unknown, 'Status not recorded');
  }
}

const _onPrefix = ' with effect from ';

String territoryName(String? key) =>
    const {
      'punjab': 'Punjab',
      'sindh': 'Sindh',
      'kp': 'Khyber Pakhtunkhwa',
      'balochistan': 'Balochistan',
      'ict': 'Islamabad Capital Territory',
      'ajk': 'Azad Jammu and Kashmir',
      'gb': 'Gilgit-Baltistan',
    }[key] ??
    (key ?? '');

/// Why a unit is not law at the chosen date (and territory). Worded as an outcome, never as a failure.
String notServedWording(String code, {String? from, required String asOf, String? territory}) {
  switch (code) {
    case 'unit_repealed':
      return 'Not law on $asOf: this provision was repealed with effect from ${from ?? "a date not recorded"}. '
          'Choose an earlier date to read it as it stood.';
    case 'law_repealed':
      return 'Not law on $asOf: the law was repealed${_on(from)}.';
    case 'law_not_current':
      return 'Not law on $asOf: the law stopped being current${_on(from)}.';
    case 'law_historical':
      return 'This is a historical text; it was not in force on $asOf.';
    case 'law_not_yet_in_force':
      return 'Not yet law on $asOf: it comes into force${_on(from)}.';
    case 'law_does_not_run_in_territory':
      return 'This law does not apply in ${territoryName(territory)}.';
    case 'law_repealed_in_territory':
      return 'Repealed in ${territoryName(territory)}${_on(from)}; it may still apply elsewhere.';
    case 'served_through_consolidated_text':
      return 'This is the text as originally made. Read the consolidated text for the law as it stands.';
    default:
      return 'No text is held for $asOf. That does not mean the provision did not exist then.';
  }
}

/// The label as the statute prints it: '(1)' for a sub-section, '(a)' for a clause, '302.' for a section.
String printedLabel(String kind, String? label) {
  if (label == null || label.isEmpty) return '';
  const bracketed = {'subsection', 'clause', 'subclause', 'sub_clause', 'paragraph', 'subparagraph', 'item'};
  if (bracketed.contains(kind)) return label.startsWith('(') ? label : '($label)';
  if (kind == 'section' || kind == 'article' || kind == 'rule' || kind == 'regulation') return '$label.';
  return label;
}
