"""Build golden-pk-v1 draft SET 3 (50 cases): provinces, territories and time.

Jurisdiction pairs (the same question in Punjab, Sindh, KP, Balochistan, ICT and AJK) and temporal pairs (the same
question at two dates, docs/10 §4 "temporal and jurisdiction pairs"): Punjab child marriage before and after the
Punjab Child Marriage Restraint Act, 2026; Punjab defamation before and after the Punjab Defamation Act, 2024; the
Anti-Rape Ordinance, 2020 against the Act of 2021. A temporal case's hard negatives are marked must_not_serve: the
gold says the other date's law must not be served, and the builder reports (without failing) where the system still
serves it.

Stage A0 + A3 by the lead (claude), 16 Nov 2026; propositions written from the held text (peek.py) and re-verified
by each case's `check` regexes at every build. Not gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set3")
c = S.case

# ---------------------------------------------------------------- citizen scenarios (20)
c("S3-C01", "citizen", "F3-rent-ict", "property", ["en"], "latin",
  "My landlord in Islamabad says I must vacate. When can he legally evict me?",
  "Grounds for eviction under the Islamabad Rent Restriction Ordinance, 2001", "fed", "ict", "answer",
  ["A tenant may be evicted only under section 17: the landlord applies to the Controller, who may order eviction "
   "on the listed grounds, such as rent not paid within fifteen days after the time fixed in the agreement (or "
   "sixty days without one)."],
  necessary=[(3126, "17", 3)], negatives=[(6269, "15", 0)], must_not_serve=[(6269, "15")],
  check=[r"Controller", r"fifteen days", r"sixty days"])
c("S3-C02", "citizen", "F3-rent-kp", "property", ["en"], "latin",
  "I rent a shop in Peshawar and the owner wants me out. What does the law require?",
  "Eviction under the West Pakistan Urban Rent Restriction Ordinance, 1959 (KP text)", "kp", "kp", "answer",
  ["A tenant may be evicted only in accordance with section 13 (or 13-A): the landlord applies to the Controller, "
   "who directs eviction if satisfied of a listed ground, such as non-payment of rent."],
  necessary=[(2234, "13", 3)], negatives=[(6269, "15", 0), (3126, "17", 0)],
  must_not_serve=[(6269, "15"), (3126, "17")], check=[r"Controller", r"shall not be evicted"])
c("S3-C03", "citizen", "F3-childmar-punjab", "family", ["en"], "latin",
  "My family in Lahore wants to marry my 16-year-old sister to a 25-year-old man. Is this a child marriage, and "
  "what can happen to him?", "Child marriage in Punjab under the Punjab Child Marriage Restraint Act, 2026",
  "punjab", "punjab", "answer",
  ["In Punjab a child is anyone, male or female, under eighteen, so this is a child marriage; an adult above "
   "eighteen who contracts it faces rigorous imprisonment of two to three years and fine up to five hundred "
   "thousand rupees, and no Nikah registrar may register it."],
  necessary=[(3382, "2", 3), (3382, "4", 3)], relevant=[(3382, "3", 2)],
  negatives=[(3227, "2", 0), (2693, "4", 0)], must_not_serve=[(3227, "2"), (2693, "4")],
  check=[r"under eighteen years of age", r"not be less than two years", r"five hundred thousand"])
c("S3-C04", "citizen", "F3-childmar-punjab", "family", ["en"], "latin",
  "In June 2020, could my family in Lahore lawfully marry my 16-year-old sister — was that a 'child marriage' "
  "under Punjab law then?", "Child marriage in Punjab as at 2020, under the Punjab text of the 1929 Act",
  "punjab", "punjab", "answer",
  ["As at June 2020 the Punjab text of the Child Marriage Restraint Act, 1929 defined a child as a male under "
   "eighteen or a female under sixteen, so the marriage of a sixteen-year-old girl was not a 'child marriage' "
   "within that Act."],
  as_of="2020-06-01",
  necessary=[(3227, "2", 3)], relevant=[(3227, "4", 1)], negatives=[(3382, "2", 0)],
  must_not_serve=[(3382, "2")], check=[r"female, is under sixteen"])
c("S3-C05", "citizen", "F3-childmar-ict", "family", ["en"], "latin",
  "Can a nikah registrar in Islamabad register the marriage of a 17-year-old?",
  "Child marriage under the ICT Child Marriage Restraint Act, 2025", "fed", "ict", "answer",
  ["No Nikah registrar may register a marriage where either party is below eighteen; the registrar must check both "
   "parties' CNICs; a male above eighteen who contracts a child marriage faces rigorous imprisonment of two to "
   "three years and fine."],
  necessary=[(2523, "3", 3), (2523, "4", 3)], negatives=[(2693, "4", 0)], must_not_serve=[(2693, "4")],
  check=[r"below the age of eighteen", r"not be less than two years"])
c("S3-C06", "citizen", "F3-childmar-balochistan", "family", ["en"], "latin",
  "What is the punishment in Balochistan for an adult man who marries a child?",
  "Punishment under the Balochistan Child Marriages Restraint Act, 2025", "balochistan", "balochistan", "answer",
  ["A male above eighteen who contracts a child marriage faces rigorous imprisonment of two to three years and "
   "fine of one to two hundred thousand rupees."],
  necessary=[(3519, "3", 3)], negatives=[(2693, "4", 0)], must_not_serve=[(2693, "4")],
  check=[r"not be less than two years", r"two hundred thousand"])
c("S3-C07", "citizen", "F3-defamation-punjab", "privacy", ["en"], "latin",
  "A YouTuber in Lahore made false claims about me. Can I sue him for damages, and do I have to prove a loss?",
  "Civil defamation under the Punjab Defamation Act, 2024", "punjab", "punjab", "answer",
  ["In Punjab defamation is a civil wrong actionable under the Punjab Defamation Act, 2024 without proof of actual "
   "damage or loss; where defamation is proved, general damages are presumed."],
  necessary=[(3321, "3", 3)], negatives=[(6333, "3", 0), (2020, "4", 0)],
  must_not_serve=[(6333, "3"), (2020, "4")], check=[r"without proof of actual damage", r"General Damages"])
c("S3-C08", "citizen", "F3-defamation-punjab", "privacy", ["en"], "latin",
  "In January 2020, someone in Lahore published false statements about me. Which law let me sue for defamation "
  "then?", "Civil defamation in Punjab as at 2020", "punjab", "punjab", "answer",
  ["As at January 2020 the Defamation Ordinance, 2002 (Punjab text) made a false statement injuring reputation "
   "actionable as defamation, in two forms: slander (oral) and libel (written or visual)."],
  as_of="2020-01-01",
  necessary=[(6333, "3", 3)], negatives=[(3321, "3", 0)], must_not_serve=[(3321, "3")],
  check=[r"slander", r"libel"])
c("S3-C09", "citizen", "F3-defamation-sindh", "privacy", ["en"], "latin",
  "A Karachi newspaper printed false things about me. Can I sue, and how long do I have?",
  "Civil defamation in Sindh under the Defamation Ordinance, 2002", "fed", "sindh", "answer",
  ["Publication of defamatory matter is actionable without proof of special damage; an action against a "
   "newspaper's author, editor, proprietor or publisher must be taken within six months after the publication "
   "came to the person's notice."],
  necessary=[(2020, "4", 3), (2020, "12", 3)], relevant=[(2020, "3", 2)], negatives=[(3321, "3", 0)],
  must_not_serve=[(3321, "3")], check=[r"without proof of special damage", r"six months"])
c("S3-C10", "citizen", "F3-dv-kp", "liberty", ["en"], "latin",
  "In Mardan my husband's family beats me. Is domestic violence a crime in KP, and what is the punishment?",
  "Offence of domestic violence under the KP Act of 2021", "kp", "kp", "answer",
  ["Committing, aiding or abetting domestic violence is an offence punishable with imprisonment of not less than "
   "one year and up to five years, in addition to the fine the Penal Code provides."],
  necessary=[(4871, "3", 3)], negatives=[(6414, "7", 0)], must_not_serve=[(6414, "7")],
  check=[r"not less than one year", r"five years"])
c("S3-C11", "citizen", "F3-dv-balochistan", "liberty", ["en"], "latin",
  "In Quetta, can a court stop my abusive husband from contacting me or coming to my workplace?",
  "Protection orders under the Balochistan Domestic Violence Act, 2014", "balochistan", "balochistan", "answer",
  ["If satisfied that domestic violence has taken place, the court may pass a protection order prohibiting the "
   "accused from further violence, from entering the aggrieved person's workplace or places she frequents, and "
   "from communicating with her."],
  necessary=[(692, "8", 3)], relevant=[(692, "5", 1)],
  check=[r"protection order", r"place of employment", r"communicate"])
c("S3-C12", "citizen", "F3-dv-ict", "liberty", ["en"], "latin",
  "I live in Islamabad and my brother is violent at home. How quickly will a court hear my petition?",
  "Petition and protection orders under the Domestic Violence (Prevention and Protection) Act, 2026",
  "fed", "ict", "answer",
  ["An aggrieved person petitions, through a Protection Officer, the court where she resides or where the parties "
   "last lived together; the first hearing must be within seven days, and the court may pass a protection order "
   "if satisfied that violence prima facie has taken or is likely to take place."],
  necessary=[(2711, "5", 3), (2711, "8", 3)], relevant=[(2711, "4", 2)],
  check=[r"seven days", r"protection order", r"prima facie"])
c("S3-C13", "citizen", "F3-education-sindh", "routine", ["en"], "latin",
  "My son is 10 and we live in Larkana. Does the government have to give him free schooling?",
  "Free and compulsory education in Sindh", "sindh", "sindh", "answer",
  ["Every child aged five to sixteen has a right to free and compulsory education; no fee may be charged that "
   "prevents completion; private schools must give free education to at least ten percent of their students."],
  necessary=[(1682, "3", 3)], relevant=[(4419, "25A", 2)], check=[r"five to sixteen", r"ten percent"])
c("S3-C14", "citizen", "F3-education-punjab", "routine", ["en"], "latin",
  "Is schooling free and compulsory in Punjab, and up to which class?",
  "Free and compulsory education in Punjab", "punjab", "punjab", "answer",
  ["Every child has a right to free and compulsory education from class one to ten (or the notified non-formal or "
   "vocational alternatives)."],
  necessary=[(6127, "3", 3)], relevant=[(4419, "25A", 2)], check=[r"class one to ten"])
c("S3-C15", "citizen", "F3-education-ict", "routine", ["en"], "latin",
  "Can a government school in Islamabad charge my daughter fees?",
  "Right to Free and Compulsory Education Act, 2012 (ICT)", "fed", "ict", "answer",
  ["Every child has a fundamental right to free and compulsory education in a neighbourhood school, and no child "
   "is liable to pay any fee or charge that would prevent completing education; the Constitution requires free "
   "and compulsory education for ages five to sixteen."],
  necessary=[(4227, "3", 3)], relevant=[(4419, "25A", 2)], check=[r"neighbourhood school", r"fee"])
c("S3-C16", "citizen", "F3-consumer-sindh", "money", ["en"], "latin",
  "A Karachi shop sold me a faulty fridge. How do I bring a claim?",
  "Notice and claim under the Sindh Consumer Protection Act, 2014", "sindh", "sindh", "answer",
  ["The consumer first serves written notice on the manufacturer or service provider, who must reply within fifteen "
   "days; a claim for damages is then filed before the Consumer Court."],
  necessary=[(1727, "29", 3), (1727, "26", 3)], negatives=[(6267, "28", 0)], must_not_serve=[(6267, "28")],
  check=[r"fifteen days", r"Consumer Court"])
c("S3-C17", "citizen", "F3-consumer-kp", "money", ["en"], "latin",
  "Who can file a consumer complaint in KP?", "Consumers Protection Act, 1997 (KP) complaint", "kp", "kp", "answer",
  ["A complaint about goods or services may be filed with the Consumer Court by the consumer, a recognised "
   "consumers' association, or the authorised Director or officer."],
  necessary=[(3420, "13", 3)], check=[r"recognized consumers association", r"Director"])
c("S3-C18", "citizen", "F3-consumer-balochistan", "money", ["en"], "latin",
  "Where do I complain in Balochistan about a defective product?",
  "Consumers Protection Act, 2003 (Balochistan) complaint", "balochistan", "balochistan", "answer",
  ["A complaint may be filed with the Consumer Court by the consumer, the Council, a recognised consumers' "
   "association, an authorised government officer or the authority."],
  necessary=[(1032, "14", 3)], check=[r"filed with the Court", r"consumers association"])
c("S3-C19", "citizen", "F3-domestic-child-punjab", "liberty", ["en"], "latin",
  "Can we hire a 13-year-old girl as a maid in our house in Lahore?",
  "Prohibition on employing children as domestic workers in Punjab", "punjab", "punjab", "answer",
  ["No child under fifteen may work in a household in any capacity, and a domestic worker under eighteen may do "
   "only light, part-time work."],
  necessary=[(6177, "3", 3)], check=[r"15 years", r"light work"])
c("S3-C20", "citizen", "F3-hindu-marriage-sindh", "family", ["en"], "latin",
  "We are Hindus in Mirpurkhas. What are the conditions for our marriage and must it be registered?",
  "Sindh Hindus Marriage Act, 2016", "sindh", "sindh", "answer",
  ["Both parties must be eighteen or above, able to and freely consenting, outside the prohibited degrees, with no "
   "living spouse, and two witnesses present; the marriage must be registered with the Union Council or municipal "
   "authority within 45 days."],
  necessary=[(2022, "4", 3), (2022, "6", 3)], negatives=[(3483, "4", 0)], must_not_serve=[(3483, "4")],
  check=[r"18 years", r"45 days", r"two witnesses"])

# ---------------------------------------------------------------- professional lookups (12)
c("S3-P01", "professional", "F3-antirape-cells", "liberty", ["en"], "latin",
  "Which law now provides for anti-rape crisis cells, and who establishes them?",
  "Anti-rape crisis cells under the Anti-Rape (Investigation and Trial) Act, 2021", "fed", "punjab", "answer",
  ["Under the Anti-Rape (Investigation and Trial) Act, 2021 the Secretary, Ministry of Law and Justice, in "
   "consultation with the provincial chief secretary or ICT chief commissioner, establishes anti-rape crisis cells "
   "in public hospitals."],
  necessary=[(3070, "4", 3)], negatives=[(5366, "4", 0)], must_not_serve=[(5366, "4")],
  check=[r"ministry of law and justice", r"crisis cells"])
c("S3-P02", "professional", "F3-antirape-cells", "liberty", ["en"], "latin",
  "In March 2021, who was empowered to establish anti-rape crisis cells?",
  "Anti-rape crisis cells as at March 2021 (Anti-Rape Ordinance, 2020)", "fed", "punjab", "answer",
  ["As at March 2021 the Anti-Rape (Investigation and Trial) Ordinance, 2020 empowered the Prime Minister to "
   "establish or designate anti-rape crisis cells in public hospitals."],
  as_of="2021-03-01",
  necessary=[(5366, "4", 3)], negatives=[(3070, "4", 0)], must_not_serve=[(3070, "4")],
  check=[r"Prime Minister shall establish"])
c("S3-P03", "professional", "F3-harassment-punjab", "privacy", ["en"], "latin",
  "Forum for a workplace harassment complaint in Punjab", "Punjab text of the Protection Against Harassment of "
  "Women at the Workplace Act, 2010", "punjab", "punjab", "answer",
  ["An employee may complain either to the Ombudsperson or to the Inquiry Committee; the Ombudsperson issues a "
   "show-cause notice within three days, and the accused answers within five days."],
  # the federal Act (doc 2105) 'extends to the whole of Pakistan' (its s.1), so in Punjab it is relevant, not a
  # trap; the Punjab text as amended in Punjab is the one that answers
  necessary=[(6263, "8", 3)], relevant=[(2105, "8", 2)],
  check=[r"either to the", r"Inquiry Committee", r"5 days|five days"])
c("S3-P04", "professional", "F3-harassment-ajk", "privacy", ["en"], "latin",
  "Inquiry procedure for a workplace harassment complaint in Azad Kashmir",
  "AJK Protection against Harassment of Women at the Workplace Act, 2014", "ajk", "ajk", "answer",
  ["Within three days of a written complaint the Inquiry Committee communicates the charges to the accused, who "
   "must file a written defence within seven days, failing which the Committee proceeds ex parte."],
  necessary=[(10226, "4", 3)], equivalent=[(11035, "4")], check=[r"three days", r"seven days", r"ex-parte"])
c("S3-P05", "professional", "F3-torture-confession", "liberty", ["en"], "latin",
  "Admissibility of a confession obtained by torture", "Section 3 Torture and Custodial Death Act, 2022", "fed",
  "sindh", "answer",
  ["A statement, information or confession obtained by a public official through torture or cruel, inhuman or "
   "degrading treatment is inadmissible against the person who made it, and an official who knowingly uses it is "
   "punishable."],
  necessary=[(2461, "3", 3)], check=[r"inadmissible", r"torture"])
c("S3-P06", "professional", "F3-torture-offence", "liberty", ["en"], "latin",
  "Is custodial torture by a public official bailable?", "Section 8 Torture and Custodial Death Act, 2022",
  "fed", "punjab", "answer",
  ["A public official who commits, abets or conspires in torture is punished as Chapter XVI PPC prescribes for the "
   "harm caused; the offence is cognizable, non-compoundable and non-bailable."],
  necessary=[(2461, "8", 3)], check=[r"non-bailable", r"Chapter XVI"])
c("S3-P07", "professional", "F3-trafficking", "liberty", ["en"], "latin",
  "Offence and punishment of trafficking in persons", "Section 3 Prevention of Trafficking in Persons Act, 2018",
  "fed", "kp", "answer",
  ["Recruiting, harbouring, transporting, providing or obtaining a person for compelled labour, organised beggary "
   "or sexual exploitation by force, fraud or coercion is punishable with up to ten years and fine up to one "
   "million rupees; against a child or woman, up to fourteen years."],
  necessary=[(2398, "3", 3)], check=[r"ten years", r"fourteen years", r"force, fraud or coercion"])
c("S3-P08", "professional", "F3-organ-trade", "liberty", ["en"], "latin",
  "Commercial dealing in human organs — offence", "Section 11 Transplantation of Human Organs and Tissues Act, 2010",
  "fed", "ict", "answer",
  ["Making or receiving payment for the supply of a human organ, or offering, seeking or negotiating such a supply "
   "for payment, is an offence under section 11."],
  necessary=[(1943, "11", 3)], relevant=[(1943, "9", 2)], check=[r"payment for the supply"])
c("S3-P09", "professional", "F3-zainab-alert", "liberty", ["en"], "latin",
  "Penalty for a police officer who fails to act on a missing-child report in Islamabad",
  "Section 9 Zainab Alert, Response and Recovery Act, 2020", "fed", "ict", "answer",
  ["A police officer who does not comply with section 8 in a missing or abducted child case, or an officer who "
   "wilfully delays the information, faces one to two years' imprisonment and fine of Rs. 50,000 to Rs. 100,000."],
  necessary=[(2850, "9", 3)], relevant=[(2850, "3", 1)], check=[r"not less than 1 year", r"50,000"])
c("S3-P10", "professional", "F3-senior-abandonment-ict", "family", ["en"], "latin",
  "Penalty for abandoning a senior citizen in Islamabad", "Section 20 ICT Senior Citizens Act, 2021", "fed", "ict",
  "answer", ["A person responsible for a senior citizen's care who abandons him with intent to do so wholly is "
             "punishable by the Grievance Committee with fine up to one hundred thousand rupees."],
  necessary=[(2884, "20", 3)], check=[r"one hundred thousand", r"Grievance Committee"])
c("S3-P11", "professional", "F3-senior-card-kp", "routine", ["en"], "latin",
  "Senior citizen card and privileges in KP", "Section 9 KP Senior Citizens Act, 2014", "kp", "kp", "answer",
  ["On turning sixty a senior citizen may apply for a senior citizen card, giving privileges such as free entry to "
   "public museums, libraries and parks, separate hospital counters and medical concessions."],
  necessary=[(4922, "9", 3)], check=[r"sixty", r"senior citizen card"])
c("S3-P12", "professional", "F3-senior-card-ict", "routine", ["en"], "latin",
  "Senior citizen card and privileges in Islamabad", "Section 11 ICT Senior Citizens Act, 2021", "fed", "ict",
  "answer", ["On turning sixty a senior citizen may apply for a card giving privileges such as free entry to "
             "public museums and parks, express lanes in government establishments and separate hospital counters."],
  necessary=[(2884, "11", 3)], negatives=[(4922, "9", 0)], must_not_serve=[(4922, "9")],
  check=[r"sixty years", r"express lanes"])

# ---------------------------------------------------------------- procedural (8)
c("S3-R01", "procedural", "F3-rent-ajk-appeal", "deadline", ["en"], "latin",
  "The Rent Controller in Mirpur decided against me. How long do I have to appeal, and to whom?",
  "Appeal under the AJK Rent Restriction Act, 1986", "ajk", "ajk", "answer",
  ["An appeal lies to the District Judge within thirty days of the Controller's final order; no appeal lies from "
   "an interlocutory order."],
  necessary=[(10394, "18", 3)], negatives=[(10096, "13", 0), (11195, "13", 0)],
  must_not_serve=[(10096, "13"), (11195, "13")], check=[r"thirty days", r"District Judge", r"interlocutory"])
c("S3-R02", "procedural", "F3-rent-ict-appeal", "deadline", ["en"], "latin",
  "How do I appeal a Rent Controller's order in Islamabad?", "Appeal under the Islamabad Rent Restriction "
  "Ordinance, 2001", "fed", "ict", "answer",
  ["A party aggrieved by the Controller's final order may appeal to the District Judge within thirty days."],
  necessary=[(3126, "21", 3)], check=[r"thirty days", r"District Judge"])
c("S3-R03", "procedural", "F3-rent-kp-appeal", "deadline", ["en"], "latin",
  "The Rent Controller in Abbottabad ordered my eviction. Can I appeal?", "Appeal under the WP Urban Rent "
  "Restriction Ordinance, 1959 (KP text)", "kp", "kp", "answer",
  ["An order under sections 4, 10, 12 or 13 may be appealed in writing to the District Judge within thirty days; "
   "no appeal lies from an interlocutory order."],
  necessary=[(2234, "15", 3)], check=[r"thirty days", r"District Judge"])
c("S3-R04", "procedural", "F3-rti-punjab", "routine", ["en"], "latin",
  "How do I request information from a Punjab government office? Do I have to say why I want it?",
  "Application under the Punjab Transparency and Right to Information Act, 2013", "punjab", "punjab", "answer",
  ["Apply to the public information officer on the request form or plain paper; the applicant need not give "
   "reasons, only an adequate description of the information."],
  necessary=[(6185, "10", 3)], relevant=[(1714, "5", 2)], check=[r"plain paper", r"reasons"])
c("S3-R05", "procedural", "F3-rti-federal", "routine", ["en"], "latin",
  "How do I ask a federal ministry for information?", "Request under the Right of Access to Information Act, 2017",
  "fed", "ict", "answer",
  ["A citizen makes a written request to the public body through its designated official — in person, by mail, "
   "fax, online or e-mail — identifying the information in sufficient detail and giving contact details."],
  necessary=[(2213, "11", 3)], check=[r"designated official", r"in writing"])
c("S3-R06", "procedural", "F3-legal-aid-punjab", "routine", ["en"], "latin",
  "I cannot afford a lawyer in Punjab. How do I apply for free legal aid?", "Application to the Punjab Legal Aid "
  "Agency", "punjab", "punjab", "answer",
  ["An indigent person applies to the Agency with an application supported by an affidavit; if refused, he may "
   "appeal within the time section 9 sets."],
  necessary=[(6325, "9", 3)], check=[r"indigent person", r"affidavit"])
c("S3-R07", "procedural", "F3-preemption-punjab", "deadline", ["en"], "latin",
  "My neighbour sold his land in Sahiwal to an outsider. How do I claim my right of pre-emption?",
  "Demands of pre-emption (talbs) under the Punjab Pre-emption Act, 1991", "punjab", "punjab", "answer",
  ["The right is extinguished unless the pre-emptor makes, in order, talb-i-muwathibat (an immediate demand in the "
   "sitting where he learns of the sale), talb-i-ishhad (demand by establishing evidence) and talb-i-khusumat."],
  necessary=[(2716, "13", 3)], check=[r"muwathibat", r"ishhad", r"khusumat"])
c("S3-R08", "procedural", "F3-mutation-punjab", "property", ["en"], "latin",
  "My father died and left agricultural land in Punjab. How do I get it entered in my name?",
  "Reporting inherited land to the Patwari for mutation", "punjab", "punjab", "answer",
  ["A person acquiring a right in an estate by inheritance must report it to the Patwari, who records it in the "
   "Roznamcha and gives a copy of the report free of charge."],
  necessary=[(4389, "42", 3)], check=[r"Patwari", r"inheritance"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5), each in its family
c("S3-U01", "urdu", "F3-rent-ict", "property", ["ur"], "arabic",
  "اسلام آباد میں مالک مکان کرایہ دار کو کن صورتوں میں نکال سکتا ہے؟",
  "Eviction grounds in Islamabad (Urdu variant of S3-C01)", "fed", "ict", "answer",
  ["Section 17 of the Islamabad Rent Restriction Ordinance, 2001: application to the Controller on the listed "
   "grounds."], necessary=[(3126, "17", 3)], check=[r"Controller"])
c("S3-U02", "urdu", "F3-childmar-punjab", "family", ["ur-Latn"], "roman_urdu",
  "Punjab mein ab larki ki shadi ki kam az kam umar kya hai?",
  "Child marriage in Punjab today (Roman Urdu variant of S3-C03)", "punjab", "punjab", "answer",
  ["A child is anyone under eighteen; marrying a child is punishable."],
  necessary=[(3382, "2", 3), (3382, "4", 3)], negatives=[(3227, "2", 0)], must_not_serve=[(3227, "2")],
  check=[r"under eighteen years of age"])
c("S3-U03", "urdu", "F3-education-sindh", "routine", ["ur"], "arabic",
  "کیا سندھ میں بچوں کی تعلیم مفت اور لازمی ہے؟",
  "Free education in Sindh (Urdu variant of S3-C13)", "sindh", "sindh", "answer",
  ["Yes, for every child aged five to sixteen."], necessary=[(1682, "3", 3)], check=[r"five to sixteen"])
c("S3-U04", "urdu", "F3-dv-kp", "liberty", ["ur-Latn"], "roman_urdu",
  "KP mein ghar mein aurat par tashaddud ki saza kya hai?",
  "Domestic violence punishment in KP (Roman Urdu variant of S3-C10)", "kp", "kp", "answer",
  ["Imprisonment of one to five years, plus the Penal Code fine."], necessary=[(4871, "3", 3)],
  check=[r"not less than one year"])
c("S3-U05", "urdu", "F3-rent-ajk-appeal", "deadline", ["ur"], "arabic",
  "آزاد کشمیر میں رینٹ کنٹرولر کے فیصلے کے خلاف اپیل کتنے دن میں کی جا سکتی ہے؟",
  "Rent appeal in AJK (Urdu variant of S3-R01)", "ajk", "ajk", "answer",
  ["Within thirty days, to the District Judge."], necessary=[(10394, "18", 3)], check=[r"thirty days"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S3-X01", "unanswerable", "F3-x-foreign-rent", "property", ["en"], "latin",
  "What are a tenant's rights against eviction in Dubai?", "Foreign rent law", "foreign", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from Islamabad or Punjab rent law"],
                  why="the corpus is Pakistani law only"),
  negatives=[(3126, "17", 0)])
c("S3-X02", "unanswerable", "F3-x-judgment", "privacy", ["en"], "latin",
  "What did the Lahore High Court decide in the challenge to the Punjab Defamation Act, 2024?",
  "A judgment on a statute", "punjab", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["describing the Act instead", "summarising from model memory"],
                  why="the corpus holds no judgments"),
  negatives=[(3321, "3", 0)])
c("S3-X03", "unanswerable", "F3-x-future-wage", "money", ["en"], "latin",
  "What will Punjab's minimum wage be next July?", "A rate not yet declared", "punjab", None, "abstain", [],
  abstention=dict(code="abstained", requiredClarification=[],
                  unsafeAlternatives=["quoting a past notification as next year's rate"],
                  why="a future rate is not law until the Government declares it by notification"))
c("S3-X04", "unanswerable", "F3-x-statistics", "family", ["en"], "latin",
  "How many cases have been registered under the Punjab Child Marriage Restraint Act, 2026 so far?",
  "Enforcement statistics", "punjab", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["inventing a figure"],
                  why="the corpus holds statutes, not case or police statistics"))
c("S3-X05", "unanswerable", "F3-x-strategy", "property", ["en"], "latin",
  "Should I take my tenant to the Rent Controller or settle with him? Which will get me a better result?",
  "Litigation strategy on undisclosed facts", "fed", None, "abstain", [],
  abstention=dict(code="professional_review_required", requiredClarification=["facts", "documents", "goals"],
                  unsafeAlternatives=["recommending a course of action"],
                  why="choosing a litigation strategy is legal advice"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 3: provinces, territories and time — jurisdiction pairs across Punjab, Sindh, "
                              "KP, Balochistan, ICT and AJK, and temporal pairs at two dates."))
