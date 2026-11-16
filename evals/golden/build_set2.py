"""Build golden-pk-v1 draft SET 2 (50 cases): the core codes, criminal process, personal law and civil remedies.

Stage A0 (authored without system output) and A3 (identity resolution) of docs/10 §5, by the lead (claude),
16 Nov 2026. Every proposition was written from the provision text read in the database (evals/golden/peek.py), and
each case's `check` regexes re-verify, at every build, that the facts it states are in the held text. Not gold until
A1/A2 (two legal annotators, senior-advocate adjudication) — see evals/golden/README.md.

Where Punjab or KP publishes its own official text of a federal code, the case lists it as an `equivalent`
(grade-3 relevant unit), so a system citing either text is not marked wrong.

    python evals/golden/build_set2.py      # writes golden-pk-v1-set2.draft.jsonl and .md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set2")
c = S.case

# ---------------------------------------------------------------- citizen scenarios (20)
c("S2-C01", "citizen", "F2-theft", "liberty", ["en"], "latin",
  "Someone stole my motorbike in Peshawar. What punishment can the thief get?",
  "Punishment for theft", "fed", "kp", "answer",
  ["Theft is punishable with imprisonment of either description for up to three years, or fine, or both."],
  necessary=[(4441, "379", 3)], check=[r"three years", r"theft"])
c("S2-C02", "citizen", "F2-cheating", "money", ["en"], "latin",
  "A man in Karachi took my money promising a job abroad and disappeared. Is that a crime?",
  "Cheating and dishonestly inducing delivery of property", "fed", "sindh", "answer",
  ["Cheating that dishonestly induces the deceived person to deliver property is punishable with imprisonment of "
   "either description for up to seven years, and fine."],
  necessary=[(4441, "420", 3)], check=[r"seven years", r"dishonestly induces"])
c("S2-C03", "citizen", "F2-acid", "liberty", ["en"], "latin",
  "What is the punishment for throwing acid on someone?",
  "Punishment for hurt by corrosive substance", "fed", "sindh", "answer",
  ["Causing hurt by corrosive substance is punishable with imprisonment for life or of either description of not "
   "less than fourteen years, and a minimum fine of one million rupees."],
  necessary=[(4441, "336B", 3)], check=[r"fourteen years", r"one million"])
c("S2-C04", "citizen", "F2-rash-driving", "liberty", ["en"], "latin",
  "A driver hit and killed a pedestrian by driving carelessly. What is he liable for?",
  "Qatl-i-khata by rash or negligent driving", "fed", "sindh", "answer",
  ["Qatl-i-khata by rash or negligent driving is punishable, in addition to diyat, with imprisonment of either "
   "description for up to ten years."],
  necessary=[(4441, "320", 3)], check=[r"diyat", r"ten years"])
c("S2-C05", "citizen", "F2-arrest-24h", "liberty", ["en"], "latin",
  "Police arrested my brother last night. How long can they keep him before taking him to a magistrate?",
  "Production before a magistrate within twenty-four hours", "fed", "sindh", "answer",
  ["A person arrested must be produced before a magistrate within twenty-four hours of arrest, excluding travel "
   "time, and may not be detained beyond that without a magistrate's authority; he must be told the grounds of "
   "arrest and may consult a lawyer of his choice."],
  necessary=[(4419, "10", 3), (4501, "61", 3)], check=[r"twenty-four hours", r"legal practitioner"])
c("S2-C06", "citizen", "F2-fir-refused", "liberty", ["en"], "latin",
  "The police station in Multan refuses to register my complaint. Who can I go to?",
  "Justice of the Peace powers under section 22A CrPC", "fed", "punjab", "answer",
  ["A Justice of the Peace may, on a complaint, issue appropriate directions to the police concerned on "
   "non-registration of a criminal case."],
  necessary=[(4501, "22A", 3)], check=[r"Justice of the Peace", r"non\W?registration of a criminal case"])
c("S2-C07", "citizen", "F2-dispossession", "property", ["en"], "latin",
  "Someone has forcibly occupied my empty plot in Hyderabad. Is that a crime?",
  "Illegal dispossession of property", "fed", "sindh", "answer",
  ["Entering upon property without lawful authority to dispossess, grab, control or occupy it is an offence "
   "punishable with imprisonment of up to ten years and fine, and the victim is compensated."],
  necessary=[(1305, "3", 3)], check=[r"dispossess", r"ten years"])
c("S2-C08", "citizen", "F2-maintenance", "family", ["en"], "latin",
  "My husband does not give me any money for household expenses. What can I do?",
  "Wife's remedy for failure to maintain", "fed", "kp", "answer",
  ["A wife whose husband fails to maintain her adequately may, besides any other legal remedy, apply to the "
   "Chairman, who constitutes an Arbitration Council that may certify the maintenance payable; a suit for "
   "maintenance lies to the Family Court, which may order interim maintenance."],
  necessary=[(3283, "9", 3)], relevant=[(2944, "17A", 2), (2944, "5", 1)],
  check=[r"fails to maintain", r"Arbitration Council"])
c("S2-C09", "citizen", "F2-orphaned-grandchild", "family", ["en"], "latin",
  "My father died before my grandfather. Do we, the grandchildren, get anything from my grandfather's estate?",
  "Share of children of a predeceased son or daughter", "fed", "sindh", "answer",
  ["Children of a son or daughter who died before the succession opened receive, per stirpes, the share their "
   "parent would have received if alive."],
  necessary=[(3283, "4", 3)], check=[r"per stripes", r"would have received if alive"])
c("S2-C10", "citizen", "F2-nikah-registration", "family", ["en"], "latin",
  "Does a nikah have to be registered?", "Registration of Muslim marriages", "fed", "balochistan", "answer",
  ["Every marriage solemnized under Muslim law must be registered; Union Councils license Nikah Registrars, and a "
   "marriage not solemnized by the Nikah Registrar must be reported to him."],
  necessary=[(3283, "5", 3)], check=[r"shall be registered", r"Nikah Registrar"])
c("S2-C11", "citizen", "F2-hindu-marriage-ict", "family", ["en"], "latin",
  "We are a Hindu couple in Islamabad. What are the legal conditions for our marriage?",
  "Conditions for a Hindu marriage under the Hindu Marriage Act, 2017", "fed", "ict", "answer",
  ["Both parties must be of sound mind and able to consent, not below eighteen, outside the prohibited degrees, "
   "and neither may have a living spouse (with the stated exception)."],
  necessary=[(3483, "4", 3)], negatives=[(2022, "4", 0)], must_not_serve=[(2022, "4")],
  check=[r"eighteen years", r"prohibited relationship"])
c("S2-C12", "citizen", "F2-guardian-property", "family", ["en"], "latin",
  "I was appointed guardian of my nephew's property by the court. Can I sell his house to pay for his schooling?",
  "Limits on a court-appointed guardian's power over a ward's immovable property", "fed", "sindh", "conditional",
  ["A guardian of property appointed or declared by the Court may not sell, mortgage, gift or exchange any part of "
   "the ward's immovable property, or lease it beyond the stated terms, without the Court's previous permission."],
  necessary=[(4283, "29", 3)], check=[r"previous permission of the Court", r"immoveable property"])
c("S2-C13", "citizen", "F2-unregistered-firm", "money", ["en"], "latin",
  "My business partner in Quetta took the firm's money. Our partnership was never registered. Can I sue him?",
  "Effect of non-registration of a firm", "fed", "balochistan", "conditional",
  ["A partner cannot sue the firm or a fellow partner to enforce a right arising from the contract or the Act "
   "unless the firm is registered and he is shown as a partner in the Register of Firms (subject to the section's "
   "exceptions, such as a suit for dissolution or accounts)."],
  necessary=[(4075, "69", 3)], omitted=["whether the suit is for dissolution or accounts"],
  check=[r"unless the firm is registered", r"Register of Firms"])
c("S2-C14", "citizen", "F2-goods-fitness", "money", ["en"], "latin",
  "I told the shop I needed a pump for a deep well and it can't lift water from that depth. Can I hold the seller "
  "responsible?", "Implied condition of fitness for a particular purpose", "fed", "kp", "conditional",
  ["Where the buyer makes known the particular purpose and relies on the seller's skill or judgment, and the "
   "goods are of a kind the seller deals in, there is an implied condition that they are reasonably fit for that "
   "purpose."],
  necessary=[(3617, "16", 3)], check=[r"particular purpose", r"skill or judgment"])
c("S2-C15", "citizen", "F2-penalty-clause", "money", ["en"], "latin",
  "My contract says I must pay one lakh rupees if I am late. Do I have to pay the full amount?",
  "Compensation where a penalty or sum is named in a contract", "fed", "sindh", "answer",
  ["The party complaining of breach gets reasonable compensation not exceeding the sum named, whether or not "
   "actual loss is proved — not automatically the full sum."],
  necessary=[(4337, "74", 3)], check=[r"reasonable compensation not exceeding"])
c("S2-C16", "citizen", "F2-frustration", "money", ["en"], "latin",
  "I agreed to supply goods but a new government ban makes it illegal. Am I still bound?",
  "Contract becoming impossible or unlawful after it is made", "fed", "balochistan", "conditional",
  ["A contract to do an act that afterwards becomes impossible, or unlawful because of an event the promisor could "
   "not prevent, becomes void when the act becomes impossible or unlawful."],
  necessary=[(4337, "56", 3)], check=[r"becomes void when the act becomes impossible or unlawful"])
c("S2-C17", "citizen", "F2-land-acquisition", "property", ["en"], "latin",
  "The government is acquiring my land near Sukkur for a road. How is the compensation worked out?",
  "Matters considered in determining compensation for acquired land", "fed", "sindh", "answer",
  ["The Court considers, first, the market value of the land at the date of the section 4(1) notification, taking "
   "into account transfers of similarly situated land in similar use, along with the other matters section 23 "
   "lists."],
  necessary=[(4099, "23", 3)], relevant=[(4099, "4", 1)], check=[r"market-value", r"section 4"])
c("S2-C18", "citizen", "F2-online-dignity", "privacy", ["en"], "latin",
  "Someone in Lahore is posting false things about me on Facebook to ruin my reputation. Is that a crime?",
  "Offences against the dignity of a natural person (PECA s.20)", "fed", "punjab", "answer",
  ["Intentionally and publicly transmitting information through an information system that one knows to be false, "
   "and that harms a person's reputation or privacy, is punishable with imprisonment up to three years, fine up to "
   "one million rupees, or both; the aggrieved person may apply for its removal."],
  necessary=[(3592, "20", 3)], negatives=[(4441, "500", 1)],
  check=[r"knows to be false", r"three years", r"one million"])
c("S2-C19", "citizen", "F2-cyberstalking", "privacy", ["en"], "latin",
  "My ex keeps contacting me online and watching my accounts even after I told him to stop. What does the law say?",
  "Cyber stalking", "fed", "sindh", "answer",
  ["Using an information system, the internet or similar means to repeatedly contact a person despite clear "
   "disinterest, or to monitor or spy on them, with intent to coerce, intimidate or harass, is the offence of "
   "cyber stalking."],
  necessary=[(3592, "24", 3)], check=[r"cyber stalking", r"clear indication of disinterest"])
c("S2-C20", "citizen", "F2-defamation-criminal", "privacy", ["en"], "latin",
  "A neighbour in Hyderabad spread lies about my character. Can he be punished criminally?",
  # scoped to Sindh on purpose: the Punjab Code text of PPC s.500 (doc 4458) lacks the 2004 'originator' proviso
  # the federal text carries (Act IX of 2004); which text is current in Punjab is not settled by the corpus — a
  # question for the A1 annotators, not a gold claim
  "Punishment for defamation under the Pakistan Penal Code", "fed", "sindh", "answer",
  ["Defamation is punishable with imprisonment up to two years, fine, or both; the originator of the defamatory "
   "imputation faces up to five years or a fine of not less than one hundred thousand rupees, or both."],
  necessary=[(4441, "500", 3)], check=[r"two years", r"originator"])

# ---------------------------------------------------------------- professional lookups (12)
c("S2-P01", "professional", "F2-common-intention", "liberty", ["en"], "latin",
  "Liability for acts done in furtherance of common intention — PPC", "Section 34 PPC", "fed", "sindh", "answer",
  ["When several persons do a criminal act in furtherance of the common intention of all, each is liable as if he "
   "had done it alone."], necessary=[(4441, "34", 3)], check=[r"common intention"])
c("S2-P02", "professional", "F2-arrest-warrantless", "liberty", ["en"], "latin",
  "When may police arrest without a warrant?", "Section 54 CrPC", "fed", "sindh", "answer",
  ["Section 54 CrPC lets police arrest without a warrant, among others, a person concerned in a cognizable offence "
   "or against whom a reasonable complaint, credible information or reasonable suspicion exists."],
  necessary=[(4501, "54", 3)], check=[r"without a warrant", r"cognizable offence"])
c("S2-P03", "professional", "F2-compounding", "liberty", ["en"], "latin",
  "Which PPC offences may be compounded, and by whom?", "Section 345 CrPC", "fed", "kp", "answer",
  ["Section 345 CrPC lists, in its tables, the PPC offences that may be compounded and the person by whom each may "
   "be compounded."], necessary=[(4501, "345", 3)], check=[r"may be compounded"])
c("S2-P04", "professional", "F2-double-jeopardy", "liberty", ["en"], "latin",
  "Constitutional protection against double punishment and self-incrimination", "Article 13", "fed", "ict",
  "answer", ["No person shall be prosecuted or punished for the same offence more than once, or be compelled to be "
             "a witness against himself."], necessary=[(4419, "13", 3)],
  check=[r"more than once", r"witness against himself"])
c("S2-P05", "professional", "F2-retrospective", "liberty", ["en"], "latin",
  "Can a law punish an act that was not an offence when it was done?", "Article 12", "fed", "balochistan", "answer",
  ["No law may authorise punishment for an act not punishable when done, or a greater or different penalty than "
   "the law then prescribed — except for laws on abrogation or subversion of a Constitution since 23 March 1956."],
  necessary=[(4419, "12", 3)], check=[r"not punishable by law at the time", r"abrogation or subversion"])
c("S2-P06", "professional", "F2-witness-number", "money", ["en"], "latin",
  "How many witnesses must attest a written financial obligation?", "Article 17 Qanun-e-Shahadat", "fed", "sindh",
  "answer", ["In matters of financial or future obligations reduced to writing, the instrument shall be attested by "
             "two men, or one man and two women, unless a Hudood or special law provides otherwise."],
  necessary=[(4166, "17", 3)], check=[r"two men, or one man and two women"])
c("S2-P07", "professional", "F2-attested-document", "property", ["en"], "latin",
  "Proving a document required by law to be attested", "Article 79 Qanun-e-Shahadat", "fed", "punjab", "answer",
  ["A document required by law to be attested cannot be used as evidence until at least two attesting witnesses "
   "(if alive and available) are called to prove its execution; a registered document, other than a will, needs no "
   "attesting witness unless its execution is specifically denied."],
  necessary=[(4166, "79", 3)], check=[r"two attesting witnesses", r"not being a will"])
c("S2-P08", "professional", "F2-burden-of-proof", "routine", ["en"], "latin",
  "Who bears the burden of proof?", "Article 117 Qanun-e-Shahadat", "fed", "kp", "answer",
  ["Whoever wants a court to give judgment on a right or liability that depends on facts he asserts must prove "
   "those facts."], necessary=[(4166, "117", 3)], check=[r"must prove that those facts exist"])
c("S2-P09", "professional", "F2-condonation", "deadline", ["en"], "latin",
  "Condonation of delay in filing an appeal", "Section 5 Limitation Act", "fed", "sindh", "answer",
  ["An appeal or an application to which section 5 applies may be admitted after the limitation period if the "
   "appellant or applicant satisfies the Court that he had sufficient cause for the delay."],
  necessary=[(4237, "5", 3)], check=[r"sufficient cause"])
c("S2-P10", "professional", "F2-limitation-bar", "deadline", ["en"], "latin",
  "Must a court dismiss a time-barred suit even if limitation is not pleaded?", "Section 3 Limitation Act", "fed",
  "balochistan", "answer",
  ["Subject to sections 4 to 25, every suit, appeal or application made after the prescribed period shall be "
   "dismissed although limitation has not been set up as a defence."],
  necessary=[(4237, "3", 3)], check=[r"although limitation has not been set up as a defence"])
c("S2-P11", "professional", "F2-lis-pendens", "property", ["en"], "latin",
  "Transfer of property while a suit about it is pending", "Section 52 Transfer of Property Act", "fed", "sindh",
  "answer", ["During a non-collusive suit in which a right to immovable property is directly and specifically in "
             "question, no party may transfer or deal with the property so as to affect another party's rights under "
             "the decree, except under the Court's authority."],
  necessary=[(3991, "52", 3)], check=[r"directly and specifically in question", r"authority of the Court"])
c("S2-P12", "professional", "F2-part-performance", "property", ["en"], "latin",
  "Protection of a transferee in possession under a written contract of sale", "Section 53A Transfer of Property Act",
  "fed", "balochistan", "answer",
  ["Where a person contracts in signed writing to transfer immovable property and the transferee has taken or "
   "continued possession in part performance and is willing to perform, the transferor is barred from enforcing "
   "rights against the transferee other than those the contract provides."],
  necessary=[(3991, "53A", 3)], check=[r"part performance", r"writing signed"])

# ---------------------------------------------------------------- procedural (8)
c("S2-R01", "procedural", "F2-first-appeal", "deadline", ["en"], "latin",
  "The civil court decided against me. Can I appeal, even though the decree was ex parte?",
  "Appeal from an original decree", "fed", "sindh", "answer",
  ["An appeal lies from every decree passed in original jurisdiction, including an ex parte decree, but not from a "
   "decree passed with the parties' consent."],
  necessary=[(4463, "96", 3)], check=[r"ex-parte", r"consent of the parties"])
c("S2-R02", "procedural", "F2-civil-revision", "routine", ["en"], "latin",
  "No appeal lies from the trial court's order. Can the High Court still correct it?",
  "Civil revision", "fed", "sindh", "answer",
  ["In a case decided by a subordinate court where no appeal lies, the High Court may interfere in revision if the "
   "court exercised a jurisdiction it lacked, failed to exercise one it had, or acted illegally or with material "
   "irregularity."],
  necessary=[(4463, "115", 3)], check=[r"material irregularity", r"no appeal lies"])
c("S2-R03", "procedural", "F2-decree-fraud", "property", ["en"], "latin",
  "A decree against my land was obtained by fraud. Do I file a new suit?",
  "Challenge to a decree on the plea of fraud (s.12(2) CPC)", "fed", "kp", "answer",
  ["A person challenging a judgment, decree or order on the plea of fraud, misrepresentation or want of "
   "jurisdiction applies to the court that passed the final judgment, decree or order — not by a separate suit."],
  necessary=[(4463, "12", 3)], check=[r"fraud, mis-representation or want of jurisdiction", r"not by a separate suit"])
c("S2-R04", "procedural", "F2-declaration", "property", ["en"], "latin",
  "My cousin denies that I own my share of our family house. How do I get the court to declare my right?",
  "Suit for declaration of title", "fed", "sindh", "answer",
  ["A person entitled to a right to property may sue anyone denying it for a declaration, but the court will not "
   "grant a mere declaration where the plaintiff could seek further relief and omits to do so."],
  necessary=[(3944, "42", 3)], check=[r"declaration", r"further relief"])
c("S2-R05", "procedural", "F2-perpetual-injunction", "property", ["en"], "latin",
  "My neighbour keeps building on my land. Can the court permanently stop him?",
  "When a perpetual injunction may be granted", "fed", "sindh", "conditional",
  ["A perpetual injunction may be granted to prevent breach of an obligation in the applicant's favour; where the "
   "defendant invades or threatens the plaintiff's property, it may be granted in the cases section 54 lists."],
  necessary=[(3944, "54", 3)], check=[r"perpetual injunction", r"invades or threatens"])
c("S2-R06", "procedural", "F2-set-aside-award", "money", ["en"], "latin",
  "Can I challenge an arbitration award because the arbitrator was biased?",
  "Grounds for setting aside an award", "fed", "sindh", "conditional",
  ["An award may be set aside only on the grounds section 30 lists: the arbitrator's misconduct of himself or the "
   "proceedings, an award made after supersession or invalidity of the proceedings, or improper procurement or "
   "other invalidity."],
  necessary=[(3132, "30", 3)], check=[r"misconducted", r"improperly procured"])
c("S2-R07", "procedural", "F2-hindu-divorce-consent", "family", ["en"], "latin",
  "My Hindu husband and I in Islamabad both want a divorce. What is the procedure?",
  "Termination of a Hindu marriage by mutual consent", "fed", "ict", "answer",
  ["Both spouses present a joint petition on the ground that they have lived separately for one year or more and "
   "agree the marriage should end; the decision is taken not earlier than six months after the petition."],
  necessary=[(3483, "15", 3)], relevant=[(3483, "12", 1)], check=[r"one year or more", r"six months"])
c("S2-R08", "procedural", "F2-interim-maintenance", "family", ["en"], "latin",
  "My maintenance case in the family court will take months. Can I get money in the meantime?",
  "Interim maintenance in a Punjab maintenance suit (Punjab text of the Family Courts Act)", "punjab", "punjab",
  "answer",
  ["In Punjab the Family Court shall, on the defendant's first appearance, fix interim monthly maintenance for the "
   "wife or child; if it is not paid by the fourteenth of each month the defence stands struck off and the suit is "
   "decreed. Maintenance decreed rises by ten percent a year unless the court prescribes the increase."],
  # the Punjab text (doc 4081 s.17-A) differs materially from the federal s.17A (doc 2944), which is the weaker
  # 'may pass an interim order' text; in Punjab the federal text is background only
  necessary=[(4081, "17-A", 3)], relevant=[(2944, "17A", 1)],
  check=[r"first appearance", r"fourteen day of each month", r"ten percent each year"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5), each in its English family
c("S2-U01", "urdu", "F2-theft", "liberty", ["ur-Latn"], "roman_urdu", "Chori ki saza kya hai?",
  "Punishment for theft (Roman Urdu variant of S2-C01)", "fed", "kp", "answer",
  ["Theft is punishable with imprisonment up to three years, or fine, or both."],
  necessary=[(4441, "379", 3)], check=[r"three years"])
c("S2-U02", "urdu", "F2-arrest-24h", "liberty", ["ur"], "arabic",
  "پولیس گرفتاری کے بعد کسی کو مجسٹریٹ کے سامنے پیش کیے بغیر کتنی دیر تک رکھ سکتی ہے؟",
  "Production before a magistrate (Urdu variant of S2-C05)", "fed", "punjab", "answer",
  ["Within twenty-four hours of arrest, excluding travel time."],
  necessary=[(4419, "10", 3), (4501, "61", 3)], check=[r"twenty-four hours"])
c("S2-U03", "urdu", "F2-maintenance", "family", ["ur-Latn"], "roman_urdu",
  "Shohar ghar ka kharcha nahi deta, biwi kya kar sakti hai?",
  "Wife's remedy for failure to maintain (Roman Urdu variant of S2-C08)", "fed", "sindh", "answer",
  ["The wife may apply to the Chairman, who constitutes an Arbitration Council to certify maintenance, besides any "
   "other remedy."], necessary=[(3283, "9", 3)], relevant=[(2944, "17A", 2)], check=[r"Arbitration Council"])
c("S2-U04", "urdu", "F2-dispossession", "property", ["ur"], "arabic",
  "کسی نے میرے خالی پلاٹ پر زبردستی قبضہ کر لیا ہے، کیا یہ جرم ہے؟",
  "Illegal dispossession (Urdu variant of S2-C07)", "fed", "sindh", "answer",
  ["Yes: illegal dispossession is punishable with up to ten years' imprisonment and fine."],
  necessary=[(1305, "3", 3)], check=[r"ten years"])
c("S2-U05", "urdu", "F2-online-dignity", "privacy", ["ur-Latn"], "roman_urdu",
  "Koi online meri jhooti baatein phaila kar meri izzat kharab kar raha hai, kya yeh jurm hai?",
  "False information harming reputation online (Roman Urdu variant of S2-C18)", "fed", "punjab", "answer",
  ["Yes: PECA s.20 punishes it with up to three years, fine up to one million rupees, or both."],
  necessary=[(3592, "20", 3)], check=[r"three years"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S2-X01", "unanswerable", "F2-x-judgment", "routine", ["en"], "latin",
  "What did the Supreme Court hold in the Zulfikar Ali Bhutto presidential reference?",
  "A judgment's holding", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["summarising from model memory", "citing a statute instead"],
                  why="the corpus holds no judgments (CLAUDE.md: no judgment table yet)"))
c("S2-X02", "unanswerable", "F2-x-foreign", "liberty", ["en"], "latin",
  "What is the punishment for theft in the UAE?", "Foreign criminal law", "foreign", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from PPC s.379"], why="the corpus is Pakistani law only"),
  negatives=[(4441, "379", 0)])
c("S2-X03", "unanswerable", "F2-x-fiqh", "family", ["en"], "latin",
  "Is my nikah valid under Hanafi fiqh if my wali was not present?",
  "A religious ruling under a school of fiqh", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["issuing a fatwa", "answering from MFLO s.5 registration rules"],
                  why="the validity of a nikah under a school of fiqh is not settled by any statute in the corpus"),
  negatives=[(3283, "5", 0)])
c("S2-X04", "unanswerable", "F2-x-record", "liberty", ["en"], "latin",
  "Is there any FIR registered against my CNIC number?", "A personal criminal-record lookup", "fed", None,
  "abstain", [], abstention=dict(code="unsupported_scope", requiredClarification=[],
                                 unsafeAlternatives=["guessing", "explaining s.154 as if it answered the question"],
                                 why="the system holds law, not police records about individuals"))
c("S2-X05", "unanswerable", "F2-x-future-tax", "money", ["en"], "latin",
  "What will the income tax slabs for salaried people be in tax year 2029?",
  "Law not yet made", "fed", None, "abstain", [],
  abstention=dict(code="abstained", requiredClarification=[],
                  unsafeAlternatives=["projecting current rates forward", "quoting the current First Schedule"],
                  why="no law fixing tax year 2029 rates exists; the corpus answers law as at a date, not forecasts"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 2: the core codes (PPC, CrPC, CPC, Contract, Qanun-e-Shahadat, Limitation, TPA, "
                              "Specific Relief), personal law and online offences."))
