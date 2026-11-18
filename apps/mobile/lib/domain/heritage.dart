/// Pakistan's regions as the Heritage tab and the jurisdiction tiles show them (D-077): a landmark of each region,
/// one sentence about it, and a craft the region is known for. Editorial context, never law: every fact here was
/// checked against the source it links on 18 Nov 2026 (CLAUDE.md: never assert an external fact from memory), and
/// none of it says what the law requires -- the laws themselves come from the database.
library;

/// The landmarks drawn by design/heritage_art.dart.
enum Landmark { minar, badshahi, mohenjodaro, takhtibahi, ziarat, faisal, redfort, baltit, mazar }

/// The motif bands drawn by design/heritage_art.dart, each after a craft of its region (D-077, D-079).
enum Motif {
  truckArt, kashi, ajrak, lacquer, mirrorwork, faisalFolds, chainStitch, crossStitch,
  // D-079: a motif for every craft a region names
  football, jaali, halaTile, chappal, rug, folkVessels, chinar, woolCap,
}

/// A craft, a made thing or a keeper of crafts, named for its region: its motif, the town it is made in, one sourced
/// line. Editorial context: it says nothing about what the law requires.
class Craft {
  final String name;
  final Motif motif;
  final String? town;
  final String note;
  final String source;
  const Craft(this.name, this.motif, this.note, this.source, {this.town});
}

class HeritageRegion {
  final String jurisdiction;
  final Landmark landmark;
  /// The region's own band, drawn under its landmark and on its home tile: its first craft's motif, or, where it
  /// has none of its own, its landmark's (Islamabad).
  final Motif motif;
  final String place;
  final String location;
  final String note;
  /// Where each fact in [note] was checked; every sentence is covered by one of them.
  final List<String> sources;
  final List<Craft> crafts;
  const HeritageRegion({
    required this.jurisdiction,
    required this.landmark,
    required this.motif,
    required this.place,
    required this.location,
    required this.note,
    required this.sources,
    this.crafts = const [],
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
    crafts: [
      Craft('Truck art', Motif.truckArt,
          'Hand-painted trucks and buses, a folk art whose styles differ from region to region.',
          'https://www.dawn.com/news/1892032'),
    ],
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
    crafts: [
      Craft('Multani blue pottery', Motif.kashi, 'Glazed blue-and-white ceramic and tile work, known as kashi.',
          'https://thefridaytimes.com/29-Dec-2025/preserving-multani-ceramics-handicrafts-pakistan-s-cultural-heritage-craft-economy',
          town: 'Multan'),
      // the World Cup balls are thermo-bonded, not hand-stitched (Forward Sports, 2022): the line claims no stitching
      Craft('Footballs', Motif.football,
          'Sialkot’s ball makers supplied match balls for the 2022 FIFA World Cup in Qatar.',
          'https://www.dawn.com/news/1697661', town: 'Sialkot'),
      Craft('Carved furniture', Motif.jaali,
          'Hand-carved sheesham and walnut furniture; the trade authority calls Chiniot its main centre.',
          'https://tdap.gov.pk/wp-content/uploads/2023/10/Report-on-Wooden-Furniture-Updated-on-17-Oct-2023.pdf',
          town: 'Chiniot'),
    ],
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
    crafts: [
      Craft('Ajrak and ralli', Motif.ajrak, 'Block-printed ajrak cloth, and ralli patchwork quilts of rural Sindh.',
          'https://journals.umt.edu.pk/index.php/jdt/article/download/5294/2217'),
      Craft('Kashi tiles and lacquer', Motif.halaTile,
          'Glazed blue kashi tiles made by kashigars in Hala and Nasarpur, and Hala’s turned lacquer woodwork.',
          'https://www.aic-iac.org/wp-content/uploads/Clay-Culture-of-Blue-Kashi-Tiles_FINAL.pdf', town: 'Hala'),
    ],
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
    crafts: [
      Craft('Lacquer and metal work', Motif.lacquer,
          'Lacquer art of Khyber Pakhtunkhwa and the metal craft of Peshawar.',
          'https://tdap.gov.pk/wp-content/uploads/2022/04/Handicraft-1.pdf'),
      Craft('Peshawari chappal', Motif.chappal,
          'Handmade leather sandals, sought out in Peshawar’s markets before Eid.',
          'https://www.app.com.pk/domestic/peshawari-chappal-a-handmade-footwear-draw-people-ahead-of-eid-ul-fitr-celebrations/',
          town: 'Peshawar'),
    ],
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
    crafts: [
      Craft('Balochi embroidery', Motif.mirrorwork, 'Needlework and mirror work, as on the doch dress.',
          'https://en.wikipedia.org/wiki/Balochi_handicrafts', town: 'Kalat'),
      Craft('Balochi rugs', Motif.rug,
          'Knotted rugs in deep reds, browns and blues with geometric patterns, often woven by women.',
          'https://en.wikipedia.org/wiki/Balochi_rug'),
    ],
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
    crafts: [
      // a keeper of crafts rather than a craft: the federal law that gives it its status is in the Heritage laws
      Craft('Lok Virsa', Motif.folkVessels,
          'The national institute of folk and traditional heritage, founded in 1974; its museum on the Shakarparian '
              'hills keeps crafts from every region.',
          'https://en.wikipedia.org/wiki/Lok_Virsa_Museum', town: 'Islamabad'),
    ],
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
    crafts: [
      Craft('Namda and chain stitch', Motif.chainStitch,
          'Felted-wool namda rugs, chain-stitch, gabba and shawls, among the crafts Azad Kashmir promotes.',
          'https://sic.ajk.gov.pk/?p=648'),
      Craft('Walnut wood carving', Motif.chinar,
          'Carved walnut chairs and beds, often with chinar leaves; carvers who came in 1947 began the trade here.',
          'https://tribune.com.pk/story/1385532/walnut-wood-fading-rage-ajk', town: 'Muzaffarabad'),
    ],
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
    crafts: [
      Craft('Hunza embroidery', Motif.crossStitch,
          'Fine geometric stitching, often on women’s caps, and patti, a local handwoven wool.',
          'https://pamirtimes.net/2016/02/26/needles-and-threads-disappearing-forms-of-embroidery-in-gilgit-baltsitan/'),
      Craft('The Gilgiti cap', Motif.woolCap,
          'A soft, round woollen cap worn across Gilgit-Baltistan, still made by hand.',
          'https://pamirtimes.net/2015/11/29/history-and-origin-of-the-traditional-hat-of-gilgit-baltistan/'),
    ],
  ),
];

/// Every craft with its region, in region order: what the home page's "From the regions" card turns through.
final List<(HeritageRegion, Craft)> allCrafts = [
  for (final r in heritageRegions)
    for (final c in r.crafts) (r, c),
];

/// The craft shown on [day] (an ISO date, the reader's as_of): one a day, the same all day, in turn through every
/// region -- no clock, no randomness, so a screenshot and a test see the same card.
(HeritageRegion, Craft) craftOfDay(String day) {
  final d = DateTime.tryParse(day) ?? DateTime(2026, 11, 18);
  final n = d.difference(DateTime(2026, 1, 1)).inDays;
  return allCrafts[n % allCrafts.length];
}

/// Editorial context for "Protecting what Pakistan makes" (D-079), checked against its source on 18 Nov 2026. It
/// says what happened, not what the law requires: the laws and sections are the database's.
const giFirst = (
  note: 'Basmati rice was registered as Pakistan’s first geographical indication in January 2021, under the '
      '2020 Act.',
  source: 'https://www.dawn.com/news/1604023',
);

HeritageRegion? heritageRegion(String jurisdiction) {
  for (final r in heritageRegions) {
    if (r.jurisdiction == jurisdiction) return r;
  }
  return null;
}

/// The questions the server sends as codes (nizam/api/collections.py HERITAGE_QUESTIONS), in the words shown. The
/// answer is always the law's own units, opened in the reader -- never a summary written here. Each region asks its
/// own law (D-078), so the words name no law and no place.
String heritageQuestion(String key) => const {
      'found_object': 'Found an old object while digging or building?',
      'build_near': 'Planning to build near a protected monument?',
      'repair': 'Repairing or altering a protected old building?',
      'declared_protected': 'How does a place become protected, and can its owner object?',
      'damage_signs': 'Damage, graffiti or signboards on a monument?',
      'export': 'Taking an antiquity out of the country?',
      'visit': 'Can the public visit a protected site?',
      'culture_right': 'The right to preserve a language, script and culture',
      // makers (D-079)
      'gi_place': 'Can a product known by its place be protected?',
      'gi_logo': 'How is a registered regional product marked?',
      'gi_fake': 'Someone sells goods under a place name they don’t come from?',
      'brand': 'Registering a workshop’s name or mark?',
      'design': 'Protecting a new pattern or shape?',
      'copyright': 'Who owns a painting, song or photograph?',
    }[key] ??
    key;
