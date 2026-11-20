"""Build golden-pk-v1 draft SET 7 (50 cases): family and personal status II.

The grounds of the Dissolution of Muslim Marriages Act (absence, an additional wife, the option of puberty, cruelty,
imprisonment, insanity, unperformed obligations, lian) and the dower it saves; dower payable on demand and the
delegated right of divorce (MFLO); guardianship (return of a ward, the living father, interim custody, removal from
jurisdiction, cessation of powers) and the age of majority; the offences against women -- depriving a woman of her
inheritance, forced marriage, "marriage with the Quran", swara and wanni; legitimacy; the Family Courts' procedure
(plaint, notice, written statement, the criminal jurisdiction, conclusion of trial, enforcement, appeal); Sikh Anand
Karaj marriage and its dissolution in Punjab; Christian marriage; and registration of births and identity cards.

Sections already used by sets 1-4 (MFLO 4-7, 9; Family Courts Act 5's civil list, 10, 17A; Guardians and Wards 17,
29) are not the subject of a new family. MFLO, the PPC, the Qanun-e-Shahadat and the Family Courts Act have Punjab
copies (and Balochistan for the Family Courts Act), so those cases are asked in Sindh, KP or Islamabad. Stage A0 + A3
by the lead (claude), 20 Nov 2026; propositions written from the held text (peek.py) and re-verified by each case's
`check` regexes at every build. Not gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set7.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set7")
c = S.case
DMMA, MFLO, GWA, FCA, MAJ, PPC, QSO, SIKH, CMA, NADRA = 3100, 3283, 4283, 2944, 2355, 4441, 4166, 6122, 3829, 3967

# ---------------------------------------------------------------- citizen scenarios (20)
c("S7-C01", "citizen", "F7-dmma-missing-husband", "family", ["en"], "latin",
  "My husband left five years ago and nobody knows where he is. Can I get my marriage dissolved in Karachi?",
  "Dissolution where the husband's whereabouts are unknown for four years", "fed", "sindh", "answer",
  ["A woman married under Muslim law may obtain a decree of dissolution if her husband's whereabouts have not been "
   "known for four years."],
  necessary=[(DMMA, "2", 3)], check=[r"whereabouts of the husband have not been known for a period of four years"])
c("S7-C02", "citizen", "F7-dmma-second-wife", "family", ["en"], "latin",
  "My husband in Islamabad married another woman without the Arbitration Council's permission. Is that a ground "
  "for me to end the marriage?", "Dissolution for an additional wife taken in contravention of the MFLO", "fed",
  "ict", "answer",
  ["Yes: that the husband has taken an additional wife in contravention of the Muslim Family Laws Ordinance is a "
   "ground for a decree of dissolution."],
  necessary=[(DMMA, "2", 3)], check=[r"additional wife in contravention"])
c("S7-C03", "citizen", "F7-option-of-puberty", "family", ["en"], "latin",
  "My father married me off at fifteen and I never lived with my husband. Now I am seventeen. Can I undo the "
  "marriage?", "The option of puberty", "fed", "kp", "conditional",
  ["A woman given in marriage by her father or guardian before sixteen who repudiates it before eighteen, the "
   "marriage not having been consummated, may obtain a decree of dissolution."],
  necessary=[(DMMA, "2", 3)], omitted=["whether the marriage was consummated"],
  check=[r"repudiated the marriage before attaining the age of eighteen", r"not been consummated"])
c("S7-C04", "citizen", "F7-dmma-dower-saved", "family", ["en"], "latin",
  "If the court dissolves my marriage in Hyderabad, do I lose my dower?", "Dissolution does not affect dower",
  "fed", "sindh", "answer",
  ["Nothing in the Act affects a married woman's right under Muslim law to her dower on dissolution."],
  necessary=[(DMMA, "5", 3)], check=[r"right which a married woman may have under Muslim law to her dower"])
c("S7-C05", "citizen", "F7-dower-on-demand", "family", ["en"], "latin",
  "My nikah nama in Islamabad does not say when the dower is to be paid. When can I ask for it?",
  "Dower is payable on demand where the mode is not specified", "fed", "ict", "answer",
  ["Where the nikah nama or contract gives no details of the mode of payment, the entire dower is payable on "
   "demand."],
  necessary=[(MFLO, "10", 3)], check=[r"payable on demand"])
c("S7-C06", "citizen", "F7-family-court-offence", "family", ["en"], "latin",
  "My husband in Peshawar assaulted me. Can the Family Court hearing our case also try him for it?",
  "The Family Court's criminal jurisdiction where one spouse is the victim", "fed", "kp", "conditional",
  ["The Family Court may try the offences in Part II of the Schedule where one spouse is the victim of an offence by "
   "the other."],
  necessary=[(FCA, "5", 3)], omitted=["whether the offence is listed in Part II of the Schedule"],
  check=[r"one of the spouses is victim of an offence"])
c("S7-C07", "citizen", "F7-return-of-ward", "family", ["en"], "latin",
  "The court made me guardian of my son, but his father took him from my house in Karachi. Can the court get him "
  "back?", "Order for the return of a ward to the guardian", "fed", "sindh", "answer",
  ["If a ward leaves or is removed from the custody of the guardian of his person, the court may, for the ward's "
   "welfare, order his return and enforce it by causing him to be arrested and delivered to the guardian."],
  necessary=[(GWA, "25", 3)], check=[r"make an order for his return"])
c("S7-C08", "citizen", "F7-living-father-guardian", "family", ["en"], "latin",
  "Can a court in Islamabad appoint me, the mother, as guardian of my children while their father is alive?",
  "No court guardian of the person while the father is living and fit", "fed", "ict", "conditional",
  ["The court may not appoint a guardian of the person of a minor whose father is living unless, in the court's "
   "opinion, he is unfit to be guardian of the minor's person."],
  necessary=[(GWA, "19", 3)], omitted=["whether the father is unfit"], check=[r"whose father is living"])
c("S7-C09", "citizen", "F7-age-of-majority", "family", ["en"], "latin",
  "At what age does my son in Karachi become an adult in law?", "The age of majority", "fed", "sindh", "answer",
  ["A person domiciled in Pakistan attains majority on completing eighteen years (twenty-one if a court appointed a "
   "guardian of his person or property before eighteen)."],
  necessary=[(MAJ, "3", 3)], check=[r"completed his age of eighteen years"])
c("S7-C10", "citizen", "F7-depriving-inheritance", "property", ["en"], "latin",
  "My brothers in Sukkur forged papers so that I got nothing from our father's estate. Is that a crime?",
  "Depriving a woman of her inheritance by deceitful or illegal means", "fed", "sindh", "answer",
  ["Depriving a woman by deceitful or illegal means of inheriting property is punishable with five to ten years' "
   "imprisonment or a fine of one million rupees or both."],
  necessary=[(PPC, "498A", 3)], check=[r"deprives any woman from inheriting", r"one million rupees"])
c("S7-C11", "citizen", "F7-forced-marriage", "family", ["en"], "latin",
  "My family in Mardan is forcing me to marry a man I don't want. Is that against the law?",
  "Forced marriage is an offence", "fed", "kp", "answer",
  ["Coercing or compelling a woman to marry is punishable with three to seven years' imprisonment and a fine of "
   "five hundred thousand rupees."],
  necessary=[(PPC, "498B", 3)], check=[r"compels a woman to enter into marriage"])
c("S7-C12", "citizen", "F7-marriage-with-quran", "property", ["en"], "latin",
  "My uncles in Larkana want my sister to swear on the Quran never to marry so that the land stays with them. Is "
  "that allowed?", "Marriage with the Holy Quran is an offence", "fed", "sindh", "answer",
  ["Compelling, arranging or facilitating a woman's 'marriage with the Holy Quran' -- including an oath to remain "
   "unmarried or not to claim her inheritance -- is punishable with three to seven years and a fine."],
  necessary=[(PPC, "498C", 3)], check=[r"marriage of a woman with the Holy Quran", r"not to claim her share"])
c("S7-C13", "citizen", "F7-swara", "family", ["en"], "latin",
  "To settle a murder case in Swat, the jirga wants to give my 14-year-old cousin in marriage to the other family. "
  "Is that legal?", "Giving a female in badla-e-sulh, wanni or swara", "fed", "kp", "answer",
  ["Giving or compelling a female into marriage as badla-e-sulh, wanni or swara to settle a civil dispute or "
   "criminal liability is punishable with three to seven years and a fine of five hundred thousand rupees."],
  necessary=[(PPC, "310A", 3)], check=[r"swara", r"settling a civil dispute or a criminal liability"])
c("S7-C14", "citizen", "F7-legitimacy", "family", ["en"], "latin",
  "Our baby was born eight months after our nikah in Karachi and my husband now says the child is not his. What "
  "does the law presume?", "Birth during marriage as proof of legitimacy", "fed", "sindh", "conditional",
  ["Birth during a valid marriage, not earlier than six lunar months after it (or within two years of its "
   "dissolution, the mother unmarried), is conclusive proof of legitimacy unless the husband refuses to own the "
   "child, among the stated exceptions."],
  necessary=[(QSO, "128", 3)], check=[r"six lunar months", r"conclusive proof"])
c("S7-C15", "citizen", "F7-anand-karaj-registration", "family", ["en"], "latin",
  "We are Sikhs and married in Nankana Sahib. How do we register our marriage?", "Registration of Anand Karaj",
  "punjab", "punjab", "answer",
  ["The bride and bridegroom or the Granthi present the Anand Karaj Form to the licensed Anand Karaj Registrar "
   "within thirty days; the Registrar registers the marriage and issues the Anand Karaj Certificate."],
  necessary=[(SIKH, "5", 3)], check=[r"within thirty days of the marriage", r"Anand Karaj Registrar"])
c("S7-C16", "citizen", "F7-family-appeal", "family", ["en"], "latin",
  "I lost my maintenance case in the Family Court in Abbottabad. Where do I appeal?",
  "Appeals from a Family Court", "fed", "kp", "conditional",
  ["An appeal lies to the High Court where the Family Court is presided over by a District or Additional District "
   "Judge, and to the District Court in any other case."],
  necessary=[(FCA, "14", 3)], omitted=["who presided over the Family Court"], check=[r"High Court", r"District Court"])
c("S7-C17", "citizen", "F7-christian-solemnizer", "family", ["en"], "latin",
  "We are Christians in Islamabad. Who can lawfully perform our marriage?",
  "Persons by whom Christian marriages may be solemnized", "fed", "ict", "answer",
  ["A person who has received episcopal ordination, a Church of Scotland clergyman, a licensed Minister of Religion, "
   "a Marriage Registrar, or a person licensed to certify marriages between Native Christians."],
  necessary=[(CMA, "5", 3)], check=[r"episcopal ordination", r"Marriage Registrar"])
c("S7-C18", "citizen", "F7-birth-registration-nadra", "routine", ["en"], "latin",
  "Our baby was born in Karachi. By when must we register her with NADRA?",
  "Registration of a child within one month of birth", "fed", "sindh", "answer",
  ["A parent or guardian must get a citizen under eighteen registered not later than one month after birth (the "
   "Authority may extend the period)."],
  necessary=[(NADRA, "9", 3)], check=[r"one month after the birth"])
c("S7-C19", "citizen", "F7-cnic-cancellation", "routine", ["en"], "latin",
  "NADRA has blocked my ID card in Quetta saying it was obtained wrongly. Can they do that, and what can I do?",
  "Cancellation of a card and the appeal", "fed", "balochistan", "conditional",
  ["A card may be cancelled or impounded only after a show-cause notice and on stated grounds (ineligibility, "
   "duplicate cards, tampering, forgery); the holder may appeal to the Federal Government within thirty days."],
  necessary=[(NADRA, "18", 3)], check=[r"show cause", r"within thirty days of the order"])
c("S7-C20", "citizen", "F7-dmma-cruelty", "family", ["en"], "latin",
  "My husband in Karachi beats me regularly. Is that a ground to have the marriage dissolved?",
  "Cruelty as a ground of dissolution", "fed", "sindh", "answer",
  ["That the husband treats her with cruelty, as by habitually assaulting her, is a ground for a decree of "
   "dissolution."],
  necessary=[(DMMA, "2", 3)], check=[r"treats her with cruelty", r"habitually assaults"])

# ---------------------------------------------------------------- professional lookups (12)
c("S7-P01", "professional", "F7-majority-guardian-21", "family", ["en"], "latin",
  "Age of majority of a minor for whom a court appointed a guardian", "Section 3 Majority Act, 1875", "fed", "ict",
  "answer",
  ["Such a minor attains majority on completing twenty-one years, not eighteen."],
  necessary=[(MAJ, "3", 3)], check=[r"completed his age of twenty-one years"])
c("S7-P02", "professional", "F7-dmma-insanity", "family", ["en"], "latin",
  "Insanity or disease of the husband as a ground of dissolution", "Section 2 Dissolution of Muslim Marriages "
  "Act, 1939", "fed", "ict", "answer",
  ["That the husband has been insane for two years or suffers from leprosy or a virulent venereal disease is a "
   "ground."],
  necessary=[(DMMA, "2", 3)], check=[r"insane for a period of two years"])
c("S7-P03", "professional", "F7-dmma-obligations", "family", ["en"], "latin",
  "Failure to perform marital obligations as a ground of dissolution", "Section 2 Dissolution of Muslim Marriages "
  "Act, 1939", "fed", "kp", "answer",
  ["That the husband has failed without reasonable cause to perform his marital obligations for three years is a "
   "ground."],
  necessary=[(DMMA, "2", 3)], check=[r"marital obligations for a period of three years"])
c("S7-P04", "professional", "F7-dmma-imprisonment", "family", ["en"], "latin",
  "The husband's imprisonment as a ground of dissolution", "Section 2 Dissolution of Muslim Marriages Act, 1939",
  "fed", "sindh", "answer",
  ["That the husband has been sentenced to imprisonment for seven years or more is a ground."],
  necessary=[(DMMA, "2", 3)], check=[r"seven years or upwards"])
c("S7-P05", "professional", "F7-guardian-appointment", "family", ["en"], "latin",
  "Court's power to appoint or declare a guardian", "Section 7 Guardians and Wards Act, 1890", "fed", "sindh",
  "answer",
  ["Where satisfied it is for the minor's welfare, the court may appoint or declare a guardian of his person or "
   "property or both; the order implies removal of a guardian not appointed by will, instrument or court."],
  necessary=[(GWA, "7", 3)], check=[r"welfare of a minor", r"appointing a guardian of his person or property"])
c("S7-P06", "professional", "F7-cnic-issue", "routine", ["en"], "latin",
  "Issue of the National Identity Card", "Section 10 NADRA Ordinance, 2000", "fed", "ict", "answer",
  ["NADRA issues or renews a National Identity Card to every registered citizen who has attained eighteen."],
  necessary=[(NADRA, "10", 3)], check=[r"attained the age of eighteen years", r"National Identity Card"])
c("S7-P07", "professional", "F7-ward-removal", "family", ["en"], "latin",
  "Removal of a ward from the court's jurisdiction", "Section 26 Guardians and Wards Act, 1890", "fed", "kp",
  "answer",
  ["A court-appointed guardian of the person may not remove the ward from the court's jurisdiction without its "
   "leave, save for prescribed purposes."],
  necessary=[(GWA, "26", 3)], check=[r"without the leave of the Court"])
c("S7-P08", "professional", "F7-guardian-cessation", "family", ["en"], "latin",
  "When does a guardian of the person cease to act?", "Section 41 Guardians and Wards Act, 1890", "fed", "sindh",
  "answer",
  ["On his death, removal or discharge, on the Court of Wards assuming superintendence, on the ward ceasing to be a "
   "minor, or on a female ward's marriage to a husband not unfit."],
  necessary=[(GWA, "41", 3)], check=[r"ceasing to be a minor"])
c("S7-P09", "professional", "F7-family-court-evidence", "family", ["en"], "latin",
  "Application of the Qanun-e-Shahadat and CPC to Family Court proceedings", "Section 17 Family Courts Act, 1964",
  "fed", "ict", "answer",
  ["Save as expressly provided, the Qanun-e-Shahadat and the CPC (except sections 10 and 11) do not apply to Family "
   "Court proceedings under Part I of the Schedule; sections 8 to 11 of the Oaths Act do."],
  necessary=[(FCA, "17", 3)], check=[r"shall not apply to proceedings before any Family Court"])
c("S7-P10", "professional", "F7-fca-mflo-saving", "family", ["en"], "latin",
  "Relation of the Family Courts Act to the Muslim Family Laws Ordinance", "Section 21 Family Courts Act, 1964",
  "fed", "kp", "answer",
  ["Nothing in the Family Courts Act affects the Muslim Family Laws Ordinance or its rules."],
  necessary=[(FCA, "21", 3)], check=[r"Nothing in this Act shall be deemed to affect"])
c("S7-P11", "professional", "F7-anand-karaj-conditions", "family", ["en"], "latin",
  "Conditions of a valid Anand Karaj", "Section 3 Punjab Sikh Anand Karaj Marriage Act, 2018", "punjab", "punjab",
  "answer",
  ["The parties must be of sound mind, not below eighteen, consenting freely and fully, and not within the degrees "
   "Sikh customary law prohibits."],
  necessary=[(SIKH, "3", 3)], check=[r"not below the age of eighteen years", r"free and full consent"])
c("S7-P12", "professional", "F7-dmma-lian", "family", ["en"], "latin",
  "Lian as a ground of dissolution", "Section 2 Dissolution of Muslim Marriages Act, 1939", "fed", "sindh",
  "answer",
  ["Lian -- the husband accusing the wife of zina and her not accepting it as true -- is a ground."],
  necessary=[(DMMA, "2", 3)], check=[r"Lian means"])

# ---------------------------------------------------------------- procedural (8)
c("S7-R01", "procedural", "F7-family-plaint", "family", ["en"], "latin",
  "How do I start a case in the Family Court in Karachi?", "Institution of a family suit", "fed", "sindh", "answer",
  ["By presenting a plaint with the material facts and a Schedule of witnesses and what each will say."],
  necessary=[(FCA, "7", 3)], check=[r"presentation of a plaint", r"number of witnesses"])
c("S7-R02", "procedural", "F7-family-notice", "family", ["en"], "latin",
  "After I file in the Family Court in Islamabad, how soon must my husband be called?",
  "Intimation to the defendant", "fed", "ict", "answer",
  ["The court fixes the defendant's appearance within thirty days, issues summons, and within three days sends the "
   "plaint and Schedule by registered post or courier."],
  necessary=[(FCA, "8", 3)], check=[r"not more than thirty days", r"within three days"])
c("S7-R03", "procedural", "F7-written-statement", "family", ["en"], "latin",
  "I filed for dissolution in Peshawar. Can my husband ask the same court to order me to return to him?",
  "Written statement; a claim for restitution of conjugal rights", "fed", "kp", "answer",
  ["The defendant files a written statement with witnesses and a precis; a husband may, if no earlier restitution "
   "suit is pending, claim restitution of conjugal rights in his written statement to a dissolution suit."],
  necessary=[(FCA, "9", 3)], check=[r"restitution of conjugal rights"])
c("S7-R04", "procedural", "F7-interim-custody", "family", ["en"], "latin",
  "While my guardianship case is pending in Hyderabad, can the court decide who keeps the child for now?",
  "Interim custody and production of the minor", "fed", "sindh", "answer",
  ["The court may direct production of the minor and make orders for the temporary custody and protection of the "
   "minor's person or property."],
  necessary=[(GWA, "12", 3)], check=[r"temporary custody"])
c("S7-R05", "procedural", "F7-anand-karaj-dissolution", "family", ["en"], "latin",
  "How is a Sikh marriage dissolved in Punjab?", "Dissolution of an Anand Karaj", "punjab", "punjab", "answer",
  ["A party gives written notice to the Chairman (copy to the other party); an Arbitration Council attempts "
   "reconciliation, and if none is reached within ninety days the Chairman declares the marriage dissolved."],
  necessary=[(SIKH, "6", 3)], check=[r"Arbitration Council", r"ninety days"])
c("S7-R06", "procedural", "F7-family-decree-enforcement", "family", ["en"], "latin",
  "The Family Court in Islamabad decreed maintenance but my ex-husband is not paying. How is it enforced?",
  "Enforcement of a Family Court money decree", "fed", "ict", "answer",
  ["The court records the decree and any payment; a money decree not paid within the time it sets (not exceeding "
   "thirty days) is enforced as the Act provides."],
  necessary=[(FCA, "13", 3)], check=[r"not exceeding thirty days"])
c("S7-R07", "procedural", "F7-delegated-divorce", "family", ["en"], "latin",
  "My nikah nama in Peshawar gives me the right to divorce. How do I use it?",
  "Exercising a delegated right of divorce", "fed", "kp", "answer",
  ["Where the right of divorce has been duly delegated to the wife, the notice and Arbitration Council procedure of "
   "section 7 applies, mutatis mutandis."],
  necessary=[(MFLO, "8", 3)], check=[r"right to divorce has been duly delegated"])
c("S7-R08", "procedural", "F7-family-conclusion", "family", ["en"], "latin",
  "What does the Family Court in Karachi do after both sides finish their evidence?", "Conclusion of trial",
  "fed", "sindh", "answer",
  ["It makes a further attempt at compromise or reconciliation within fifteen days; failing that, it announces "
   "judgment and passes a decree."],
  necessary=[(FCA, "12", 3)], check=[r"fifteen days", r"compromise or reconciliation"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5)
c("S7-U01", "urdu", "F7-dmma-missing-husband", "family", ["ur-Latn"], "roman_urdu",
  "Mera shohar paanch saal se laapata hai, kya mein Karachi mein nikah khatam karwa sakti hoon?",
  "A missing husband (Roman Urdu variant of S7-C01)", "fed", "sindh", "answer",
  ["Yes, after four years of unknown whereabouts."], necessary=[(DMMA, "2", 3)],
  check=[r"period of four years"])
c("S7-U02", "urdu", "F7-depriving-inheritance", "property", ["ur"], "arabic",
  "میرے بھائیوں نے دھوکے سے مجھے والد کی جائیداد کے حصے سے محروم کر دیا، کیا یہ جرم ہے؟",
  "Depriving a woman of inheritance (Urdu variant of S7-C10)", "fed", "sindh", "answer",
  ["Yes: five to ten years or a fine of one million rupees or both."], necessary=[(PPC, "498A", 3)],
  check=[r"deprives any woman from inheriting"])
c("S7-U03", "urdu", "F7-swara", "family", ["ur-Latn"], "roman_urdu",
  "Jirga ne qatl ka faisla karne ke liye meri cousin ko swara mein dene ka kaha hai, kya yeh qanooni hai?",
  "Swara (Roman Urdu variant of S7-C13)", "fed", "kp", "answer",
  ["No: an offence punishable with three to seven years and a fine."], necessary=[(PPC, "310A", 3)],
  check=[r"swara"])
c("S7-U04", "urdu", "F7-dower-on-demand", "family", ["ur-Latn"], "roman_urdu",
  "Mere nikah nama mein haq mehr ki adaigi ka waqt nahi likha, mein kab mang sakti hoon?",
  "Dower on demand (Roman Urdu variant of S7-C05)", "fed", "ict", "answer",
  ["The whole dower is payable on demand."], necessary=[(MFLO, "10", 3)], check=[r"payable on demand"])
c("S7-U05", "urdu", "F7-birth-registration-nadra", "routine", ["ur"], "arabic",
  "بچے کی پیدائش کے بعد نادرا میں اندراج کب تک کروانا ضروری ہے؟",
  "Registering a newborn (Urdu variant of S7-C18)", "fed", "sindh", "answer",
  ["Not later than one month after the birth."], necessary=[(NADRA, "9", 3)],
  check=[r"one month after the birth"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S7-X01", "unanswerable", "F7-x-fiqh-video-nikah", "family", ["en"], "latin",
  "Is a nikah done over a video call valid under Shafi'i fiqh?", "A religious ruling", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["issuing a fatwa", "answering from MFLO s.5 as if it settled validity"],
                  why="a school of fiqh's ruling is not statute"))
c("S7-X02", "unanswerable", "F7-x-custody-outcome", "family", ["en"], "latin",
  "Will the Family Court give me custody of my six-year-old son?", "A prediction of a custody decision", "fed",
  None, "abstain", [],
  abstention=dict(code="professional_review_required", requiredClarification=["the facts"],
                  unsafeAlternatives=["predicting the decision"],
                  why="predicting a court's decision on particular facts is legal advice"))
c("S7-X03", "unanswerable", "F7-x-uk-divorce", "family", ["en"], "latin",
  "What are the divorce laws in the UK for a couple who married there?", "Foreign family law", "foreign", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["applying Pakistani family law to an English divorce"],
                  why="the corpus is Pakistani law only"))
c("S7-X04", "unanswerable", "F7-x-khula-statistics", "family", ["en"], "latin",
  "How many khula cases were filed in Lahore's family courts this year?", "Court statistics", "punjab", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["inventing a figure"], why="court statistics are not in the corpus"))
c("S7-X05", "unanswerable", "F7-x-fsc-decision", "family", ["en"], "latin",
  "What did the Federal Shariat Court decide about section 4 of the Muslim Family Laws Ordinance?",
  "A judgment's holding", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["quoting s.4 as if it were the court's holding"],
                  why="the corpus holds no judgments (D-100)"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 7: family and personal status II -- dissolution grounds, dower, delegated "
                              "divorce, guardianship and majority, offences against women, legitimacy, Family Court "
                              "procedure, Sikh and Christian marriage, and NADRA registration."))
