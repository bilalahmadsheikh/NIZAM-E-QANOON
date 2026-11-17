/// Reading modes (client domain: pure). Doc 13 §02: "model circumstances and capabilities, not decorative personas";
/// the everyday view is "progressive disclosure, not information deletion" and a professional view "increases
/// evidence density and tools, not legal certainty". So a mode changes density, defaults and tools -- never which
/// law is served, never a status, never a qualification. It is a reading preference, not an identity: choosing
/// "Judge" verifies nothing and unlocks nothing (doc 13 §00, possession of a phone is not professional identity).
library;

enum ReadingMode { everyday, student, lawyer, judge }

extension ReadingModeTraits on ReadingMode {
  String get label => switch (this) {
        ReadingMode.everyday => 'Everyday',
        ReadingMode.student => 'Student',
        ReadingMode.lawyer => 'Lawyer',
        ReadingMode.judge => 'Judge',
      };

  String get description => switch (this) {
        ReadingMode.everyday =>
          'Larger text and plain wording. Every status and qualification is still shown.',
        ReadingMode.student => 'Parts and chapters stay in view, with citations to note down.',
        ReadingMode.lawyer => 'Denser lists, citations with one-tap copy, source pages inline.',
        ReadingMode.judge =>
          'As lawyer, plus a record panel above the text: the date it is read at, the territory, and the '
              'recorded basis of the law\'s status.',
      };

  /// Added to the reader's chosen size.
  double get sizeDelta => switch (this) {
        ReadingMode.everyday => 2,
        ReadingMode.student => 0,
        ReadingMode.lawyer => -1,
        ReadingMode.judge => -1,
      };

  /// Part/Chapter headings inside a law's section list.
  bool get showGroups => this != ReadingMode.everyday;

  /// The citation, rendered by the server from the records (INV-1), shown with each section.
  bool get showCitation => this != ReadingMode.everyday;

  /// One-tap copy of that citation.
  bool get copyCitation => this == ReadingMode.lawyer || this == ReadingMode.judge;

  /// Compact section rows.
  bool get compact => this == ReadingMode.lawyer || this == ReadingMode.judge;

  /// The as-at date and the serving reason code beside the status.
  bool get showTemporal => this == ReadingMode.judge;

  /// PDF page numbers beside each section.
  bool get showPages => this == ReadingMode.lawyer || this == ReadingMode.judge;
}
