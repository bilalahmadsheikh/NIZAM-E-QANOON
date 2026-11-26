"""golden-pk-v1 precedent set 2 (D-168): the precedent stratum widened toward 150 cases, over every court held. Gold is
judgment paragraphs found by reading (a plain SQL text match, then the paragraph read in full), never by the precedent
search it measures. Families are new (FP2-*), so the split places them by the same sha256 rule as set 1's, among
themselves (evals/precedent_eval.py split); set 1's families keep their places.

    python evals/golden/build_precedent2.py      # rebuilds the set from the database and checks every case

Strata as set 1 (build_precedent1.py). Set 2 leans on the paths set 1 found weak (D-133): case numbers in the forms
lawyers type them, named provisions, and Urdu and Roman Urdu questions. Federal Shariat Court, AJK and GB cases ask no
authority question (forum None), as set 1's FSC and FCC cases: the author's binding reading (precedent_common.
expected_status) covers Arts. 189 and 201 only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from precedent_common import PrecedentSet, build  # noqa: E402

ps = PrecedentSet("precedent2")
c = ps.case

# ---------------------------------------------------------------- issue: criminal evidence and procedure
c("P2-I01", "issue", "FP2-dying-declaration", "liberty", ["en"], "latin",
  "Can an accused be convicted on a dying declaration alone, and what must the prosecution show about it?",
  "Conviction on a dying declaration", "kp", "answer",
  ["A conviction can rest on a dying declaration alone, but the prosecution must show the deceased made it "
   "voluntarily, truthfully and in a fit state of mind, and that it inspires confidence."],
  necessary=[(15198, "6", 3)],
  check=[r"conviction can be based solely on a dying declaration", r"fit state of mind"])
c("P2-I02", "issue", "FP2-fir-delay", "liberty", ["en"], "latin",
  "What is the effect of an unexplained delay in lodging the FIR on the prosecution case?",
  "Unexplained delay in the FIR", "sindh", "answer",
  ["An unexplained delay in lodging the FIR, particularly one leaving room for consultation and deliberation, "
   "undermines the prosecution case."],
  necessary=[(95968, "17", 3)], relevant=[(115872, "8", 2)],
  check=[r"unexplained delay in lodging the FIR", r"consultation and deliberation"])
c("P2-I03", "issue", "FP2-extra-judicial-confession", "liberty", ["en"], "latin",
  "Can a conviction be based on an extra-judicial confession?", "Evidentiary value of an extra-judicial confession",
  "punjab", "answer",
  ["An extra-judicial confession is a weak type of evidence; as a rule of prudence it needs corroboration from "
   "independent, reliable evidence before it can found a conviction."],
  necessary=[(114209, "10", 3)], relevant=[(30223, "26", 2), (90263, "17", 2)],
  check=[r"weak type of evidence", r"requires corroboration"])
c("P2-I04", "issue", "FP2-identification-parade", "liberty", ["en"], "latin",
  "Is an identification of the accused reliable when it was made outside court with no test identification parade?",
  "Identification without a test identification parade", "sindh", "answer",
  ["Where no test identification parade was held under judicial supervision, with no persons of similar appearance "
   "and no safeguard against prior exposure, the identification is inherently suggestive."],
  necessary=[(24437, "7", 3)], check=[r"test\s+identification parade", r"inherently suggestive"])
c("P2-I05", "issue", "FP2-related-witness", "liberty", ["en"], "latin",
  "Can the evidence of eyewitnesses be discarded only because they are relatives of the deceased?",
  "Related versus interested witnesses", "kp", "answer",
  ["Mere relationship with the deceased does not make a witness unworthy of belief; a related witness is not "
   "necessarily an interested one."],
  necessary=[(111188, "8", 3)], relevant=[(111249, "6", 2), (23114, "16", 2)],
  check=[r"mere relationship", r"related witness is not necessarily an interested witness"])
c("P2-I06", "issue", "FP2-circumstantial-chain", "liberty", ["en"], "latin",
  "When can a conviction rest on circumstantial evidence alone?", "The unbroken chain of circumstantial evidence",
  "sindh", "answer",
  ["Each circumstance must be firmly established, and together they must form a complete and unbroken chain "
   "pointing to guilt and excluding every reasonable hypothesis of innocence."],
  necessary=[(87018, "12", 3)], relevant=[(87018, "16", 2)],
  check=[r"complete and unbroken chain", r"every\s+reasonable hypothesis"])
c("P2-I07", "issue", "FP2-bail-cancellation", "liberty", ["en"], "latin",
  "On what grounds can bail that has already been granted be cancelled?", "Grounds for cancelling bail", "sindh",
  "answer",
  ["Cancelling bail needs stronger and exceptional grounds than granting it: the order must be patently illegal or "
   "perverse, or the accused must have misused the concession."],
  necessary=[(102038, "6", 3)], relevant=[(102038, "8", 2)],
  check=[r"stronger and exceptional grounds", r"misused the concession"])
c("P2-I08", "issue", "FP2-acquittal-265k", "liberty", ["en"], "latin",
  "Can a trial court acquit an accused before the prosecution evidence is complete?",
  "Acquittal at any stage under s.265-K CrPC", "sindh", "answer",
  ["Yes: section 265-K lets the court acquit at any stage, after hearing both sides and for reasons recorded, if "
   "there is no probability of conviction."],
  necessary=[(39546, "10", 3)], relevant=[(85878, "8", 2)],
  check=[r"at any stage", r"no probability of the accused being convicted"])
c("P2-I09", "issue", "FP2-dowry-depreciation", "family", ["en"], "latin",
  "When dowry articles are decreed, how is their worth fixed after years of use?",
  "Depreciation of dowry articles", "kp", "answer",
  ["No fixed statutory percentage governs depreciation of dowry articles; the value must reflect each proved "
   "article's nature, use, remaining serviceability, condition and a realistic market assessment."],
  necessary=[(111258, "30", 3)], check=[r"no fixed statutory percentage", r"depreciation"])

# ---------------------------------------------------------------- issue: property, civil procedure
c("P2-I10", "issue", "FP2-adverse-possession", "property", ["en"], "latin",
  "What must a person prove to claim ownership of land by adverse possession?", "Ingredients of adverse possession",
  "kp", "answer",
  ["The possession must be open, notorious, continuous, exclusive and hostile, specifically pleaded as to time, "
   "nature and extent; permissive or non-exclusive possession does not suffice."],
  necessary=[(16538, "6", 3), (16538, "7", 3)],
  check=[r"open, notorious, continuous, exclusive and hostile", r"permissive in character"])
c("P2-I11", "issue", "FP2-pardanasheen", "property", ["en"], "latin",
  "What must be proved when a property transaction with an old, illiterate pardanasheen lady is challenged?",
  "Transactions with pardanasheen ladies", "punjab", "answer",
  ["Mandatory conditions must be met transparently and proved by evidence of a high degree (Phul Peer Shah)."],
  necessary=[(115714, "3", 3)], relevant=[(122341, "16", 2)],
  check=[r"Pardanasheen", r"mandatory conditions"])
c("P2-I12", "issue", "FP2-benami", "property", ["en"], "latin",
  "How do courts decide whether property bought in another person's name is a benami transaction?",
  "Proof of a benami transaction", "punjab", "answer",
  ["The person alleging benami bears the burden; the source of funds is the acid test but not conclusive, and "
   "possession of title documents, conduct and enjoyment of the property are weighed."],
  necessary=[(6670, "6", 3)], relevant=[(113609, "3", 2)],
  check=[r"burden of proving", r"source of funds"])
c("P2-I13", "issue", "FP2-inheritance-limitation", "property", ["en"], "latin",
  "Does limitation bar a daughter's claim to her share of inheritance many years after her father's death?",
  "Limitation in inheritance claims", "punjab", "answer",
  ["On the opening of succession the property devolves on the heirs; efflux of time does not extinguish the right "
   "of inheritance, and limitation runs from when a co-sharer's right is denied."],
  necessary=[(12107, "11", 3)], relevant=[(15813, "8", 2)],
  check=[r"efflux of time did not extinguish the right of inheritance"])
c("P2-I14", "issue", "FP2-rejection-of-plaint", "civil-procedure", ["en"], "latin",
  "Can a plaint be rejected under Order VII Rule 11 CPC when the case turns on disputed facts?",
  "Rejection of plaint and disputed questions", "sindh", "answer",
  ["No: where controversial questions of fact or law arise, Order VII Rule 11 cannot be invoked; the court frames "
   "an issue and decides it on evidence."],
  necessary=[(34952, "24", 3)], relevant=[(108381, "4", 2)],
  check=[r"Order VII, Rule 11, C\.P\.C\. cannot be invoked", r"frame issue"])
c("P2-I15", "issue", "FP2-ex-parte-decree", "civil-procedure", ["en"], "latin",
  "How is setting aside an ex parte decree under Order IX Rule 13 CPC different from a challenge under section "
  "12(2) CPC?", "Order IX Rule 13 versus s.12(2) CPC", "sindh", "answer",
  ["Under Order IX Rule 13 the defendant must show sufficient cause for his absence; the grounds of section 12(2) "
   "(fraud, misrepresentation, want of jurisdiction) are different."],
  necessary=[(93505, "22", 3)], check=[r"sufficient cause for his absence", r"12\(2\)"])

# ---------------------------------------------------------------- issue: constitutional and service
c("P2-I16", "issue", "FP2-laches-writ", "rights", ["en"], "latin",
  "Can a writ petition be dismissed for delay when no limitation period applies to it?", "Laches in writ petitions",
  "ict", "answer",
  ["Laches is not applied with a limitation period's rigidity, but constitutional jurisdiction is discretionary and "
   "equitable, so unexplained and unreasonable delay weighs against relief."],
  necessary=[(133424, "30", 3)], relevant=[(135851, "38", 2)],
  check=[r"doctrine of laches does not operate with the same rigidity", r"discretionary and equitable"])
c("P2-I17", "issue", "FP2-aggrieved-person", "rights", ["en"], "latin",
  "Who can file a writ petition under Article 199(1)(a) of the Constitution?", "The aggrieved person under Art. 199",
  "ict", "answer",
  ["Only an aggrieved person: one whose own legal right or interest is affected by the action complained of."],
  necessary=[(134146, "16", 3)], relevant=[(12979, "5", 2)],
  check=[r"aggrieved person", r"own legal right or interest"])
c("P2-I18", "issue", "FP2-pension-right", "service", ["en"], "latin",
  "Is a pension a concession the government may withhold at will?", "Pension as an earned right", "sindh", "answer",
  ["Pension is not a bounty but compensation for service rendered, earned by qualifying service."],
  necessary=[(102094, "20", 3)], relevant=[(103169, "18", 2), (107457, "11", 2)],
  check=[r"pension is not a bounty", r"compensation"])
c("P2-I19", "issue", "FP2-regular-inquiry", "service", ["en"], "latin",
  "Can a major penalty be imposed on an employee without a regular inquiry when he denies the allegations?",
  "Dispensing with a regular inquiry", "punjab", "answer",
  ["Where the facts are disputed there is no reasonable ground to dispense with the inquiry; guilt not established "
   "by a regular inquiry supports no penalty."],
  necessary=[(5086, "15", 3), (5086, "16", 3)],
  check=[r"no reasonable ground to dispense with the inquiry", r"never established by a regular inquiry"])
c("P2-I20", "issue", "FP2-locus-poenitentiae", "service", ["en"], "latin",
  "Can an authority withdraw an order it issued by mistake, or has a vested right arisen?",
  "Locus poenitentiae and vested rights", "punjab", "answer",
  ["The power of receding is available until a decisive step is taken; an erroneous step creates no vested right."],
  necessary=[(114463, "11", 3)], relevant=[(17784, "3", 2)],
  check=[r"locus poenitentiae", r"decisive step"])
c("P2-I21", "issue", "FP2-legitimate-expectation", "rights", ["en"], "latin",
  "Can legitimate expectation be invoked to make an authority act against a statute?",
  "Legitimate expectation against a statute", "sindh", "answer",
  ["No: a legitimate expectation must arise from a lawful representation or practice and cannot defeat a mandatory "
   "statutory restriction."],
  necessary=[(27031, "42", 3)], relevant=[(87496, "7", 2)],
  check=[r"legitimate expectation", r"mandatory statutory restriction"])
c("P2-I22", "issue", "FP2-fair-trial-cross", "liberty", ["en"], "latin",
  "Can a trial court close an accused's right to cross-examine a prosecution witness?",
  "Cross-examination and Art. 10-A", "punjab", "answer",
  ["The right to cross-examine may be foregone by the accused but he cannot be deprived of it; depriving him "
   "violates the fair-trial guarantee of Article 10-A."],
  necessary=[(112220, "11", 3)], check=[r"cannot deprive him of that opportunity", r"10-A"])

# ---------------------------------------------------------------- issue: family, finance, special laws
c("P2-I23", "issue", "FP2-maintenance-wife", "family", ["en"], "latin",
  "Is a husband bound to maintain his wife during the marriage, or can he make it depend on her obedience?",
  "The husband's obligation of maintenance", "kp", "answer",
  ["Maintenance during the marriage is the husband's legal obligation; it is not a discretionary reward."],
  necessary=[(111258, "24", 3), (12752, "16", 3)], relevant=[(102848, "12", 2)],
  check=[r"obligation of the husband"])
c("P2-I24", "issue", "FP2-hizanat-remarriage", "family", ["en"], "latin",
  "Does a mother lose custody of her child because she has remarried?", "Remarriage and hizanat", "sindh", "answer",
  ["Not by itself: the welfare of the minor is the touchstone, and departure from the rule of hizanat needs "
   "exceptional circumstances proved on evidence."],
  necessary=[(96220, "24", 3)], relevant=[(15300, "14", 2)],
  check=[r"second marriage does not, by itself and automatically", r"welfare of the minor"])
c("P2-I25", "issue", "FP2-talaq-union-council", "family", ["en"], "latin",
  "Which Union Council must receive the notice of talaq under section 7 of the Muslim Family Laws Ordinance?",
  "Jurisdiction for a notice of talaq", "sindh", "answer",
  ["Rule 3(b) of the West Pakistan Rules: the Union Council where the wife was residing when talaq was pronounced."],
  necessary=[(6069, "16", 3)], check=[r"Rule 3\(b\)", r"wife was residing"])
c("P2-I26", "issue", "FP2-fio-leave-to-defend", "finance", ["en"], "latin",
  "What must a defendant's application for leave to defend contain in a banking suit under the Financial "
  "Institutions (Recovery of Finances) Ordinance 2001?", "Leave to defend under s.10 FIO 2001", "kp", "answer",
  ["Filed within thirty days of first service, in the form of a written statement, with a concise summary of the "
   "substantial questions of law and fact, and the documents relied on."],
  necessary=[(17783, "8", 3)], relevant=[(48983, "7", 2)],
  check=[r"thirty \(30\) days", r"substantial\s*questions of law and fact"])
c("P2-I27", "issue", "FP2-ata-terrorism", "liberty", ["en"], "latin",
  "Does a murder in a public place make the case triable as terrorism under the Anti-Terrorism Act?",
  "Place of occurrence and s.6 ATA", "punjab", "answer",
  ["No: the place of occurrence is not by itself enough; the decisive factor is the object, design and impact of "
   "the act under section 6 ATA."],
  necessary=[(5899, "10", 3)], relevant=[(96159, "6", 2)],
  check=[r"mere place of the occurrence", r"object, design and impact"])
c("P2-I28", "issue", "FP2-medical-bail", "liberty", ["en"], "latin",
  "When can an accused in custody get bail on medical grounds?", "Bail on medical grounds", "sindh", "answer",
  ["Not as a matter of course: there must be strong and exceptional reasons, on explicit medical opinion, that "
   "adequate treatment is unavailable and detention would endanger life."],
  necessary=[(44641, "8", 3)],
  check=[r"bail on medical grounds is not to\s+be granted as a matter of course", r"hazardous to his life"])
c("P2-I29", "issue", "FP2-fsc-qazf", "liberty", ["en"], "latin",
  "What has the Federal Shariat Court held amounts to qazf (a false imputation of zina)?",
  "Qazf without four witnesses", None, "answer",
  ["Any word directly or indirectly imputing zina to an adult Muslim, without the support of four witnesses, is "
   "enough to constitute qazf."],
  necessary=[(136337, "16", 3)], check=[r"four witnesses", r"Qazf"])
c("P2-I30", "issue", "FP2-gb-complete-justice", "rights", ["en"], "latin",
  "Can the Gilgit-Baltistan Chief Court grant relief not sought, in the name of complete justice?",
  "Complete justice under the GB Order 2018", None, "answer",
  ["The power to do complete justice belongs to the Supreme Court of Pakistan (Art. 187) and the GB Supreme "
   "Appellate Court (Art. 77 of the GB Order 2018), not the Chief Court."],
  necessary=[(109990, "23", 3)], check=[r"complete justice", r"Article 77"])
c("P2-I31", "issue", "FP2-fcc-leave-merger", "rights", ["en"], "latin",
  "When the Federal Constitutional Court refuses leave to appeal, does the High Court's judgment merge into the "
  "refusal?", "Merger and leave to appeal (Art. 175F(1)(c))", None, "answer",
  ["No: on refusal of leave the High Court's order stays the final order; only where leave is granted and the "
   "appeal decided does the High Court's judgment merge into the Court's decision."],
  necessary=[(94525, "6", 3)], relevant=[(94525, "5", 2)],
  check=[r"does not merge", r"leave is allowed"])
c("P2-I32", "issue", "FP2-ajk-preemption-waiver", "property", ["en"], "latin",
  "In Azad Jammu and Kashmir, what evidence defeats a pre-emptor's right on the ground that he waived it?",
  "Waiver of the right of prior purchase (AJK)", None, "answer",
  ["Very strong evidence is required to deprive a pre-emptor of his right on the ground of waiver."],
  necessary=[(109216, "5", 3)], check=[r"very strong evidence is required", r"waiver"])
c("P2-I33", "issue", "FP2-gb-ransom-delay", "liberty", ["en"], "latin",
  "In a kidnapping for ransom case, is a delay of a few days in lodging the FIR fatal to the prosecution?",
  "FIR delay in abduction for ransom (GB Chief Court)", None, "answer",
  ["No: families of an abductee, held in terror and hoping for recovery, are reluctant to go to the police, so "
   "delay is a natural phenomenon in such cases."],
  necessary=[(110792, "2", 3)], check=[r"kidnapping for ransom", r"delay is a natural"])
c("P2-I34", "issue", "FP2-gb-executing-court", "civil-procedure", ["en"], "latin",
  "Can an executing court go beyond the terms of the decree it is executing?", "The executing court and the decree",
  None, "answer", ["No: an executing court cannot go beyond the decree and must execute it as it stands."],
  # undated (D-124): it exists from its landing on 25 Nov 2026, so it is asked after that
  necessary=[(121854, "8", 3)], check=[r"cannot go beyond the decree"], as_of="2026-11-27")
c("P2-I35", "issue", "FP2-art-184-3", "rights", ["en"], "latin",
  "When can a petition be filed directly in the Supreme Court under Article 184(3)?",
  "The two conditions of Art. 184(3)", "punjab", "answer",
  ["Only where it raises a question of public importance with reference to the enforcement of a Fundamental "
   "Right in Chapter 1 of Part II."],
  necessary=[(4816, "15", 3)], check=[r"question of public importance", r"enforcement of any of the Fundamental"])
c("P2-I36", "issue", "FP2-land-acq-potential", "property", ["en"], "latin",
  "In land acquisition, is compensation limited to the land's current price?",
  "Potential value under s.23 Land Acquisition Act", "kp", "answer",
  ["No: under section 23 courts must look beyond the current price to the potential value, weighing features "
   "such as roads, amenities and surrounding commercial use."],
  necessary=[(6943, "11", 3)], relevant=[(111179, "9", 2)],
  check=[r"potential value", r"more than just the current price"])
c("P2-I37", "issue", "FP2-limitation-duty", "civil-procedure", ["en"], "latin",
  "Must a court dismiss a time-barred suit even if the defendant never raised limitation?",
  "The court's duty under s.3 Limitation Act", "sindh", "answer",
  ["Yes: section 3 casts a mandatory duty to dismiss a suit filed after the period, even if limitation was not "
   "set up as a defence."],
  necessary=[(7377, "12", 3)], relevant=[(35782, "20", 2)],
  check=[r"mandatory duty", r"not been set\s+up as a defence"])

# ---------------------------------------------------------------- case lookup: a case by its number, as typed (15)
for cid, fam, text, doc, rx, forum in [
        ("P2-C01", "FP2-regular-inquiry", "SC Civil Petition No. 1729-L of 2017", 5086, r"regular inquiry", "punjab"),
        ("P2-C02", "FP2-talaq-union-council", "CP 5364/2024 Supreme Court", 6069, r"Rule 3\(b\)", "sindh"),
        ("P2-C03", "FP2-circumstantial-chain", "Sindh High Court Criminal Jail Appeal No. D-01 of 2024", 87018,
         r"unbroken chain", "sindh"),
        ("P2-C04", "FP2-bail-cancellation", "Crl. Misc. Appl. No. S-424 of 2025 (SHC)", 102038,
         r"cancellation of bail", "sindh"),
        ("P2-C05", "FP2-laches-writ", "IHC W.P. No. 2155/2026", 133424, r"laches", "ict"),
        ("P2-C06", "FP2-aggrieved-person", "Islamabad High Court Writ Petition No. 2913 of 2025", 134146,
         r"aggrieved person", "ict"),
        ("P2-C07", "FP2-adverse-possession", "PHC C.R No. 395-A/2010", 16538, r"adverse possession", "kp"),
        ("P2-C08", "FP2-fio-leave-to-defend", "Peshawar High Court F.A.B No. 02-D/2023", 17783, r"leave to defend",
         "kp"),
        ("P2-C09", "FP2-fair-trial-cross", "LHC Criminal Revision No. 323 of 2025", 112220, r"cross-examin",
         "punjab"),
        ("P2-C10", "FP2-extra-judicial-confession", "Lahore High Court Crl. Appeal 138/2024", 114209,
         r"extra-judicial confession", "punjab"),
        ("P2-C11", "FP2-fsc-qazf", "Federal Shariat Court Criminal Appeal No. 04-P of 2019", 136337, r"Qazf", None),
        ("P2-C12", "FP2-gb-complete-justice", "GB Supreme Appellate Court CPLA No. 24/2020", 109990,
         r"complete justice", None),
        ("P2-C13", "FP2-ajk-preemption-waiver", "AJK Supreme Court Civil Appeal No. 356 of 2018", 109216,
         r"pre-emption", None),
        ("P2-C14", "FP2-fcc-leave-merger", "FCC review petition 128/2026 in CPLA 1267/2026", 94525, r"leave to appeal",
         None),
        ("P2-C15", "FP2-benami", "Civil Appeal 41-K/2021 SC", 6670, r"benami", "punjab")]:
    c(cid, "case_lookup", fam, "lookup", ["en"], "latin", text, "A case by its number, as typed", forum, "answer",
      ["The judgment in that case."], necessary=[(doc, None, 3)], check=[rx], task="case_lookup")

# ---------------------------------------------------------------- provision: the judgments on a named provision (11)
c("P2-S01", "provision", "FP2-acquittal-265k", "liberty", ["en"], "latin",
  "Judgments on section 265-K of the Code of Criminal Procedure", "Case law on s.265-K CrPC", "sindh", "answer",
  ["Judgments on acquittal at any stage where there is no probability of conviction."],
  necessary=[(39546, "10", 3), (85878, "8", 3)], check=[r"265-K"])
c("P2-S02", "provision", "FP2-fair-trial-cross", "liberty", ["en"], "latin",
  "Case law on Article 10-A of the Constitution (fair trial and due process)", "Case law on Art. 10-A", "punjab",
  "answer", ["Judgments applying the fair-trial guarantee; the Sindh judgment persuades a Punjab court."],
  necessary=[(112220, "11", 3), (95301, "10", 3)], check=[r"10-A"])
c("P2-S03", "provision", "FP2-fio-leave-to-defend", "finance", ["en"], "latin",
  "Judgments on section 10 of the Financial Institutions (Recovery of Finances) Ordinance 2001",
  "Case law on s.10 FIO 2001 (leave to defend)", "kp", "answer",
  ["Judgments on the requirements of an application for leave to defend."],
  necessary=[(17783, "8", 3), (48983, "7", 3)], check=[r"leave to defend"])
c("P2-S04", "provision", "FP2-ata-terrorism", "liberty", ["en"], "latin",
  "Case law on section 6 of the Anti-Terrorism Act 1997", "Case law on s.6 ATA", "punjab", "answer",
  ["Judgments on what makes an act terrorism under section 6."],
  necessary=[(5899, "10", 3), (96159, "6", 3)], check=[r"Section 6"])
c("P2-S05", "provision", "FP2-ex-parte-decree", "civil-procedure", ["en"], "latin",
  "Judgments on Order IX Rule 13 of the Code of Civil Procedure", "Case law on O.IX R.13 CPC", "sindh", "answer",
  ["Judgments on setting aside an ex parte decree."], necessary=[(93505, "22", 3)], check=[r"Order IX Rule 13"])
c("P2-S06", "provision", "FP2-talaq-union-council", "family", ["en"], "latin",
  "Case law on section 7 of the Muslim Family Laws Ordinance 1961", "Case law on s.7 MFLO", "sindh", "answer",
  ["Judgments on the notice of talaq to the Union Council."], necessary=[(6069, "16", 3)], check=[r"section 7"])
c("P2-S07", "provision", "FP2-aggrieved-person", "rights", ["en"], "latin",
  "Judgments on Article 199(1)(a) of the Constitution: who is an aggrieved person",
  "Case law on Art. 199(1)(a)", "ict", "answer", ["Judgments on standing to seek a writ."],
  necessary=[(134146, "16", 3)], check=[r"199\(1\)\(a\)"])
c("P2-S08", "provision", "FP2-limitation-duty", "civil-procedure", ["en"], "latin",
  "Case law on section 3 of the Limitation Act 1908", "Case law on s.3 Limitation Act", "kp", "answer",
  ["Judgments on the court's own duty to apply limitation; the Peshawar judgment binds a KP court."],
  necessary=[(7377, "12", 3), (17495, "8", 3)], relevant=[(35782, "20", 2)],
  check=[r"section 3 of\s+the Limitation Act"])
c("P2-S09", "provision", "FP2-land-acq-potential", "property", ["en"], "latin",
  "Judgments on section 23 of the Land Acquisition Act 1894", "Case law on s.23 Land Acquisition Act", "kp",
  "answer", ["Judgments on what compensation must take into account."],
  necessary=[(6943, "11", 3), (111179, "9", 3)], check=[r"section 23 of the Land Acquisition Act"])
c("P2-S10", "provision", "FP2-extra-judicial-confession", "liberty", ["en"], "latin",
  "Case law on Article 40 of the Qanun-e-Shahadat Order 1984 (extra-judicial confession)",
  "Case law on Art. 40 QSO", "sindh", "answer", ["Judgments on when an extra-judicial confession can be used."],
  necessary=[(90263, "17", 3)], check=[r"Article 40"])
c("P2-S11", "provision", "FP2-art-184-3", "rights", ["en"], "latin",
  "Judgments on Article 184(3) of the Constitution", "Case law on Art. 184(3)", "punjab", "answer",
  ["Judgments on the Supreme Court's original jurisdiction."], necessary=[(4816, "15", 3)], check=[r"184\(3\)"])

# ---------------------------------------------------------------- Urdu / Roman Urdu, each in its family (10)
c("P2-U01", "urdu", "FP2-fir-delay", "liberty", ["ur-Latn"], "roman_urdu",
  "Agar FIR der se darj ho aur der ki koi wajah na batai jaye to muqadme par kya asar parta hai?",
  "Unexplained FIR delay (Roman Urdu variant of P2-I02)", "sindh", "answer",
  ["An unexplained delay undermines the prosecution case."], necessary=[(95968, "17", 3)],
  check=[r"unexplained delay"])
c("P2-U02", "urdu", "FP2-dying-declaration", "liberty", ["ur"], "arabic",
  "کیا صرف مرنے والے کے نزعی بیان کی بنیاد پر ملزم کو سزا دی جا سکتی ہے؟",
  "Conviction on a dying declaration (Urdu variant of P2-I01)", "kp", "answer",
  ["Yes, if made voluntarily, truthfully and in a fit state of mind."], necessary=[(15198, "6", 3)],
  check=[r"dying declaration"])
c("P2-U03", "urdu", "FP2-maintenance-wife", "family", ["ur"], "arabic",
  "کیا شوہر پر بیوی کا نان نفقہ ادا کرنا لازم ہے؟", "The husband's duty of maintenance (Urdu variant of P2-I23)",
  "kp", "answer", ["Yes: it is his legal obligation during the marriage."],
  necessary=[(111258, "24", 3), (12752, "16", 3)], check=[r"obligation of the husband"])
c("P2-U04", "urdu", "FP2-hizanat-remarriage", "family", ["ur-Latn"], "roman_urdu",
  "Kya maa doosri shadi kar le to bache ki hizanat us se le li jati hai?",
  "Remarriage and hizanat (Roman Urdu variant of P2-I24)", "sindh", "answer",
  ["Not by itself; the welfare of the minor decides."], necessary=[(96220, "24", 3)],
  check=[r"welfare of the minor"])
c("P2-U05", "urdu", "FP2-pension-right", "service", ["ur"], "arabic",
  "کیا پنشن حکومت کی مہربانی ہے یا ملازم کا حق ہے؟", "Pension as a right (Urdu variant of P2-I18)", "sindh",
  "answer", ["Pension is not a bounty; it is earned by service."], necessary=[(102094, "20", 3)],
  check=[r"not a bounty"])
c("P2-U06", "urdu", "FP2-bail-cancellation", "liberty", ["ur-Latn"], "roman_urdu",
  "Zamanat mil jane ke baad kin wajohat par zamanat mansookh ho sakti hai?",
  "Cancelling bail (Roman Urdu variant of P2-I07)", "sindh", "answer",
  ["Only on stronger and exceptional grounds."], necessary=[(102038, "6", 3)],
  check=[r"stronger and exceptional grounds"])
c("P2-U07", "urdu", "FP2-talaq-union-council", "family", ["ur"], "arabic",
  "طلاق کا نوٹس کس یونین کونسل کو بھیجا جانا چاہیے؟", "Notice of talaq (Urdu variant of P2-I25)", "sindh",
  "answer", ["The Union Council where the wife was residing when talaq was pronounced."],
  necessary=[(6069, "16", 3)], check=[r"wife was residing"])
c("P2-U08", "urdu", "FP2-adverse-possession", "property", ["ur-Latn"], "roman_urdu",
  "Qabza mukhalifana (adverse possession) se zameen ki milkiyat kab milti hai?",
  "Adverse possession (Roman Urdu variant of P2-I10)", "kp", "answer",
  ["Only on open, continuous, exclusive and hostile possession, specifically pleaded."],
  necessary=[(16538, "6", 3), (16538, "7", 3)], check=[r"adverse possession"])
c("P2-U09", "urdu", "FP2-related-witness", "liberty", ["ur-Latn"], "roman_urdu",
  "Kya rishtedar gawahon ki gawahi sirf rishtedari ki wajah se radd ki ja sakti hai?",
  "Related witnesses (Roman Urdu variant of P2-I05)", "kp", "answer",
  ["No: mere relationship does not make a witness unworthy of belief."], necessary=[(111188, "8", 3)],
  check=[r"mere relationship"])
c("P2-U10", "urdu", "FP2-medical-bail", "liberty", ["ur"], "arabic",
  "کیا کسی ملزم کو بیماری کی بنیاد پر ضمانت مل سکتی ہے؟", "Bail on medical grounds (Urdu variant of P2-I28)",
  "sindh", "answer", ["Only for strong and exceptional reasons on explicit medical opinion."],
  necessary=[(44641, "8", 3)], check=[r"medical grounds"])

# ---------------------------------------------------------------- temporal: a later judgment did not exist (6)
c("P2-T01", "temporal", "FP2-maintenance-wife", "family", ["en"], "latin",
  "Is a husband bound to maintain his wife during the marriage?", "Maintenance, asked on 1 January 2026", "kp",
  "answer", ["As in September 2025; the September 2026 judgment did not yet exist."],
  necessary=[(12752, "16", 3)], must_not_serve=[111258], as_of="2026-01-01", check=[r"obligation of the husband"])
c("P2-T02", "temporal", "FP2-pension-right", "service", ["en"], "latin",
  "Is a pension a concession the government may withhold at will?", "Pension, asked on 1 September 2026", "sindh",
  "answer", ["As in August 2026; the October and November 2026 judgments did not yet exist."],
  necessary=[(103169, "18", 3)], must_not_serve=[102094, 107457], as_of="2026-09-01", check=[r"not a bounty"])
c("P2-T03", "temporal", "FP2-ata-terrorism", "liberty", ["en"], "latin",
  "What makes an offence terrorism under section 6 of the Anti-Terrorism Act?", "Section 6 ATA, asked on 1 "
  "December 2025", "sindh", "answer",
  ["As the Sindh High Court read Ghulam Hussain in October 2025; the February 2026 Supreme Court judgment did not "
   "yet exist."], necessary=[(96159, "6", 3)], must_not_serve=[5899], as_of="2025-12-01",
  check=[r"Ghulam Hussain"])
c("P2-T04", "temporal", "FP2-extra-judicial-confession", "liberty", ["en"], "latin",
  "Can a conviction be based on an extra-judicial confession?", "Extra-judicial confession, asked on 1 July 2025",
  "sindh", "answer", ["As in June 2025; the 2026 judgments did not yet exist."],
  necessary=[(90263, "17", 3)], must_not_serve=[114209, 30223], as_of="2025-07-01",
  check=[r"weak type of evidence"])
c("P2-T05", "temporal", "FP2-laches-writ", "rights", ["en"], "latin",
  "Can a writ petition be dismissed for delay?", "Laches, asked on 20 September 2026", "ict", "answer",
  ["As on 17 September 2026; the October 2026 judgment did not yet exist."],
  necessary=[(133424, "30", 3)], must_not_serve=[135851], as_of="2026-09-20", check=[r"laches"])
c("P2-T06", "temporal", "FP2-dying-declaration", "liberty", ["en"], "latin",
  "Can an accused be convicted on a dying declaration alone?", "Dying declaration, asked on 1 February 2026", "kp",
  "answer", ["As in January 2026; the May 2026 judgment did not yet exist."],
  necessary=[(15198, "6", 3)], must_not_serve=[15018], as_of="2026-02-01",
  check=[r"solely on a dying declaration"])

# ---------------------------------------------------------------- authority: the same question elsewhere (6)
c("P2-F01", "authority", "FP2-fir-delay", "liberty", ["en"], "latin",
  "For a trial court in Punjab: what is the effect of an unexplained delay in lodging the FIR?",
  "FIR delay, asked from Punjab", "punjab", "answer",
  ["The Lahore High Court's judgment binds; the Sindh High Court's persuades (Art. 201)."],
  necessary=[(115872, "8", 3), (95968, "17", 3)], check=[r"consultation and deliberation"])
c("P2-F02", "authority", "FP2-related-witness", "liberty", ["en"], "latin",
  "For a sessions court in Sindh: can a related eyewitness's evidence be rejected for the relationship alone?",
  "Related witnesses, asked from Sindh", "sindh", "answer",
  ["The Sindh High Court's judgment binds; the Peshawar High Court's persuades."],
  necessary=[(23114, "16", 3), (111188, "8", 3)], check=[r"mere relationship"])
c("P2-F03", "authority", "FP2-pension-right", "service", ["en"], "latin",
  "For a service matter in Khyber Pakhtunkhwa: is pension a bounty the employer may withhold?",
  "Pension, asked from KP", "kp", "answer",
  ["The Sindh High Court's holding is persuasive, not binding, on a KP forum."],
  necessary=[(102094, "20", 3)], check=[r"not a bounty"])
c("P2-F04", "authority", "FP2-laches-writ", "rights", ["en"], "latin",
  "For a writ before the Lahore High Court's subordinate forums: does delay alone defeat constitutional relief?",
  "Laches, asked from Punjab", "punjab", "answer",
  ["The Islamabad High Court's reasoning persuades; it does not bind a Punjab court."],
  necessary=[(133424, "30", 3)], check=[r"laches"])
c("P2-F05", "authority", "FP2-limitation-duty", "civil-procedure", ["en"], "latin",
  "For a civil court in Sindh: must a time-barred suit be dismissed though limitation was not pleaded?",
  "Section 3 Limitation Act, asked from Sindh", "sindh", "answer",
  ["The Supreme Court (Art. 189) and the Sindh High Court (Art. 201) both bind."],
  necessary=[(7377, "12", 3), (35782, "20", 3)], check=[r"inherent duty"])
c("P2-F06", "authority", "FP2-extra-judicial-confession", "liberty", ["en"], "latin",
  "For a trial court in Sindh: can an extra-judicial confession alone found a conviction?",
  "Extra-judicial confession, asked from Sindh", "sindh", "answer",
  ["The Sindh High Court's judgments bind; the Lahore High Court's persuades."],
  necessary=[(30223, "26", 3), (90263, "17", 3), (114209, "10", 3)], check=[r"weak type of evidence"])

# ---------------------------------------------------------------- unanswerable: a forum the corpus does not hold (2)
c("P2-X01", "unanswerable", "FP2-x-service-tribunal", "coverage", ["en"], "latin",
  "What has the Federal Service Tribunal held about the seniority of officers on deputation?",
  "A tribunal whose decisions are not held", None, "abstain", [],
  abstention=dict(code="court_not_held", court="FST", requiredClarification=[],
                  unsafeAlternatives=["citing a High Court or Supreme Court judgment as if it were the Tribunal's"],
                  why="the corpus holds no Federal Service Tribunal decisions; tribunals are not recorded courts "
                      "(D-157, docs/SOURCES-NOT-HELD-2026-11-26.md)"))
c("P2-X02", "unanswerable", "FP2-x-customs-tribunal", "coverage", ["en"], "latin",
  "What has the Customs Appellate Tribunal decided on the valuation of imported used vehicles?",
  "A tribunal whose decisions are not held", None, "abstain", [],
  abstention=dict(code="court_not_held", court="CAT", requiredClarification=[],
                  unsafeAlternatives=["citing a High Court customs reference as if it were the Tribunal's"],
                  why="the corpus holds no Customs Appellate Tribunal decisions; tribunals are not recorded courts "
                      "(D-157)"))

if __name__ == "__main__":
    sys.exit(build(ps, "Precedent stratum, set 2 (D-168): every court held. Gold is judgment paragraphs read in the "
                       "released text; it names some of the judgments that answer, not all."))
