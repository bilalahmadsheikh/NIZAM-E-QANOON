"""Places in a question -> the territory whose law answers it (D-097; docs/04 query understanding, R0).

"My landlord in Lahore ..." is a Punjab question: Punjab's own law and federal law that runs there. A place sets the
TERRITORY (operative_provision's nzq.territory, which already knows where each law runs, 0086/0095), never a guess
about the answer. Values: punjab, sindh, kp, balochistan, ict, ajk, gb (docs/SCHEMA.md).

Source of the districts: Wikipedia, "Districts of Pakistan" and the Punjab and Sindh district lists, read 18 Nov 2026
(district names verbatim; 170 districts in 7 units). Headquarters are added only where the page printed them
verbatim (Punjab, Sindh, Balochistan, Islamabad, and the KP rows marked so); summary-only headquarters are not used.

Matching is case-sensitive on whole words, so 'tank' or 'hub' in a sentence is not a district. District names that
are ordinary English words, or another country's city, are left out: Tank, Hub, Bagh, Haveli, Nagar, Khyber (as a
district; 'Khyber Pakhtunkhwa' still matches). Two different territories named in one question -> no territory: the
question compares, and docs/04 forbids guessing one.
"""
from __future__ import annotations

import re

PROVINCE_NAMES = {
    "punjab": ["Punjab"],
    "sindh": ["Sindh", "Sind"],
    "kp": ["Khyber Pakhtunkhwa", "Khyber-Pakhtunkhwa", "KPK", "KP", "NWFP", "North-West Frontier Province"],
    "balochistan": ["Balochistan", "Baluchistan"],
    "ict": ["Islamabad", "Islamabad Capital Territory", "ICT"],
    "ajk": ["Azad Jammu and Kashmir", "Azad Jammu & Kashmir", "Azad Kashmir", "AJK", "AJ&K"],
    "gb": ["Gilgit-Baltistan", "Gilgit Baltistan"],
}

DISTRICTS = {
    "punjab": """Attock Bahawalnagar Bahawalpur Bhakkar Chakwal Chiniot|Dera Ghazi Khan|Faisalabad Gujranwala Gujrat
        Hafizabad Jhang Jhelum Kasur Khanewal Khushab Jauharabad Lahore Layyah Lodhran|Mandi Bahauddin|Mianwali Multan
        Muzaffargarh|Nankana Sahib|Narowal Okara Pakpattan|Rahim Yar Khan|Rajanpur Rawalpindi Sahiwal Sargodha
        Sheikhupura Sialkot|Toba Tek Singh|Vehari Talagang Murree Taunsa|Kot Addu|Wazirabad""",
    "sindh": """Badin Dadu Ghotki|Mirpur Mathelo|Hyderabad Jacobabad Jamshoro Karachi|Karachi Central|Karachi East|
        Karachi South|Karachi West|Kashmore Kandhkot Keamari Khairpur Korangi Larkana Malir Matiari|Mirpur Khas|
        Naushahro Feroze|Qambar Shahdadkot|Qambar|Sanghar|Shaheed Benazirabad|Nawabshah Shikarpur Sujawal Sukkur|
        Tando Allahyar|Tando Muhammad Khan|Tharparkar Mithi Thatta Umerkot""",
    "kp": """Abbottabad Allai Battagram Haripur|Kolai Palas|Torghar|Upper Kohistan|Lower Kohistan|Mansehra Hangu
        Karak Kohat Kurram Orakzai Bannu|Lakki Marwat|North Waziristan|Miranshah|Landi Kotal|Mohmand Nowshera
        Peshawar Charsadda|Dera Ismail Khan|Upper South Waziristan|Lower South Waziristan|South Waziristan|Waziristan|
        Spinkai Wana Malakand Mardan Swabi|Upper Chitral|Booni|Upper Dir|Dir|Lower Chitral|Chitral|Lower Dir|Swat|
        Saidu Sharif|Shangla Bajaur Buner|Central Dir|Wari""",
    "balochistan": """Surab Lasbela Uthal Mastung Khuzdar Kalat Awaran Barkhan Duki Musakhel|Musa Khel Bazar|Loralai
        Gwadar Kech Turbat Panjgur Jafarabad|Dera Allahyar|Jhal Magsi|Gandava Kachhi Dhadar Nasirabad|
        Dera Murad Jamali|Sohbatpur|Usta Muhammad|Dera Bugti|Kohlu Sibi Harnai Ziarat Chaman Pishin Quetta|
        Qila Abdullah|Jungle Pir Alizai|Qilla Saifullah|Sherani Zhob Kharan Nushki Washuk Chagai Dalbandin""",
    "ajk": """Muzaffarabad|Hattian Bala|Neelum Mirpur Bhimber Kotli Poonch Sudhnati""",
    "gb": """Ghanche Skardu Roundu Astore Diamer Darel Tangir Ghizer Gilgit Hunza Kharmang Shigar|Gupis-Yasin""",
}


def _names(spec: str) -> list[str]:
    """'|' separates chunks; a chunk that is a known multi-word name is one name, any other chunk is single words"""
    out = []
    for chunk in spec.split("|"):
        chunk = " ".join(chunk.split())
        if chunk in _MULTI:
            out.append(chunk)
        elif chunk:
            out.extend(chunk.split())
    return out


_MULTI = {"Dera Ghazi Khan", "Mandi Bahauddin", "Nankana Sahib", "Rahim Yar Khan", "Toba Tek Singh", "Kot Addu",
          "Mirpur Mathelo", "Karachi Central", "Karachi East", "Karachi South", "Karachi West", "Mirpur Khas",
          "Naushahro Feroze", "Qambar Shahdadkot", "Shaheed Benazirabad", "Tando Allahyar", "Tando Muhammad Khan",
          "Kolai Palas", "Upper Kohistan", "Lower Kohistan", "Lakki Marwat", "North Waziristan", "Landi Kotal",
          "Dera Ismail Khan", "Upper South Waziristan", "Lower South Waziristan", "South Waziristan", "Upper Chitral",
          "Upper Dir", "Lower Chitral", "Lower Dir", "Saidu Sharif", "Central Dir", "Musa Khel Bazar",
          "Dera Allahyar", "Jhal Magsi", "Dera Murad Jamali", "Usta Muhammad", "Dera Bugti", "Qila Abdullah",
          "Jungle Pir Alizai", "Qilla Saifullah", "Hattian Bala", "Gupis-Yasin"}

# Urdu-script names (D-109): the provinces and territories, and their capitals and largest cities, in their common
# Urdu spellings. A question written in Urdu names its place in Urdu ('پنجاب میں مالک مکان ...').
URDU_NAMES = {
    "punjab": "پنجاب لاہور راولپنڈی فیصل_آباد ملتان گوجرانوالہ سیالکوٹ سرگودھا بہاولپور",
    "sindh": "سندھ کراچی حیدرآباد حیدر_آباد سکھر لاڑکانہ میرپور_خاص",
    "kp": "خیبر_پختونخوا خیبر_پختونخواہ کے_پی پشاور مردان ایبٹ_آباد سوات کوہاٹ بنوں",
    "balochistan": "بلوچستان کوئٹہ گوادر تربت",
    "ict": "اسلام_آباد",
    "ajk": "آزاد_کشمیر آزاد_جموں_و_کشمیر مظفرآباد مظفر_آباد میرپور",
    "gb": "گلگت_بلتستان گلگت سکردو ہنزہ",
}

GAZETTEER: dict[str, str] = {}
for _t, _ns in PROVINCE_NAMES.items():
    for _n in _ns:
        GAZETTEER[_n] = _t
for _t, _spec in DISTRICTS.items():
    for _n in _names(_spec):
        GAZETTEER.setdefault(_n, _t)
URDU_GAZETTEER = {n.replace("_", " "): t for t, spec in URDU_NAMES.items() for n in spec.split()}
# Mirpur is AJK's district and also part of Sindh's 'Mirpur Khas'/'Mirpur Mathelo' (those longer names win)
_PATTERN = re.compile(r"(?<![A-Za-z&-])(" + "|".join(sorted((re.escape(n) for n in GAZETTEER), key=len, reverse=True))
                      + r")(?![A-Za-z&-])")
_URDU_PATTERN = re.compile(r"(?<![؀-ۿ])(" + "|".join(sorted((re.escape(n) for n in URDU_GAZETTEER), key=len,
                                                               reverse=True)) + r")(?![؀-ۿ])")


def places(text: str) -> list[tuple[str, str]]:
    """[(name as written, territory)] in order of appearance"""
    found = [(m.start(), m.group(1), GAZETTEER[m.group(1)]) for m in _PATTERN.finditer(text or "")]
    found += [(m.start(), m.group(1), URDU_GAZETTEER[m.group(1)]) for m in _URDU_PATTERN.finditer(text or "")]
    return [(n, t) for _s, n, t in sorted(found)]


def territory_of(text: str) -> str | None:
    """the one territory the question names, or None (none named, or two different ones: a comparison)"""
    found = {t for _n, t in places(text)}
    return found.pop() if len(found) == 1 else None
