/// Pakistan's regions as the Heritage tab and the jurisdiction tiles show them (D-077): a landmark of each region,
/// one sentence about it, and a craft the region is known for. Editorial context, never law: every fact here was
/// checked against the source it links on 18 Nov 2026 (CLAUDE.md: never assert an external fact from memory), and
/// none of it says what the law requires -- the laws themselves come from the database.
library;

/// The landmarks drawn by design/heritage_art.dart.
enum Landmark { minar, badshahi, mohenjodaro, takhtibahi, ziarat, faisal, redfort, baltit, mazar }

/// The motif bands drawn by design/heritage_art.dart, each after a craft of its region.
enum Motif { truckArt, kashi, ajrak, lacquer, mirrorwork, faisalFolds, chainStitch, crossStitch }

class Craft {
  final String name;
  final String note;
  final String source;
  const Craft(this.name, this.note, this.source);
}

class HeritageRegion {
  final String jurisdiction;
  final Landmark landmark;
  final Motif motif;
  final String place;
  final String location;
  final String note;
  /// Where each fact in [note] was checked; every sentence is covered by one of them.
  final List<String> sources;
  final Craft? craft;
  const HeritageRegion({
    required this.jurisdiction,
    required this.landmark,
    required this.motif,
    required this.place,
    required this.location,
    required this.note,
    required this.sources,
    this.craft,
  });
}

const heritageRegions = <HeritageRegion>[
  HeritageRegion(
    jurisdiction: 'fed',
    landmark: Landmark.minar,
    motif: Motif.truckArt,
    place: 'Minar-e-Pakistan',
    location: 'Iqbal Park, Lahore',
    note: 'A national monument where the All-India Muslim League met in March 1940 and passed the Lahore '
        'Resolution. Its foundation stone was laid on 23 March 1960 and it was completed in 1968.',
    sources: ['https://archnet.org/sites/260', 'https://www.app.com.pk/?p=143540'],
    craft: Craft('Truck art', 'Hand-painted trucks and buses, a folk art whose styles differ from region to region.',
        'https://www.dawn.com/news/1892032'),
  ),
  HeritageRegion(
    jurisdiction: 'punjab',
    landmark: Landmark.badshahi,
    motif: Motif.kashi,
    place: 'Badshahi Mosque',
    location: 'Lahore',
    note: 'Built under the Mughal emperor Aurangzeb and completed in 1673, facing the Lahore Fort. The Fort and the '
        'Shalimar Gardens are a UNESCO World Heritage site, inscribed in 1981.',
    sources: ['https://en.wikipedia.org/wiki/Badshahi_Mosque',
      'https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Pakistan'],
    craft: Craft('Multani blue pottery', 'Multan’s glazed blue-and-white ceramic and tile work, known as kashi.',
        'https://thefridaytimes.com/29-Dec-2025/preserving-multani-ceramics-handicrafts-pakistan-s-cultural-heritage-craft-economy'),
  ),
  HeritageRegion(
    jurisdiction: 'sindh',
    landmark: Landmark.mohenjodaro,
    motif: Motif.ajrak,
    place: 'Mohenjo-daro',
    location: 'Larkana',
    note: 'A city of the Indus civilisation on the right bank of the Indus, a UNESCO World Heritage site since 1980. '
        'The historical monuments at Makli, Thatta, were inscribed in 1981.',
    sources: ['https://en.wikipedia.org/wiki/List_of_World_Heritage_Sites_in_Pakistan'],
    craft: Craft('Ajrak and ralli', 'Block-printed ajrak cloth, and ralli patchwork quilts of rural Sindh.',
        'https://journals.umt.edu.pk/index.php/jdt/article/download/5294/2217'),
  ),
  HeritageRegion(
    jurisdiction: 'kp',
    landmark: Landmark.takhtibahi,
    motif: Motif.lacquer,
    place: 'Takht-i-Bahi',
    location: 'Mardan',
    note: 'A Buddhist monastery founded in the 1st century CE and in use until the 7th. With the city remains at '
        'Sahr-i-Bahlol it has been a UNESCO World Heritage site since 1980.',
    sources: ['https://en.wikipedia.org/wiki/Takht-i-Bahi'],
    craft: Craft('Lacquer and metal work', 'Lacquer art of Khyber Pakhtunkhwa and the metal craft of Peshawar.',
        'https://tdap.gov.pk/wp-content/uploads/2022/04/Handicraft-1.pdf'),
  ),
  HeritageRegion(
    jurisdiction: 'balochistan',
    landmark: Landmark.ziarat,
    motif: Motif.mirrorwork,
    place: 'Quaid-e-Azam Residency',
    location: 'Ziarat',
    note: 'A wooden residency built in 1892, where Quaid-e-Azam Muhammad Ali Jinnah stayed in the last months of his '
        'life in 1948. It is a declared national monument.',
    sources: ['https://www.arabnews.pk/node/2141916'],
    craft: Craft('Balochi embroidery', 'Needlework and mirror work, as on the doch dress; Kalat is known for it.',
        'https://en.wikipedia.org/wiki/Balochi_handicrafts'),
  ),
  HeritageRegion(
    jurisdiction: 'ict',
    landmark: Landmark.faisal,
    motif: Motif.faisalFolds,
    place: 'Faisal Mosque',
    location: 'Islamabad',
    note: 'Designed by the Turkish architect Vedat Dalokay, whose design was chosen in an international competition in '
        '1969, and completed in 1986.',
    sources: ['https://www.arabnews.pk/node/1453571'],
  ),
  HeritageRegion(
    jurisdiction: 'ajk',
    landmark: Landmark.redfort,
    motif: Motif.chainStitch,
    place: 'Red Fort (Rutta Qila)',
    location: 'Muzaffarabad',
    note: 'Begun by the Chak rulers of Kashmir in the 16th century and completed in 1646 by Sultan Muzaffar Khan, '
        'the founder of Muzaffarabad. It stands despite damage in the 2005 earthquake.',
    sources: ['https://en.wikipedia.org/wiki/Red_Fort,_Muzaffarabad'],
    craft: Craft('Namda and chain stitch', 'Felted-wool namda rugs, chain-stitch, gabba and shawls, among the crafts '
        'Azad Kashmir promotes.', 'https://sic.ajk.gov.pk/?p=648'),
  ),
  HeritageRegion(
    jurisdiction: 'gb',
    landmark: Landmark.baltit,
    motif: Motif.crossStitch,
    place: 'Baltit Fort',
    location: 'Karimabad, Hunza',
    note: 'The former residence of the Mirs of Hunza, restored by the Aga Khan Trust for Culture as a museum; the '
        'restoration won a UNESCO Asia-Pacific Heritage Award in 2004.',
    sources: ['https://www.akdn.org/project/sustaining-restored-monuments'],
    craft: Craft('Hunza embroidery', 'Fine geometric stitching, often on women’s caps, and patti, a local handwoven wool.',
        'https://pamirtimes.net/2016/02/26/needles-and-threads-disappearing-forms-of-embroidery-in-gilgit-baltsitan/'),
  ),
];

HeritageRegion? heritageRegion(String jurisdiction) {
  for (final r in heritageRegions) {
    if (r.jurisdiction == jurisdiction) return r;
  }
  return null;
}

/// The questions the server sends as codes (nizam/api/collections.py HERITAGE_QUESTIONS), in the words shown. The
/// answer is always the law's own units, opened in the reader -- never a summary written here.
String heritageQuestion(String key) => const {
      'found_object': 'Found an old object while digging or building?',
      'build_near': 'Planning to build near a protected monument?',
      'repair': 'Repairing or altering a protected old building?',
      'declared_protected': 'How does a place become protected, and can its owner object?',
      'damage_signs': 'Damage, graffiti or signboards on a monument?',
      'export': 'Taking an antiquity out of Pakistan?',
      'culture_right': 'The right to preserve a language, script and culture',
    }[key] ??
    key;
