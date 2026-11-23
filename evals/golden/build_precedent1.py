"""golden-pk-v1 precedent set 1 (D-133): 58 precedent questions over the Supreme Court, Lahore and Peshawar High
Courts. Gold is judgment paragraphs, found by reading (peek_judgment.py), never by the precedent search.

    python evals/golden/build_precedent1.py      # rebuilds the set from the database and checks every case

Strata: issue (a legal question a judgment answers), authority (the same question for a court elsewhere), temporal
(asked at an earlier date: a later judgment did not exist), case_lookup (a case by its printed number), provision
(the judgments on a named provision), urdu (Urdu and Roman Urdu variants, in their English case's family), and
unanswerable (a court whose judgments are not held, or a date before coverage).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from precedent_common import PrecedentSet, build  # noqa: E402

ps = PrecedentSet("precedent1")
c = ps.case

# ---------------------------------------------------------------- issue: Supreme Court (15)
c("P1-I01", "issue", "FP1-bail-further-inquiry", "liberty", ["en"], "latin",
  "When does a case fall within 'further inquiry' for bail under section 497(2) CrPC, and what are 'reasonable "
  "grounds'?", "The meaning of further inquiry and reasonable grounds in bail", "sindh", "answer",
  ["Further inquiry presupposes a tentative assessment that may create doubt about the accused's involvement.",
   "'Reasonable grounds' are grounds legally tenable, admissible in evidence and appealing to a reasonable judicial "
   "mind, as opposed to whimsical, arbitrary or presumptuous."],
  necessary=[(4414, "6", 3), (6231, "6", 3)], relevant=[(8400, "12", 2)],
  check=[r"further inquiry", r"tentative assessment", r"legally tenable", r"whimsical"])
c("P1-I02", "issue", "FP1-mutation-title", "property", ["en"], "latin",
  "Does a mutation entry in the revenue record give a person title to land?", "Evidentiary value of a mutation",
  "punjab", "answer",
  ["Mutation does not confer title; it may be considered as a piece of evidence if effected in accordance with law."],
  necessary=[(4550, "6", 3)], check=[r"mutation does not confer title", r"piece of\s+evidence"])
c("P1-I03", "issue", "FP1-gift-ingredients", "property", ["en"], "latin",
  "What must be pleaded and proved for a valid oral gift (hiba) of property?", "Ingredients and proof of a gift",
  "balochistan", "answer",
  ["The basic ingredients of a valid gift are offer, acceptance and delivery of possession.",
   "The donee bears a heavy onus and must establish the date, time and place of the offer and acceptance."],
  necessary=[(6514, "4", 3), (5903, "12", 3)],
  check=[r"offer, acceptance and delivery of possession", r"date, time and place"])
c("P1-I04", "issue", "FP1-talb-muwathibat", "property", ["en"], "latin",
  "Under the Khyber Pakhtunkhwa Pre-emption Act, how promptly must the first demand (Talb-i-Muwathibat) be made, "
  "and how must it be proved?", "Talb-i-Muwathibat under s.13 KP Pre-emption Act 1987", "kp", "answer",
  ["Section 13 requires Talb-i-Muwathibat immediately on acquiring knowledge of the sale, proved through "
   "unimpeachable evidence; the requirement is foundational, not merely procedural."],
  necessary=[(7506, "5", 3)],
  check=[r"immediately upon acquiring knowledge", r"unimpeachable evidence", r"not merely procedural"])
c("P1-I05", "issue", "FP1-attesting-witness", "property", ["en"], "latin",
  "Can the scribe of an agreement to sell stand in for an attesting witness under Article 79 of the Qanun-e-Shahadat "
  "Order?", "Scribe versus attesting witness, Art. 79 QSO", "punjab", "answer",
  ["A scribe signs in a different capacity and with a different state of mind from an attesting witness; a scribe "
   "who signed without the intention of attesting does not satisfy Article 79."],
  necessary=[(7719, "9", 3), (5020, "10", 3)], relevant=[(7719, "8", 2)],
  check=[r"different state of mind", r"intention of attesting"])
c("P1-I06", "issue", "FP1-res-judicata", "civil-procedure", ["en"], "latin",
  "When does res judicata under section 11 CPC bar a second suit?", "Constituents of res judicata", "ict", "answer",
  ["The matter directly and substantially in issue must be the same, between the same parties, and finally decided "
   "by a competent court.", "A second suit on a distinct cause of action and materially altered facts is not barred."],
  necessary=[(5937, "8", 3), (7515, "6", 3)],
  check=[r"directly and substantially in issue", r"same parties", r"finally decided", r"distinct cause of action"])
c("P1-I07", "issue", "FP1-narcotics-custody", "liberty", ["en"], "latin",
  "In a narcotics case, what happens to a conviction if the prosecution cannot prove safe custody and safe "
  "transmission of the samples to the laboratory?", "Chain of custody in narcotics cases", "kp", "answer",
  ["Proof of the safe chain of custody and transmission of samples from the police station to the laboratory is a "
   "sine qua non for sustaining a conviction."],
  necessary=[(7595, "6", 3)], relevant=[(5298, "8", 2)], check=[r"safe chain of custody", r"sine qua non"])
c("P1-I08", "issue", "FP1-benefit-of-doubt", "liberty", ["en"], "latin",
  "Does an accused get the benefit of doubt only when there are many doubts in the prosecution case?",
  "A single reasonable doubt suffices", "punjab", "answer",
  ["Even a single circumstance creating reasonable doubt in a prudent mind entitles the accused to the benefit of "
   "doubt, as of right and not as grace."],
  necessary=[(5298, "8", 3)], check=[r"single circumstance", r"not as a matter of grace but as a matter of right"])
c("P1-I09", "issue", "FP1-quash-fir", "liberty", ["en"], "latin",
  "Can a High Court quash an FIR or a police investigation under section 561-A CrPC?",
  "Scope of s.561-A CrPC", "punjab", "answer",
  ["No: section 561-A reaches judicial or court proceedings only, not FIR registration or police investigation."],
  necessary=[(4362, "4", 3)], relevant=[(4362, "5", 2)],
  check=[r"no power under Section 561-A", r"judicial or court proceedings"])
c("P1-I10", "issue", "FP1-upgradation", "service", ["en"], "latin",
  "Is upgradation of a post the same as promotion, and is it a vested right of a civil servant?",
  "Upgradation versus promotion", "ict", "answer",
  ["Upgradation of a post is not a vested right; it stems from a policy decision and is not to be mixed up with "
   "promotion."],
  necessary=[(3920, "9", 3), (7060, "5", 3)],
  check=[r"upgradation of a post is not a vested right", r"mixed up with\s+(the\s+)?promotion"])
c("P1-I11", "issue", "FP1-specific-performance", "property", ["en"], "latin",
  "Is a buyer entitled to specific performance of an agreement to sell as of right if he never deposited the "
  "balance price?", "Discretion and readiness in specific performance", "sindh", "answer",
  ["Specific performance is discretionary; the court asks whether the buyer was, at the relevant time, willing to "
   "perform, and not depositing the balance is a sign of unwillingness."],
  necessary=[(7650, "6", 3)],
  check=[r"dependent on the discretion of the Court", r"willing to perform", r"unwillingness"])
c("P1-I12", "issue", "FP1-condonation", "civil-procedure", ["en"], "latin",
  "To have delay condoned under section 5 of the Limitation Act, must the applicant explain the whole period of "
  "delay?", "Explaining delay for condonation", "balochistan", "answer",
  ["The party seeking condonation must explain the delay of each and every day; time spent before a wrong forum is "
   "not condoned without good faith."],
  necessary=[(6979, "4", 3)], check=[r"each\s+and every day", r"wrong forum"])
c("P1-I13", "issue", "FP1-ata-compounding", "liberty", ["en"], "latin",
  "Can an offence under section 7 of the Anti-Terrorism Act 1997 be compounded on a compromise?",
  "Compounding terrorism offences", "punjab", "answer",
  ["No: compounding an offence under section 7 of the ATA is barred by section 345(7) CrPC."],
  necessary=[(7435, "6", 3)], check=[r"compound the offence under section 7", r"subsection \(7\) of\s+section 345"])
c("P1-I14", "issue", "FP1-police-confession", "liberty", ["en"], "latin",
  "Can a confession made by an accused to a police officer be proved against him at trial?",
  "Confession to police, Art. 38 QSO", "kp", "answer",
  ["No: Article 38 of the Qanun-e-Shahadat Order 1984 bars proof of a confession made to a police officer."],
  necessary=[(4310, "12", 3)], check=[r"Article 38", r"No confession made to a police officer shall be proved"])
c("P1-I15", "issue", "FP1-co-heirs", "property", ["en"], "latin",
  "Can one co-heir claim adverse possession against the others, or lose an inheritance by delay in challenging a "
  "mutation?", "Rights among co-heirs", "sindh", "answer",
  ["Heirs own the property immediately on the predecessor's death; one co-sharer's possession is for all; delay in "
   "challenging a mutation does not extinguish the right; adverse possession does not apply among co-heirs."],
  necessary=[(5903, "12", 3)], check=[r"immediately upon death", r"adverse possession do not apply amongst co-heirs"])

# ---------------------------------------------------------------- issue: Lahore High Court (10)
c("P1-I16", "issue", "FP1-pre-arrest-bail", "liberty", ["en"], "latin",
  "What must an accused show to get bail before arrest (pre-arrest bail)?", "Conditions of pre-arrest bail",
  "punjab", "answer",
  ["Pre-arrest bail is an extraordinary relief protecting the innocent from cases lodged with mala fide or ulterior "
   "motives; mala fides is a pre-requisite besides the conditions of section 497(2) CrPC."],
  necessary=[(8400, "12", 3), (4414, "6", 3)], check=[r"mala fides?", r"extraordinary relief"])
c("P1-I17", "issue", "FP1-statutory-bail", "liberty", ["en"], "latin",
  "From which date is the period counted for bail on the statutory ground of delay in the conclusion of trial?",
  "Counting the statutory-delay period", "punjab", "answer",
  ["The period is counted from the date the accused was arrested in the case."],
  necessary=[(10312, "6", 3)], relevant=[(10312, "7", 2)],
  check=[r"arrested in this case", r"statutory ground of bail\s+due to delay in conclusion of trial"])
c("P1-I18", "issue", "FP1-cheque-489f", "money", ["en"], "latin",
  "What must the prosecution prove for the offence of dishonestly issuing a cheque under section 489-F PPC?",
  "Ingredients of s.489-F PPC", "punjab", "answer",
  ["Issuance of a cheque, with dishonest intention, to repay a loan or fulfil an obligation, and its dishonour on "
   "presentation."],
  necessary=[(9712, "10", 3)], relevant=[(9712, "11", 2), (14459, "11", 2)],
  check=[r"issuance of cheque", r"dishonest intention", r"repay a loan", r"dishonoured"])
c("P1-I19", "issue", "FP1-justice-of-peace", "liberty", ["en"], "latin",
  "Can proceedings before an ex-officio Justice of Peace under section 22-A(6) CrPC be transferred under section 526 "
  "CrPC?", "Justice of Peace is not a criminal court", "punjab", "answer",
  ["No: the ex-officio Justice of Peace performs quasi-judicial functions and is not a criminal court, so section "
   "526 CrPC does not apply."],
  necessary=[(8713, "8", 3)], check=[r"quasi-judicial", r"not a criminal court", r"526"])
c("P1-I20", "issue", "FP1-custody-welfare", "family", ["en"], "latin",
  "In a custody dispute over a minor, what is the court's paramount consideration, and what must a claimant who is "
  "not a blood relative show against the real parents?", "Welfare of the minor in custody", "punjab", "answer",
  ["The welfare of the minor is of paramount importance; a claimant with no blood relationship faces a greater "
   "threshold against the real parents."],
  necessary=[(9987, "6", 3)], check=[r"welfare of the minor, which holds paramount importance", r"greater\s+threshold"])
c("P1-I21", "issue", "FP1-khula-dower", "family", ["en"], "latin",
  "When a wife obtains khula in Punjab, must she return part of her dower, and is there still a ceiling after the "
  "Federal Shariat Court's decision?", "Surrender of dower on khula, s.10(5)-(6) Punjab Family Courts Act",
  "punjab", "answer",
  ["The Federal Shariat Court (Imran Anwar Khan) struck down the ceiling on surrender of dower in s.10(5)-(6) as "
   "repugnant to Islam, ineffective from 01.05.2022.",
   "Where khula is sought for the husband's cruelty and not mere dislike, ordering surrender of only part (25%) of "
   "the dower was upheld."],
  necessary=[(8425, "12", 3), (8425, "17", 3)], relevant=[(8425, "11", 2)],
  check=[r"ineffective from 01\.05\.2022", r"repugnant to Islam", r"not a case of Khula simpliciter"])
c("P1-I22", "issue", "FP1-temporary-injunction", "civil-procedure", ["en"], "latin",
  "What three conditions must a plaintiff show to get a temporary injunction?", "Conditions for temporary injunction",
  "punjab", "answer",
  ["A prima facie case, irreparable loss if refused, and the balance of convenience in the plaintiff's favour; the "
   "prima facie case is foundational."],
  necessary=[(10478, "7", 3), (12079, "7", 3)],
  check=[r"prima facie case", r"irreparable loss", r"balance of convenience", r"foundational"])
c("P1-I23", "issue", "FP1-juvenile-age", "liberty", ["en"], "latin",
  "When an accused claims to be a juvenile, on what documents is age decided, and who bears the burden of proving "
  "it?", "Age determination under s.8 JJSA 2018", "punjab", "answer",
  ["'In the absence of documents' means absence of authentic, admissible documents; the age inquiry is a voir dire "
   "not left to the police; an accused claiming juvenility must prove it by true documents."],
  necessary=[(9484, "6", 3), (9484, "8", 3)],
  check=[r"absence of authentic", r"voir dire", r"burden of proof lies on him"])
c("P1-I24", "issue", "FP1-registered-deed", "property", ["en"], "latin",
  "Which forum can cancel a registered deed alleged to have been procured by fraud?",
  "Cancellation of a registered instrument", "punjab", "answer",
  ["A registered document carries a statutory presumption of correctness; cancelling it needs a competent civil "
   "court under section 39 of the Specific Relief Act 1877 with section 9 CPC."],
  necessary=[(9348, "12", 3)],
  check=[r"presumption of correctness", r"Section 39 of the Specific Relief Act",
         r"Section 9 of the Code of Civil Procedure"])
c("P1-I25", "issue", "FP1-punjab-rent-ltc", "housing", ["en"], "latin",
  "Under the Punjab Rented Premises Act 2009, what must a tenant do after notice of an ejectment application, and "
  "what happens if leave to contest is refused?", "Leave to contest in Punjab rent cases", "punjab", "answer",
  ["The tenant must apply for leave to contest within the stipulated time under section 21; if it is refused the "
   "Rent Tribunal must pass a final order."],
  necessary=[(9892, "7", 3)], check=[r"leave to\s+contest", r"section 21", r"final order"])

# ---------------------------------------------------------------- issue: Peshawar High Court (10)
c("P1-I26", "issue", "FP1-talb-ishhad", "property", ["en"], "latin",
  "Who counts as an attesting witness of a notice of Talb-i-Ishhad in a pre-emption suit?",
  "Attesting witness of the notice of talb-i-ishhad", "kp", "answer",
  ["An attesting witness is one who saw the executant sign and signed the instrument as a witness (Article 79 QSO "
   "read with section 3 of the Transfer of Property Act)."],
  necessary=[(17863, "8", 3)],
  check=[r"talb-i-ishhad", r"Article 79", r"section 3 of the Transfer of Property Act"])
c("P1-I27", "issue", "FP1-nab-bail", "liberty", ["en"], "latin",
  "Can an accused facing a NAB reference get bail, although section 497 CrPC does not apply to accountability "
  "cases?", "Bail in hardship cases under the NAO", "kp", "answer",
  ["Section 497 CrPC does not apply to NAB charges, but the High Court may grant bail in hardship cases such as a "
   "shockingly long incarceration."],
  necessary=[(14561, "6", 3)], check=[r"497 Cr\.?P\.?C are not applicable", r"hardship cases"])
c("P1-I28", "issue", "FP1-ac-eviction", "housing", ["en"], "latin",
  "Can an Assistant Commissioner order the eviction of a tenant under the KP Alternate Dispute Resolution Act 2020 "
  "while ejectment proceedings are pending before the Rent Controller?",
  "Executive ADR versus a seized rent forum", "kp", "answer",
  ["No: once the Rent Controller has taken cognizance, the Assistant Commissioner is divested of jurisdiction under "
   "section 3(2) of the ADR Act 2020."],
  necessary=[(15762, "11", 3)], relevant=[(15762, "12", 2)],
  check=[r"divested of\s+jurisdiction", r"section\s+3\(2\) of the ADR Act"])
c("P1-I29", "issue", "FP1-fcr-rights", "rights", ["en"], "latin",
  "Which basic rights did the Frontier Crimes Regulation deny to people in the tribal areas?",
  "Rights denied under the FCR", "kp", "answer",
  ["Under the FCR there was no right of appeal, legal representation or reasoned evidence; clause 21 imposed "
   "collective punishment; the political agent held unchecked executive and judicial power."],
  necessary=[(15584, "48", 3)],
  check=[r"right to appeal", r"legal representation", r"collective punishment", r"clause 21"])
c("P1-I30", "issue", "FP1-fcr-merger", "rights", ["en"], "latin",
  "After the 25th Amendment merged the tribal areas into Khyber Pakhtunkhwa, do proceedings pending under the "
  "repealed FCR continue under it?", "Pending FCR proceedings after the merger", "kp", "answer",
  ["A larger bench (Suhbat Khan) held that only proceedings pending at the appeal or revision stage continue under "
   "the repealed FCR."],
  necessary=[(16568, "4", 3), (16568, "5", 3)],
  check=[r"appeal or revisional stage only", r"pending at the stage of appeal or revision"])
c("P1-I31", "issue", "FP1-cheque-bail", "money", ["en"], "latin",
  "In a cheque dishonour case under section 489-F PPC, does a very large amount bring the offence within the "
  "prohibitory clause for bail?", "Amount and the prohibitory clause, s.489-F", "kp", "answer",
  ["No: the PPC does not categorise this offence by amount; section 489-F is outside the prohibitory clause however "
   "large the cheque."],
  necessary=[(14459, "11", 3)],
  check=[r"no categorization of offence on the basis of amount", r"does not fall within the prohibitory clause"])
c("P1-I32", "issue", "FP1-mpo-detention", "liberty", ["en"], "latin",
  "Can a Deputy Commissioner use preventive detention under section 3 of the Maintenance of Public Order Ordinance "
  "against a person facing ordinary criminal cases?", "Preventive detention under s.3 MPO", "kp", "answer",
  ["No: conduct attracting other provisions of law is for the courts; preventive detention under section 3 MPO was "
   "not warranted, and the order was set aside."],
  necessary=[(14732, "3", 3)], relevant=[(14732, "4", 2)],
  check=[r"preventive detention under section 3\s+MPO", r"dealt with by the Courts"])
c("P1-I33", "issue", "FP1-interim-custody-appeal", "family", ["en"], "latin",
  "Is an order of a Guardian Judge refusing interim custody of a minor appealable under section 14 of the Family "
  "Courts Act 1964?", "Appeal against an interim custody order", "kp", "answer",
  ["The court held that such an order falls within 'a decision given' and is appealable under section 14."],
  necessary=[(14852, "7", 3)], check=[r"decision given", r"appealable"])
c("P1-I34", "issue", "FP1-dissolution-dower", "family", ["en"], "latin",
  "If a wife gets dissolution of marriage for cruelty and non-payment of maintenance rather than khula, does she "
  "keep her dower?", "Dower on dissolution other than khula", "kp", "answer",
  ["Yes: where dissolution is on grounds such as cruelty, non-payment of maintenance or expulsion, and not khula, "
   "the wife is entitled to dower, dowry and maintenance."],
  necessary=[(17400, "11", 3)],
  check=[r"not asked for dissolution of her marriage on the ground of Khula", r"entitled for recovery of dower"])
c("P1-I35", "issue", "FP1-women-property-kp", "property", ["en"], "latin",
  "What can the Ombudsperson do in Khyber Pakhtunkhwa when a woman has been unlawfully deprived of her property?",
  "Ombudsperson's powers, KP Enforcement of Women's Property Rights Act 2019", "kp", "answer",
  ["The Ombudsperson may direct restoration of possession and ownership through the Deputy Commissioner or police "
   "(s.5); intricate questions such as competing titles go to a court (s.6)."],
  necessary=[(15354, "11", 3)],
  check=[r"restoration of her property rights", r"Deputy Commissioner", r"competing titles"])

# ---------------------------------------------------------------- authority: the same question elsewhere (1)
c("P1-F01", "authority", "FP1-temporary-injunction", "civil-procedure", ["en"], "latin",
  "For a civil court in Khyber Pakhtunkhwa: what three conditions must a plaintiff show to get a temporary "
  "injunction?", "Conditions for temporary injunction, asked from KP", "kp", "answer",
  ["The same three conditions; a Lahore High Court judgment is persuasive, not binding, on a KP court (Art. 201)."],
  necessary=[(10478, "7", 3), (12079, "7", 3)],
  check=[r"prima facie case", r"irreparable loss", r"balance of convenience"])

# ---------------------------------------------------------------- temporal: a later judgment did not exist (3)
c("P1-T01", "temporal", "FP1-upgradation", "service", ["en"], "latin",
  "Is upgradation of a post the same as promotion, and is it a vested right of a civil servant?",
  "Upgradation versus promotion, asked in June 2023", "ict", "answer",
  ["Upgradation of a post is not a vested right (2022); the 2024 judgment did not yet exist."],
  necessary=[(7060, "5", 3)], must_not_serve=[3920], as_of="2023-06-30",
  check=[r"upgradation of a post is not a vested right"])
c("P1-T02", "temporal", "FP1-bail-further-inquiry", "liberty", ["en"], "latin",
  "When does a case fall within 'further inquiry' for bail under section 497(2) CrPC, and what are 'reasonable "
  "grounds'?", "Further inquiry, asked on 1 August 2025", "sindh", "answer",
  ["As in July 2025: further inquiry presupposes a tentative assessment creating doubt; the November 2025 judgment "
   "did not yet exist."],
  necessary=[(6231, "6", 3)], must_not_serve=[4414], as_of="2025-08-01",
  check=[r"tentative assessment", r"legally tenable"])
c("P1-T03", "temporal", "FP1-judges-transfer", "rights", ["en"], "latin",
  "What did the Supreme Court decide on the transfer of High Court judges to the Islamabad High Court under "
  "Article 200(1)?", "The judges-transfer case, asked on 1 July 2025 (short order only)", "ict", "answer",
  ["By the short order of 19.06.2025 (majority 3 to 2), transfer under Article 200(1) and appointment under "
   "Article 175A are distinct provisions; the detailed reasons came later."],
  necessary=[(5600, "1", 3)], must_not_serve=[4463], as_of="2025-07-01",
  check=[r"Article 200", r"175A", r"two distinct provisions"])

# ---------------------------------------------------------------- case lookup (4)
c("P1-C01", "case_lookup", "FP1-mutation-title", "property", ["en"], "latin",
  "Supreme Court Civil Appeal No. 415 of 2018", "A case by its number", "punjab", "answer",
  ["The judgment in that appeal."], necessary=[(4550, None, 3)], check=[r"mutation does not confer title"],
  task="case_lookup")
c("P1-C02", "case_lookup", "FP1-khula-dower", "family", ["en"], "latin",
  "Lahore High Court Writ Petition No. 12505 of 2020", "A case by its number", "punjab", "answer",
  ["The judgment in that petition."], necessary=[(8425, None, 3)], check=[r"Imran Anwar Khan"], task="case_lookup")
c("P1-C03", "case_lookup", "FP1-fcr-rights", "rights", ["en"], "latin",
  "Peshawar High Court Writ Petition No. 1741-P of 2012", "A case by its number", "kp", "answer",
  ["The judgment in that petition."], necessary=[(15584, None, 3)], check=[r"\bFCR\b"], task="case_lookup")
c("P1-C04", "case_lookup", "FP1-judges-transfer", "rights", ["en"], "latin",
  "Supreme Court Constitution Petition No. 22 of 2025 (transfer of judges to the Islamabad High Court)",
  "A case with a short order and its later detailed reasons", "ict", "answer",
  ["Both the short order (19.06.2025) and the detailed reasons (18.09.2025) decide that case."],
  necessary=[(5600, "1", 3), (4463, None, 3)], check=[r"Article 200", r"175A"], task="case_lookup")

# ---------------------------------------------------------------- provision: judgments on a named provision (4)
c("P1-S01", "provision", "FP1-justice-of-peace", "liberty", ["en"], "latin",
  "Judgments interpreting section 22-A(6) of the Code of Criminal Procedure", "Case law on s.22-A(6) CrPC",
  "punjab", "answer", ["Judgments construing the Justice of Peace's powers under section 22-A(6)."],
  necessary=[(8713, "8", 3)], check=[r"22-A\(6\)"])
c("P1-S02", "provision", "FP1-attesting-witness", "property", ["en"], "latin",
  "Case law on Article 79 of the Qanun-e-Shahadat Order 1984 (attesting witnesses)", "Case law on Art. 79 QSO",
  "punjab", "answer",
  ["Judgments on proof of attested documents by two attesting witnesses; the Peshawar judgment is persuasive in "
   "Punjab."],
  necessary=[(7719, "8", 3), (5020, "10", 3), (17863, "8", 3)], check=[r"Article 79", r"two attesting"])
c("P1-S03", "provision", "FP1-juvenile-age", "liberty", ["en"], "latin",
  "Case law on section 8 of the Juvenile Justice System Act 2018", "Case law on s.8 JJSA 2018", "punjab", "answer",
  ["Judgments on determining an accused's claimed juvenility."], necessary=[(9484, "6", 3)],
  check=[r"section 8 ibid"])
c("P1-S04", "provision", "FP1-cheque-489f", "money", ["en"], "latin",
  "Judgments on section 489-F of the Pakistan Penal Code", "Case law on s.489-F PPC", "kp", "answer",
  ["Judgments on dishonestly issuing a cheque; for a KP court the Peshawar judgment binds and the Lahore one "
   "persuades."],
  necessary=[(9712, "10", 3), (14459, "11", 3)], check=[r"489-F"])

# ---------------------------------------------------------------- Urdu / Roman Urdu, each in its family (5)
c("P1-U01", "urdu", "FP1-pre-arrest-bail", "liberty", ["ur-Latn"], "roman_urdu",
  "Zamanat qabl az giraftari kab milti hai? Kya bad-niyati sabit karna zaroori hai?",
  "Pre-arrest bail (Roman Urdu variant of P1-I16)", "punjab", "answer",
  ["Pre-arrest bail is extraordinary relief; mala fides must be shown."],
  necessary=[(8400, "12", 3), (4414, "6", 3)], check=[r"mala fides?"])
c("P1-U02", "urdu", "FP1-mutation-title", "property", ["ur-Latn"], "roman_urdu",
  "Kya intiqal (mutation) darj hone se zameen ki milkiyat mil jati hai?",
  "Mutation and title (Roman Urdu variant of P1-I02)", "punjab", "answer",
  ["Mutation does not confer title."], necessary=[(4550, "6", 3)], check=[r"mutation does not confer title"])
c("P1-U03", "urdu", "FP1-police-confession", "liberty", ["ur"], "arabic",
  "کیا ملزم کا پولیس کے سامنے کیا گیا اقبالِ جرم عدالت میں اس کے خلاف ثابت کیا جا سکتا ہے؟",
  "Confession to police (Urdu variant of P1-I14)", "kp", "answer",
  ["No: Article 38 QSO bars it."], necessary=[(4310, "12", 3)], check=[r"Article 38"])
c("P1-U04", "urdu", "FP1-cheque-489f", "money", ["ur-Latn"], "roman_urdu",
  "Cheque bounce ho jaye to 489-F ka muqadma kab banta hai?", "Ingredients of s.489-F (Roman Urdu variant of P1-I18)",
  "punjab", "answer", ["A cheque issued dishonestly to repay a loan or fulfil an obligation, and dishonoured."],
  necessary=[(9712, "10", 3)], check=[r"dishonest intention"])
c("P1-U05", "urdu", "FP1-custody-welfare", "family", ["ur"], "arabic",
  "بچے کی تحویل کے مقدمے میں عدالت سب سے زیادہ کس بات کو دیکھتی ہے؟",
  "Custody and the minor's welfare (Urdu variant of P1-I20)", "punjab", "answer",
  ["The welfare of the minor is paramount."], necessary=[(9987, "6", 3)], check=[r"paramount"])

# ---------------------------------------------------------------- unanswerable: not held, or before coverage (6)
_NOT_HELD = ["presenting another court's judgments as this court's view", "inventing a citation"]
for cid, fam, court, forum, q in (
        ("P1-X01", "FP1-x-shc", "SHC", "sindh",
         "What has the Sindh High Court held on personal bona fide need under the Sindh Rented Premises Ordinance 1979?"),
        ("P1-X02", "FP1-x-ihc", "IHC", "ict",
         "What has the Islamabad High Court held on section 20 of the Prevention of Electronic Crimes Act 2016?"),
        ("P1-X03", "FP1-x-bhc", "BHC", "balochistan",
         "What has the High Court of Balochistan held on the jurisdiction of the Levies Force?"),
        ("P1-X04", "FP1-x-fsc", "FSC", None,
         "What has the Federal Shariat Court ruled on riba (interest) in banking?"),
        ("P1-X05", "FP1-x-fcc", "FCC", None,
         "What has the Federal Constitutional Court decided about its own jurisdiction since the 27th Amendment?")):
    c(cid, "unanswerable", fam, "coverage", ["en"], "latin", q, f"Judgments of a court not held ({court})", forum,
      "abstain", [], abstention=dict(code="court_not_held", court=court, requiredClarification=[],
                                     unsafeAlternatives=_NOT_HELD,
                                     why=f"the corpus holds no judgment of this court ({court}); coverage must say so"))
c("P1-X06", "unanswerable", "FP1-x-before-coverage", "coverage", ["en"], "latin",
  "What was the Supreme Court's precedent on 'further inquiry' in bail matters?",
  "Asked as at 1 January 1995, before any held judgment existed", "punjab", "abstain", [], as_of="1995-01-01",
  abstention=dict(code="before_coverage", requiredClarification=[],
                  unsafeAlternatives=["citing a later judgment as if it existed in 1995"],
                  why="no held judgment had been decided by 1 January 1995"))

if __name__ == "__main__":
    sys.exit(build(ps, "Precedent stratum, set 1: Supreme Court, Lahore and Peshawar High Courts (D-133). Gold is "
                       "judgment paragraphs read in the released text; it names some of the judgments that answer, "
                       "not all."))
