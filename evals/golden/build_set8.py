"""Build golden-pk-v1 draft SET 8 (50 cases): public law.

The Constitution's rights articles not yet used by sets 1-4 (security of person, the 2024 right to a clean and healthy
environment, safeguards on arrest, forced and child labour, dignity and privacy of home, movement, assembly,
association, trade, religion, religious instruction, property and its compulsory acquisition, access to public
places, non-discrimination in service); voter enrolment, nomination, secret and postal ballots, election expenses,
election petitions and tribunals; the Exit Control List; overseas employment promoters, the Protector of Emigrants
and unlawful or fraudulent emigration; foreigners' offences; federal civil servants' retirement, probation, transfer
and appeals; the federal and Punjab Service Tribunals; and NAB's voluntary return.

Articles changed by the 26th and 27th Amendments' court provisions are left out until the amended texts are reviewed
(D-076). Stage A0 + A3 by the lead (claude), 20 Nov 2026; propositions written from the held text (peek.py) and
re-verified by each case's `check` regexes at every build. Not gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set8.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set8")
c = S.case
CON, ELEC, ECL, EMIG, FOR, ST_FED, ST_PB, CSA, NAO = 4419, 4382, 1615, 3673, 1869, 1707, 3467, 2521, 4176

# ---------------------------------------------------------------- citizen scenarios (20)
c("S8-C01", "citizen", "F8-arrest-safeguards", "liberty", ["en"], "latin",
  "Police arrested me in Karachi, would not say why, and refused to let me call a lawyer. Is that lawful?",
  "Constitutional safeguards on arrest", "fed", "sindh", "answer",
  ["An arrested person must be told the grounds of arrest as soon as may be, may not be denied a lawyer of his "
   "choice, and must be produced before a magistrate within twenty-four hours."],
  necessary=[(CON, "10", 3)], check=[r"grounds for such arrest", r"twenty-four hours"])
c("S8-C02", "citizen", "F8-clean-environment", "routine", ["en"], "latin",
  "A factory near our homes in Lahore pours out black smoke every day. Do we have any constitutional right here?",
  "The right to a clean, healthy and sustainable environment", "fed", "punjab", "answer",
  ["Every person is entitled to a clean, healthy and sustainable environment."],
  necessary=[(CON, "9A", 3)], check=[r"clean, healthy and sustainable environment"])
c("S8-C03", "citizen", "F8-forced-labour", "liberty", ["en"], "latin",
  "A brick kiln owner near Kasur will not let our family leave until we repay an advance. Is that allowed?",
  "Forced labour is prohibited", "fed", "punjab", "answer",
  ["Slavery is forbidden and all forms of forced labour and traffic in human beings are prohibited."],
  necessary=[(CON, "11", 3)], check=[r"forced labour"])
c("S8-C04", "citizen", "F8-privacy-of-home", "liberty", ["en"], "latin",
  "Officials barged into my house in Quetta at night without any reason. What does the Constitution say?",
  "Dignity of man and privacy of home", "fed", "balochistan", "answer",
  ["The dignity of man and, subject to law, the privacy of home are inviolable."],
  necessary=[(CON, "14", 3)], check=[r"privacy of home"])
c("S8-C05", "citizen", "F8-freedom-of-movement", "liberty", ["en"], "latin",
  "Can anyone stop me, a citizen from Gilgit, from moving to Karachi and settling there?",
  "Freedom of movement and residence", "fed", "sindh", "answer",
  ["Every citizen may remain in, enter and move freely throughout Pakistan and reside and settle anywhere in it, "
   "subject to reasonable restrictions imposed by law in the public interest."],
  necessary=[(CON, "15", 3)], check=[r"reside and settle in any part"])
c("S8-C06", "citizen", "F8-assembly", "liberty", ["en"], "latin",
  "Do we have a right to hold a peaceful protest in Islamabad?", "Freedom of assembly", "fed", "ict", "answer",
  ["Every citizen may assemble peacefully and without arms, subject to reasonable restrictions imposed by law in the "
   "interest of public order."],
  necessary=[(CON, "16", 3)], check=[r"assemble peacefully and without arms"])
c("S8-C07", "citizen", "F8-civil-servant-party", "routine", ["en"], "latin",
  "I am a government officer in Peshawar. Can I join a political party?",
  "Political party membership is a right of citizens not in the service of Pakistan", "fed", "kp", "answer",
  ["The right to form or be a member of a political party belongs to every citizen not being in the service of "
   "Pakistan."],
  necessary=[(CON, "17", 3)], check=[r"not being in the service of Pakistan"])
c("S8-C08", "citizen", "F8-trade-licensing", "money", ["en"], "latin",
  "Can the government require me to get a licence before I open a pharmacy in Hyderabad, or is that against my "
  "freedom to do business?", "Freedom of trade and licensing", "fed", "sindh", "answer",
  ["Every citizen may enter any lawful profession or conduct lawful business, subject to prescribed "
   "qualifications; this does not prevent regulation of a trade or profession by a licensing system."],
  necessary=[(CON, "18", 3)], check=[r"licensing system"])
c("S8-C09", "citizen", "F8-freedom-of-religion", "routine", ["en"], "latin",
  "Our Hindu community in Tharparkar wants to build and run its own temple. Do we have that right?",
  "Freedom to profess religion and manage religious institutions", "fed", "sindh", "answer",
  ["Subject to law, public order and morality, every citizen may profess, practise and propagate his religion, and "
   "every denomination may establish, maintain and manage its religious institutions."],
  necessary=[(CON, "20", 3)], check=[r"profess, practice and propagate", r"religious institutions"])
c("S8-C10", "citizen", "F8-religious-instruction", "routine", ["en"], "latin",
  "My son's school in Islamabad makes him attend religious lessons of a religion that is not ours. Can it?",
  "No compulsory religious instruction in another religion", "fed", "ict", "answer",
  ["No one attending an educational institution may be required to receive instruction, take part in a ceremony or "
   "attend worship relating to a religion other than his own."],
  necessary=[(CON, "22", 3)], check=[r"religion other than his own"])
c("S8-C11", "citizen", "F8-compulsory-acquisition", "property", ["en"], "latin",
  "The government took part of my land in Sialkot for a road and has paid nothing. What does the Constitution "
  "say?", "Compulsory acquisition only for a public purpose and with compensation", "fed", "punjab", "answer",
  ["No one may be deprived of property save by law, and property may be compulsorily acquired only for a public "
   "purpose under a law providing for compensation."],
  necessary=[(CON, "24", 3)], check=[r"compulsorily acquired", r"compensation"])
c("S8-C12", "citizen", "F8-public-places", "routine", ["en"], "latin",
  "A park in Karachi refused to let us in because of our caste. Is that allowed?",
  "Non-discrimination in access to public places", "fed", "sindh", "answer",
  ["There may be no discrimination in access to places of public entertainment or resort, not meant only for "
   "religious purposes, on the ground only of race, religion, caste, sex, residence or place of birth."],
  necessary=[(CON, "26", 3)], check=[r"places of public entertainment", r"caste"])
c("S8-C13", "citizen", "F8-service-discrimination", "routine", ["en"], "latin",
  "I was told I cannot be appointed to a federal post because of where I was born. Is that lawful?",
  "Safeguard against discrimination in services", "fed", "ict", "conditional",
  ["A citizen otherwise qualified may not be discriminated against in appointment to the service of Pakistan on the "
   "ground only of race, religion, caste, sex, residence or place of birth (save the reservations the Article "
   "allows)."],
  necessary=[(CON, "27", 3)], omitted=["whether a permitted reservation applies"],
  check=[r"otherwise qualified for appointment", r"place of birth"])
c("S8-C14", "citizen", "F8-ecl-review", "liberty", ["en"], "latin",
  "My name has been placed on the Exit Control List. How can I challenge it?", "Review of an exit control order",
  "fed", "punjab", "answer",
  ["A person aggrieved may, within fifteen days of the order, make a representation to the Federal Government for "
   "review, which hears him and decides."],
  necessary=[(ECL, "3", 3)], relevant=[(ECL, "2", 2)], check=[r"representation to the Federal Government"])
c("S8-C15", "citizen", "F8-fake-recruiter", "money", ["en"], "latin",
  "A man in Gujrat took my money promising a job abroad and then disappeared. Is that a crime?",
  "Fraudulently inducing a person to emigrate", "fed", "punjab", "answer",
  ["Causing or inducing a person to emigrate by fraud or wilful misrepresentation, or forging emigration documents, "
   "is punishable with imprisonment; recruiting for employment abroad needs an Overseas Employment Promoter's "
   "licence."],
  necessary=[(EMIG, "18", 3)], relevant=[(EMIG, "12", 2)], check=[r"fraud or wilful misrepresentation"])
c("S8-C16", "citizen", "F8-foreigner-overstay", "liberty", ["en"], "latin",
  "My cousin from abroad stayed on in Peshawar after his visa expired. What can happen to him?",
  "Penalties under the Foreigners Act", "fed", "kp", "conditional",
  ["Contravening the Act or an order under it is punishable with up to three years' imprisonment and a fine."],
  necessary=[(FOR, "14", 3)], omitted=["the order or condition contravened"], check=[r"three years"])
c("S8-C17", "citizen", "F8-punjab-service-appeal", "routine", ["en"], "latin",
  "I am a Punjab government teacher and the department dismissed me. Where do I appeal and by when?",
  "Appeal to the Punjab Service Tribunal", "punjab", "punjab", "answer",
  ["A civil servant aggrieved by a final departmental order on his terms of service may appeal to the Tribunal "
   "within thirty days of its communication (after any departmental appeal the rules provide)."],
  necessary=[(ST_PB, "4", 3)], check=[r"within thirty days of the communication"])
c("S8-C18", "citizen", "F8-forced-retirement", "routine", ["en"], "latin",
  "I am a federal civil servant in Islamabad with 22 years' service. Can the government retire me early?",
  "Retirement after twenty years in the public interest", "fed", "ict", "answer",
  ["After twenty years' qualifying service the competent authority may retire a civil servant in the public "
   "interest, after informing him of the grounds and hearing him; otherwise he retires at sixty."],
  necessary=[(CSA, "13", 3)], check=[r"twenty", r"sixtieth year of his age"])
c("S8-C19", "citizen", "F8-missing-from-roll", "routine", ["en"], "latin",
  "My name is not on the voters' list in Multan. What can I do?", "Enrolment outside periodical revision",
  "fed", "punjab", "answer",
  ["A person entitled to be enrolled may apply on the prescribed form, with a copy of his National Identity Card, "
   "to the appropriate Registration Officer for inclusion."],
  necessary=[(ELEC, "37", 3)], check=[r"Registration Officer", r"National Identity Card"])
c("S8-C20", "citizen", "F8-who-challenges-election", "routine", ["en"], "latin",
  "I am a voter and I think the election in my constituency in Sukkur was rigged. Can I challenge it?",
  "Only a candidate may file an election petition", "fed", "sindh", "answer",
  ["No election may be called in question except by an election petition filed by a candidate for that election."],
  necessary=[(ELEC, "139", 3)], check=[r"election petition filed by a candidate"])

# ---------------------------------------------------------------- professional lookups (12)
c("S8-P01", "professional", "F8-security-of-person", "liberty", ["en"], "latin",
  "Constitutional guarantee of life and liberty", "Article 9", "fed", "ict", "answer",
  ["No person shall be deprived of life or liberty save in accordance with law."],
  necessary=[(CON, "9", 3)], check=[r"life or liberty save in accordance with law"])
c("S8-P02", "professional", "F8-speech-restrictions", "liberty", ["en"], "latin",
  "Grounds on which freedom of speech may be restricted", "Article 19", "fed", "ict", "answer",
  ["Reasonable restrictions imposed by law in the interest of the glory of Islam, the integrity, security or defence "
   "of Pakistan, friendly relations with foreign States, public order, decency or morality, or in relation to "
   "contempt of court or commission of or incitement to an offence."],
  necessary=[(CON, "19", 3)], check=[r"reasonable restrictions", r"contempt of court"])
c("S8-P03", "professional", "F8-property-right", "property", ["en"], "latin",
  "Right to acquire, hold and dispose of property", "Article 23", "fed", "sindh", "answer",
  ["Every citizen may acquire, hold and dispose of property anywhere in Pakistan, subject to the Constitution and "
   "reasonable restrictions imposed by law in the public interest."],
  necessary=[(CON, "23", 3)], check=[r"acquire, hold and dispose of property"])
c("S8-P04", "professional", "F8-child-hazardous", "liberty", ["en"], "latin",
  "Constitutional bar on children in hazardous employment", "Article 11(3)", "fed", "sindh", "answer",
  ["No child below fourteen may be engaged in any factory, mine or other hazardous employment."],
  necessary=[(CON, "11", 3)], check=[r"below the age of fourteen years"])
c("S8-P05", "professional", "F8-nomination", "routine", ["en"], "latin",
  "How is a candidate nominated?", "Section 60 Elections Act, 2017", "fed", "ict", "answer",
  ["A voter of the constituency proposes and another seconds a qualified person on a separate nomination paper on "
   "Form A, signed by both, with the candidate's declarations; no voter may subscribe more than one paper."],
  necessary=[(ELEC, "60", 3)], check=[r"Form A", r"proposer and the seconder"])
c("S8-P06", "professional", "F8-enrol-once", "routine", ["en"], "latin",
  "Enrolment on more than one electoral roll", "Section 45 Elections Act, 2017", "fed", "sindh", "answer",
  ["A person may not be enrolled more than once for an electoral area or on the rolls of more than one area."],
  necessary=[(ELEC, "45", 3)], check=[r"more than once"])
c("S8-P07", "professional", "F8-election-expenses", "money", ["en"], "latin",
  "Whose spending counts as a candidate's election expenses?", "Section 132 Elections Act, 2017", "fed", "kp",
  "answer",
  ["Expenses incurred by any person or party on the candidate's behalf, from nomination to the final consolidated "
   "result, are deemed the candidate's election expenses."],
  necessary=[(ELEC, "132", 3)], check=[r"deemed to be the elect"])
c("S8-P08", "professional", "F8-election-tribunals", "routine", ["en"], "latin",
  "Composition of Election Tribunals", "Section 140 Elections Act, 2017", "fed", "ict", "answer",
  ["The Commission appoints Election Tribunals; for an Assembly or Senate election, a person who is or has been a "
   "High Court Judge; for a local government election, a District and Sessions Judge or Additional Judge (serving "
   "or former)."],
  necessary=[(ELEC, "140", 3)], check=[r"Judge of a High Court"])
c("S8-P09", "professional", "F8-ecl-power", "liberty", ["en"], "latin",
  "Power to prohibit a person from leaving Pakistan", "Section 2 Exit from Pakistan (Control) Ordinance, 1981",
  "fed", "ict", "answer",
  ["The Federal Government may by order prohibit a person or class from leaving Pakistan despite valid travel "
   "documents, without first giving a chance to show cause."],
  necessary=[(ECL, "2", 3)], check=[r"valid travel documents", r"showing cause"])
c("S8-P10", "professional", "F8-nab-voluntary-return", "money", ["en"], "latin",
  "Voluntary return of assets before investigation", "Section 25 National Accountability Ordinance, 1999", "fed",
  "ict", "answer",
  ["A person who, before an investigation is authorised, voluntarily offers to return assets gained through an "
   "offence may, on the Chairman's acceptance and deposit of the amount, be discharged."],
  necessary=[(NAO, "25", 3)], check=[r"voluntarily comes forward"])
c("S8-P11", "professional", "F8-federal-service-appeal", "routine", ["en"], "latin",
  "Limitation for a federal civil servant's appeal to the Service Tribunal", "Section 4 Service Tribunals Act, 1973",
  "fed", "ict", "answer",
  ["Within thirty days of the communication of the departmental order (or six months of the Tribunal's "
   "establishment, whichever is later)."],
  necessary=[(ST_FED, "4", 3)], check=[r"within thirty days of the communication"])
c("S8-P12", "professional", "F8-unlawful-emigration", "liberty", ["en"], "latin",
  "Punishment for emigrating unlawfully", "Section 17 Emigration Ordinance, 1979", "fed", "punjab", "answer",
  ["Emigrating or departing otherwise than under the Ordinance and rules is punishable with up to five years and a "
   "fine of up to one million rupees."],
  necessary=[(EMIG, "17", 3)], check=[r"five years", r"one million rupees"])

# ---------------------------------------------------------------- procedural (8)
c("S8-R01", "procedural", "F8-cnic-to-roll", "routine", ["en"], "latin",
  "I just got my first ID card in Lahore. How do I get onto the electoral roll?",
  "NADRA transmits new card-holders' data to the Commission", "fed", "punjab", "answer",
  ["NADRA transmits the data of every fresh National Identity Card to the Election Commission, which registers the "
   "holder at the permanent or temporary address chosen in the card application."],
  necessary=[(ELEC, "25", 3)], check=[r"transmit relevant data"])
c("S8-R02", "procedural", "F8-promoter-licence", "money", ["en"], "latin",
  "How do I get a licence to recruit workers in Karachi for jobs abroad?",
  "Grant of an Overseas Employment Promoter's Licence", "fed", "sindh", "answer",
  ["Apply for a licence with the prescribed information, documents, security and fee; after inquiry the licence may "
   "be granted on terms and conditions."],
  necessary=[(EMIG, "12", 3)], check=[r"apply for a licence"])
c("S8-R03", "procedural", "F8-protector-registration", "routine", ["en"], "latin",
  "I have a job offer abroad through a licensed promoter in Peshawar. What must I do before I leave?",
  "Appearance before the Protector of Emigrants", "fed", "kp", "answer",
  ["Before emigrating the person appears, in person or by prescribed video link, with the promoter or his "
   "representative before the Protector of Emigrants and furnishes the prescribed information."],
  necessary=[(EMIG, "15", 3)], check=[r"Protector of Emigrants", r"appear in person"])
c("S8-R04", "procedural", "F8-challenge-voter", "routine", ["en"], "latin",
  "As a polling agent in Islamabad, what can I do if I believe someone has already voted?",
  "Challenge of voters at the polling station", "fed", "ict", "answer",
  ["The candidate, election agent or polling agent may declare to the Presiding Officer the reasonable belief, "
   "undertake to prove it in court and deposit one hundred rupees; the Presiding Officer may then proceed as the "
   "section provides."],
  necessary=[(ELEC, "86", 3)], check=[r"one hundred rupees", r"Presiding Officer"])
c("S8-R05", "procedural", "F8-roll-clerical-error", "routine", ["en"], "latin",
  "My name is misspelled on the electoral roll in Hyderabad. Can the Registration Officer fix it?",
  "Correction of clerical errors in the roll", "fed", "sindh", "answer",
  ["The Registration Officer may correct clerical, printing or other errors discovered in the roll, but not so as to "
   "include or exclude any voter."],
  necessary=[(ELEC, "34", 3)], check=[r"clerical, printing or other error"])
c("S8-R06", "procedural", "F8-departmental-appeal", "routine", ["en"], "latin",
  "How long do I have to file a departmental appeal against an order about my federal service?",
  "Time for a departmental appeal or review", "fed", "ict", "answer",
  ["Where the rules give an appeal or review, it is made within thirty days of the order, unless otherwise "
   "prescribed."],
  necessary=[(CSA, "22", 3)], check=[r"within thirty days of the date of such order"])
c("S8-R07", "procedural", "F8-tribunal-powers", "routine", ["en"], "latin",
  "What can the Federal Service Tribunal do with my appeal?", "Powers of the Tribunal", "fed", "ict", "answer",
  ["It may confirm, set aside, vary or modify the order, with a civil court's powers to summon, compel documents and "
   "issue commissions."],
  necessary=[(ST_FED, "5", 3)], check=[r"confirm, set aside, vary or modify"])
c("S8-R08", "procedural", "F8-postal-ballot", "routine", ["en"], "latin",
  "I am disabled and cannot travel to the polling station in Quetta. Can I vote by post?", "Postal ballot",
  "fed", "balochistan", "answer",
  ["A person with a physical disability unable to travel who holds a National Identity Card with the disability logo "
   "may vote by postal ballot as prescribed."],
  necessary=[(ELEC, "93", 3)], check=[r"postal ballot", r"physical disability"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5)
c("S8-U01", "urdu", "F8-arrest-safeguards", "liberty", ["ur-Latn"], "roman_urdu",
  "Police ne mujhe Karachi mein giraftar kiya magar wajah nahi batai aur wakeel se milne nahi diya, kya yeh jaiz "
  "hai?", "Arrest safeguards (Roman Urdu variant of S8-C01)", "fed", "sindh", "answer",
  ["No: the grounds must be told and a lawyer allowed; production before a magistrate within twenty-four hours."],
  necessary=[(CON, "10", 3)], check=[r"grounds for such arrest"])
c("S8-U02", "urdu", "F8-missing-from-roll", "routine", ["ur"], "arabic",
  "میرا نام ووٹر لسٹ میں نہیں ہے، میں اپنا نام کیسے شامل کرواؤں؟",
  "Missing from the voters' list (Urdu variant of S8-C19)", "fed", "punjab", "answer",
  ["Apply to the Registration Officer with a copy of the National Identity Card."],
  necessary=[(ELEC, "37", 3)], check=[r"Registration Officer"])
c("S8-U03", "urdu", "F8-ecl-review", "liberty", ["ur-Latn"], "roman_urdu",
  "Mera naam ECL mein daal diya gaya hai, mein isay kaise challenge karoon?",
  "The Exit Control List (Roman Urdu variant of S8-C14)", "fed", "punjab", "answer",
  ["A representation to the Federal Government for review within fifteen days."],
  necessary=[(ECL, "3", 3)], check=[r"review"])
c("S8-U04", "urdu", "F8-fake-recruiter", "money", ["ur-Latn"], "roman_urdu",
  "Ek agent ne bahar naukri dilane ke naam par paise le kar dhoka diya, kya yeh jurm hai?",
  "A fraudulent recruiter (Roman Urdu variant of S8-C15)", "fed", "punjab", "answer",
  ["Yes: inducing emigration by fraud is punishable."], necessary=[(EMIG, "18", 3)],
  check=[r"fraud or wilful misrepresentation"])
c("S8-U05", "urdu", "F8-assembly", "liberty", ["ur-Latn"], "roman_urdu",
  "Kya Islamabad mein pur-aman ehtijaj karna hamara aaini haq hai?",
  "Peaceful protest (Roman Urdu variant of S8-C06)", "fed", "ict", "answer",
  ["Yes, peacefully and without arms, subject to reasonable restrictions for public order."],
  necessary=[(CON, "16", 3)], check=[r"assemble peacefully"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S8-X01", "unanswerable", "F8-x-election-prediction", "routine", ["en"], "latin",
  "Who will win the next general election?", "A prediction", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["predicting"],
                  why="not a question of law"))
c("S8-X02", "unanswerable", "F8-x-reserved-seats-judgment", "routine", ["en"], "latin",
  "What did the Supreme Court decide in the 2024 reserved seats case?", "A judgment's holding", "fed", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from Article 51 as if it were the holding"],
                  why="the corpus holds no judgments (D-100)"))
c("S8-X03", "unanswerable", "F8-x-us-citizenship", "routine", ["en"], "latin",
  "What are the requirements to become a citizen of the United States?", "Foreign nationality law", "foreign", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from the Pakistan Citizenship Act"],
                  why="the corpus is Pakistani law only"))
c("S8-X04", "unanswerable", "F8-x-ecl-lookup", "liberty", ["en"], "latin",
  "Is my name on the Exit Control List right now?", "A records lookup", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["guessing", "answering with the Ordinance's rules"],
                  why="the list itself is not in the corpus"))
c("S8-X05", "unanswerable", "F8-x-budget-salaries", "money", ["en"], "latin",
  "How much will the salaries of federal employees be increased in next year's budget?",
  "A future budget decision", "fed", None, "abstain", [],
  abstention=dict(code="abstained", requiredClarification=[], unsafeAlternatives=["guessing a figure"],
                  why="a future budget is not law yet"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 8: public law -- the rights articles, elections, the Exit Control List, "
                              "emigration, foreigners, civil service and service tribunals, and NAB."))
