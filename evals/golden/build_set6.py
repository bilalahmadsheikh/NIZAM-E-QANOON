"""Build golden-pk-v1 draft SET 6 (50 cases): criminal law and procedure II.

Hurt (shajjah) and its punishments, qatl-i-khata and the value of diyat, kidnapping, extortion, criminal breach of
trust, forgery, criminal intimidation, trespass, rape and the victim's identity; narcotics, where Sindh's own Act
(2024) replaced the federal one for Sindh -- the federal s.9 is a trap for a Karachi question, and the right answer for
Islamabad; remand, confessions to a Magistrate and to the police, discovery, dying declarations, habeas corpus,
land disputes likely to breach the peace, security for the peace, acquittal at any stage, appeals, revision,
suspension of sentence, credit for detention, probation, and the steps of a complaint case.

PPC and the Qanun-e-Shahadat have Punjab copies (PROVINCIAL_COPY), so their cases are asked outside Punjab. Stage A0
+ A3 by the lead (claude), 20 Nov 2026; propositions written from the held text (peek.py) and re-verified by each
case's `check` regexes at every build. Not gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set6.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set6")
c = S.case
PPC, CRPC, QSO, CNSA_FED, CNSA_SD, PROB = 4441, 4501, 4166, 4036, 3880, 2563

# ---------------------------------------------------------------- citizen scenarios (20)
c("S6-C01", "citizen", "F6-shajjah", "liberty", ["en"], "latin",
  "In a fight in Hyderabad someone hit my brother on the head with a stick. The skin was cut but no bone showed. "
  "What offence is that and what is the punishment?", "Shajjah-i-khafifah and its punishment", "fed", "sindh",
  "answer",
  ["A head or face injury that does not expose bone is shajjah-i-khafifah; the offender is liable to daman and may "
   "also be imprisoned for up to two years as ta'zir."],
  necessary=[(PPC, "337", 3), (PPC, "337A", 3)], check=[r"shajjah-i-khafifah", r"two years as ta'zir"])
c("S6-C02", "citizen", "F6-qatl-khata", "liberty", ["en"], "latin",
  "While hunting near Kohat my friend fired at what he thought was a boar and killed a man. What is he guilty of?",
  "Qatl-i-khata and its punishment", "fed", "kp", "answer",
  ["Causing death without intending death or harm, by mistake of act or fact, is qatl-i-khata; the offender is "
   "liable to diyat and, if the act was rash or negligent (other than driving), up to five years' imprisonment as "
   "ta'zir."],
  necessary=[(PPC, "318", 3), (PPC, "319", 3)], check=[r"mistake of act or by mistake of fact", r"liable to diyat"])
c("S6-C03", "citizen", "F6-diyat-value", "money", ["en"], "latin",
  "The court in Quetta ordered diyat for my father's death. How is the amount fixed?", "The value of diyat",
  "fed", "balochistan", "answer",
  ["The court fixes diyat, considering the convict's and heirs' means, at not less than the value of 30,630 grams "
   "of silver, whose value the Federal Government notifies each July."],
  necessary=[(PPC, "323", 3)], check=[r"thirty thousand six hundred and thirty grams of silver"])
c("S6-C04", "citizen", "F6-kidnapping-guardianship", "liberty", ["en"], "latin",
  "A man took my 12-year-old daughter from outside her school in Islamabad without our consent. What offence is "
  "that?", "Kidnapping from lawful guardianship and its punishment", "fed", "ict", "answer",
  ["Kidnapping is from Pakistan or from lawful guardianship; whoever kidnaps a person from lawful guardianship may be "
   "imprisoned up to seven years and fined."],
  necessary=[(PPC, "363", 3)], relevant=[(PPC, "359", 2)], check=[r"lawful guardianship", r"seven years"])
c("S6-C05", "citizen", "F6-extortion", "money", ["en"], "latin",
  "A man in Karachi says he will hurt my son unless I pay him. What crime is that?", "Extortion and its punishment",
  "fed", "sindh", "answer",
  ["Putting a person in fear of injury to dishonestly induce delivery of property is extortion, punishable with up "
   "to three years' imprisonment, fine, or both."],
  necessary=[(PPC, "383", 3), (PPC, "384", 3)], check=[r"puts any person in fear", r"three years"])
c("S6-C06", "citizen", "F6-breach-of-trust", "money", ["en"], "latin",
  "I gave a dealer in Peshawar money to buy goods for me and he spent it on himself. Is that a crime?",
  "Criminal breach of trust and its punishment", "fed", "kp", "answer",
  ["A person entrusted with property who dishonestly misappropriates or converts it commits criminal breach of "
   "trust, punishable with up to seven years, fine, or both."],
  necessary=[(PPC, "405", 3), (PPC, "406", 3)], check=[r"entrusted with property", r"seven"])
c("S6-C07", "citizen", "F6-forgery", "property", ["en"], "latin",
  "Someone forged my signature on a sale deed for my plot in Karachi. What can he be punished with?",
  "Forgery and its punishment", "fed", "sindh", "answer",
  ["Making a false document with intent to cause damage, support a claim or title, or commit fraud is forgery, "
   "punishable with up to two years, fine, or both (more for forging valuable securities)."],
  necessary=[(PPC, "463", 3), (PPC, "465", 3)], check=[r"makes any false document", r"two years"])
c("S6-C08", "citizen", "F6-intimidation", "liberty", ["en"], "latin",
  "My neighbour in Islamabad has threatened to kill me. Is that an offence?",
  "Criminal intimidation; the aggravated form for a threat to kill", "fed", "ict", "answer",
  ["Criminal intimidation is punishable with up to two years; where the threat is to cause death or grievous hurt "
   "the punishment is higher (up to seven years)."],
  necessary=[(PPC, "506", 3)], check=[r"threat be to cause death", r"two years"])
c("S6-C09", "citizen", "F6-criminal-trespass", "property", ["en"], "latin",
  "A man keeps entering our courtyard in Turbat to harass my family. What offence is that?",
  "Criminal trespass and its punishment", "fed", "balochistan", "answer",
  ["Entering property in another's possession to intimidate, insult or annoy is criminal trespass, punishable with "
   "up to three months, a fine, or both."],
  necessary=[(PPC, "441", 3), (PPC, "447", 3)], check=[r"intimidate, insult or annoy", r"three months"])
c("S6-C10", "citizen", "F6-victim-identity", "liberty", ["en"], "latin",
  "A website in Karachi published the name of a rape victim. Is that allowed?",
  "Disclosing the identity of a rape victim is an offence", "fed", "sindh", "answer",
  ["Printing or publishing the name or anything making known the identity of the victim is punishable with up to "
   "three years and fine, save listed exceptions such as a written police order for investigation."],
  necessary=[(PPC, "376A", 3)], check=[r"identity of victim", r"three years"])
c("S6-C11", "citizen", "F6-narcotics-sindh", "liberty", ["en"], "latin",
  "Police in Karachi caught my son with half a kilo of bhang. What punishment does the law give?",
  "Punishment for possessing bhang under the Sindh Act", "sindh", "sindh", "answer",
  ["Under the Sindh Act, bhang up to 999 grams is punishable with six months to three years' imprisonment and a fine "
   "of up to fifty thousand rupees."],
  necessary=[(CNSA_SD, "9", 3)], relevant=[(CNSA_SD, "6", 2)], must_not_serve=[(CNSA_FED, "9")],
  check=[r"Fifty thousand rupees", r"six months"])
c("S6-C12", "citizen", "F6-vexatious-search-sindh", "liberty", ["en"], "latin",
  "Narcotics officers in Sukkur searched our house without any reason and took our things. Is there any remedy?",
  "Punishment for a vexatious entry, search, seizure or arrest", "sindh", "sindh", "answer",
  ["An empowered officer who enters or searches without reasonable grounds of suspicion, or vexatiously seizes "
   "property or detains a person, commits an offence under the Act."],
  necessary=[(CNSA_SD, "21", 3)], check=[r"without reasonable grounds of suspicion", r"vexatiously"])
c("S6-C13", "citizen", "F6-remand", "liberty", ["en"], "latin",
  "Police arrested my brother in Mardan. How long can the Magistrate let them keep him in custody?",
  "Remand under section 167 CrPC", "fed", "kp", "answer",
  ["If investigation cannot finish in twenty-four hours, the Magistrate may authorise detention for a term not "
   "exceeding fifteen days in the whole."],
  necessary=[(CRPC, "167", 3)], check=[r"twenty-four hours", r"fifteen days in the whole"])
c("S6-C14", "citizen", "F6-police-confession", "liberty", ["en"], "latin",
  "Police in Quetta beat my son until he confessed. Can that confession be used against him?",
  "Confessions to police are not proved", "fed", "balochistan", "answer",
  ["No confession made to a police officer may be proved against an accused, nor one made in police custody unless "
   "in a Magistrate's immediate presence; a confession caused by threat or inducement is irrelevant."],
  necessary=[(QSO, "38", 3)], relevant=[(QSO, "39", 3), (QSO, "37", 2)],
  check=[r"No confession made to a police-officer shall be proved"])
c("S6-C15", "citizen", "F6-discovery", "liberty", ["en"], "latin",
  "My son told the police in Karachi where a pistol was hidden and they found it. Can that be used in court?",
  "Information leading to discovery", "fed", "sindh", "answer",
  ["So much of an accused's information in police custody as relates distinctly to a fact discovered in consequence "
   "of it may be proved."],
  necessary=[(QSO, "40", 3)], check=[r"discovered in consequence of information"])
c("S6-C16", "citizen", "F6-dying-declaration", "liberty", ["en"], "latin",
  "Before he died my uncle told us who stabbed him. Does that count as evidence in Swat?",
  "Statement of a dead person about the cause of death", "fed", "kp", "answer",
  ["A statement by a person since dead is relevant when it relates to the cause of his death."],
  necessary=[(QSO, "46", 3)], check=[r"person who is dead", r"cause of death"])
c("S6-C17", "citizen", "F6-habeas-corpus", "liberty", ["en"], "latin",
  "My husband was picked up in Islamabad and has not been produced anywhere. Can a court order his release?",
  "High Court directions in the nature of habeas corpus", "fed", "ict", "answer",
  ["The High Court may direct that a person illegally or improperly detained in public or private custody within its "
   "limits be set at liberty, or be brought before it."],
  necessary=[(CRPC, "491", 3)], check=[r"illegally or improperly detained", r"set at liberty"])
c("S6-C18", "citizen", "F6-land-dispute-peace", "property", ["en"], "latin",
  "Our dispute with another family over a field boundary in Badin may turn violent. Can a Magistrate step in?",
  "Proceedings where a land dispute is likely to breach the peace", "fed", "sindh", "answer",
  ["A first-class Magistrate satisfied that a dispute over land, water or boundaries is likely to cause a breach of "
   "the peace may require the parties to state their claims and decide who is in possession, who keeps it until "
   "lawfully evicted."],
  necessary=[(CRPC, "145", 3)], check=[r"breach of the peace", r"land or water"])
c("S6-C19", "citizen", "F6-appeal-sessions", "liberty", ["en"], "latin",
  "My brother was convicted by the Sessions Judge in Abbottabad. Where can he appeal?",
  "Appeal from a Court of Session", "fed", "kp", "answer",
  ["A person convicted at a trial held by a Sessions Judge or Additional Sessions Judge may appeal to the High "
   "Court."],
  necessary=[(CRPC, "410", 3)], check=[r"may appeal to the High Court"])
c("S6-C20", "citizen", "F6-detention-credit", "liberty", ["en"], "latin",
  "My son spent a year in jail in Karachi before his trial ended. Will that year count in his sentence?",
  "Pre-sentence detention taken into account", "fed", "sindh", "answer",
  ["When passing a sentence of imprisonment the court shall take into consideration the period the accused was "
   "detained in custody for that offence."],
  necessary=[(CRPC, "382-B", 3)], check=[r"take into consideration the period"])

# ---------------------------------------------------------------- professional lookups (12)
c("S6-P01", "professional", "F6-confession-magistrate", "liberty", ["en"], "latin",
  "Who may record a confession during investigation?", "Section 164 CrPC", "fed", "ict", "answer",
  ["A first-class Magistrate, or a specially empowered second-class Magistrate, who is not a police officer, may "
   "record a statement or confession during investigation or before the inquiry or trial begins."],
  necessary=[(CRPC, "164", 3)], check=[r"record any statement or confession", r"not a police-officer"])
c("S6-P02", "professional", "F6-bail-hc-sessions", "liberty", ["en"], "latin",
  "Powers of the High Court and Court of Session to grant or reduce bail", "Section 498 CrPC", "fed", "kp",
  "answer",
  ["Bail bonds must not be excessive; the High Court or Court of Session may in any case direct admission to bail or "
   "reduce bail required by police or a Magistrate."],
  necessary=[(CRPC, "498", 3)], check=[r"shall not be excessive", r"Court of Session"])
c("S6-P03", "professional", "F6-police-report", "liberty", ["en"], "latin",
  "Report on completion of investigation", "Section 173 CrPC", "fed", "sindh", "answer",
  ["Investigation is completed without unnecessary delay and the officer in charge forwards a report, through the "
   "Public Prosecutor, to the Magistrate empowered to take cognizance."],
  necessary=[(CRPC, "173", 3)], check=[r"without unnecessary delay", r"Public Prosecutor"])
c("S6-P04", "professional", "F6-complainant-oath", "liberty", ["en"], "latin",
  "Examination of the complainant in a complaint case", "Section 200 CrPC", "fed", "balochistan", "answer",
  ["A Magistrate taking cognizance on a complaint examines the complainant on oath at once and the substance is "
   "reduced to writing and signed."],
  necessary=[(CRPC, "200", 3)], check=[r"examine the complainant upon oath"])
c("S6-P05", "professional", "F6-acquittal-249a", "liberty", ["en"], "latin",
  "Magistrate's power to acquit at any stage", "Section 249-A CrPC", "fed", "sindh", "answer",
  ["After hearing the prosecutor and accused, and for recorded reasons, a Magistrate may acquit at any stage if the "
   "charge is groundless or conviction improbable."],
  necessary=[(CRPC, "249A", 3)], check=[r"charge is groundless", r"no probability"])
c("S6-P06", "professional", "F6-acquittal-265k", "liberty", ["en"], "latin",
  "Court of Session's power to acquit at any stage", "Section 265-K CrPC", "fed", "kp", "answer",
  ["A Court may acquit at any stage, after hearing both sides and for recorded reasons, if there is no probability "
   "of conviction."],
  necessary=[(CRPC, "265K", 3)], check=[r"no probability of the accused being convicted"])
c("S6-P07", "professional", "F6-suspension-sentence", "liberty", ["en"], "latin",
  "Suspension of sentence and bail pending appeal", "Section 426 CrPC", "fed", "ict", "answer",
  ["Pending an appeal by a convicted person, the Appellate Court may for recorded reasons suspend the sentence and "
   "release the appellant on bail."],
  necessary=[(CRPC, "426", 3)], check=[r"execution of the sentence or order appealed against be suspended"])
c("S6-P08", "professional", "F6-probation-order", "liberty", ["en"], "latin",
  "When may a court make a probation order?", "Section 5 Probation of Offenders Ordinance, 1960", "fed", "sindh",
  "answer",
  ["A court convicting a male of an offence outside the listed grave offences and those punishable with death or "
   "life imprisonment, or a female of any offence not punishable with death, may make a probation order."],
  necessary=[(PROB, "5", 3)], check=[r"probation order", r"any female person"])
c("S6-P09", "professional", "F6-security-peace", "liberty", ["en"], "latin",
  "Security for keeping the peace", "Section 107 CrPC", "fed", "ict", "answer",
  ["A first-class Magistrate informed that a person is likely to commit a breach of the peace may require him to "
   "show cause why he should not execute a bond for keeping the peace."],
  necessary=[(CRPC, "107", 3)], check=[r"breach of the peace", r"public tranquillity"])
c("S6-P10", "professional", "F6-rape-punishment", "liberty", ["en"], "latin",
  "Punishment for rape", "Section 376 Pakistan Penal Code", "fed", "sindh", "answer",
  ["Rape is punishable with death or imprisonment of not less than ten nor more than twenty-five years (or for the "
   "rest of the offender's natural life) and fine."],
  necessary=[(PPC, "376", 3)], check=[r"not be less than ten years or more than twenty-five years"])
c("S6-P11", "professional", "F6-confession-inducement", "liberty", ["en"], "latin",
  "Confession caused by inducement, threat or promise", "Article 37 Qanun-e-Shahadat", "fed", "kp", "answer",
  ["A confession is irrelevant in a criminal proceeding if caused by an inducement, threat or promise about the "
   "charge from a person in authority."],
  necessary=[(QSO, "37", 3)], check=[r"inducement, threat or promise", r"person in authority"])
c("S6-P12", "professional", "F6-narcotics-federal", "liberty", ["en"], "latin",
  "Punishment for possessing up to 999 grams of bhang in Islamabad", "Section 9 Control of Narcotic Substances "
  "Act, 1997", "fed", "ict", "answer",
  ["Under the federal Act, bhang up to 999 grams is punishable with six months to three years and a fine of up to "
   "ten thousand rupees."],
  necessary=[(CNSA_FED, "9", 3)], check=[r"ten thousand rupees", r"six months"])

# ---------------------------------------------------------------- procedural (8)
c("S6-R01", "procedural", "F6-non-cognizable", "liberty", ["en"], "latin",
  "I reported a minor offence at a police station in Karachi and they told me to go to the Magistrate. Is that "
  "right?", "Information in non-cognizable cases", "fed", "sindh", "answer",
  ["For a non-cognizable offence the officer enters the substance of the information and refers the informant to "
   "the Magistrate; police may not investigate it without a Magistrate's order."],
  necessary=[(CRPC, "155", 3)], check=[r"refer the informant to the Magistrate"])
c("S6-R02", "procedural", "F6-search-witnesses", "liberty", ["en"], "latin",
  "Police want to search my house in Charsadda. What must they do first?", "Search in the presence of witnesses",
  "fed", "kp", "answer",
  ["Before searching, the officer must call two or more respectable inhabitants of the locality to attend and "
   "witness the search, which is made in their presence."],
  necessary=[(CRPC, "103", 3)], check=[r"two or more respectable inhabitants"])
c("S6-R03", "procedural", "F6-inquiry-before-process", "liberty", ["en"], "latin",
  "I filed a private criminal complaint in Islamabad. Can the court look into it before summoning the accused?",
  "Postponement of issue of process", "fed", "ict", "answer",
  ["The court may, for recorded reasons, postpone issuing process and inquire into the case itself or direct an "
   "inquiry or investigation."],
  necessary=[(CRPC, "202", 3)], check=[r"postpone the issue of process"])
c("S6-R04", "procedural", "F6-issue-process", "liberty", ["en"], "latin",
  "If the court in Quetta finds my complaint has substance, how is the accused brought to court?",
  "Issue of summons or warrant", "fed", "balochistan", "answer",
  ["Where there is sufficient ground, the court issues a summons or, where the second schedule says so, a warrant "
   "for the accused's attendance."],
  necessary=[(CRPC, "204", 3)], check=[r"sufficient ground for proceeding", r"summons"])
c("S6-R05", "procedural", "F6-appeal-acquittal", "liberty", ["en"], "latin",
  "The man accused in my complaint case in Hyderabad was acquitted. Can I appeal?", "Appeal against acquittal",
  "fed", "sindh", "answer",
  ["The Government may direct the Public Prosecutor to appeal to the High Court; in a case instituted on complaint "
   "the complainant may appeal if the High Court grants special leave."],
  necessary=[(CRPC, "417", 3)], check=[r"special leave to appeal", r"Public Prosecutor"])
c("S6-R06", "procedural", "F6-revision-hc", "liberty", ["en"], "latin",
  "Can the Peshawar High Court revise an order passed in my criminal case?", "High Court's powers of revision",
  "fed", "kp", "answer",
  ["In revision the High Court may exercise an appellate court's powers and may enhance the sentence."],
  necessary=[(CRPC, "439", 3)], check=[r"may enhance the sentence"])
c("S6-R07", "procedural", "F6-court-witness", "liberty", ["en"], "latin",
  "Can the trial court in Islamabad call a witness that neither side has called?",
  "Power to summon a material witness", "fed", "ict", "answer",
  ["Any court may at any stage summon or recall a witness, and must do so if the evidence appears essential to the "
   "just decision of the case."],
  necessary=[(CRPC, "540", 3)], check=[r"essential to the just decision"])
c("S6-R08", "procedural", "F6-examination-accused", "liberty", ["en"], "latin",
  "In my trial in Karachi, when will the judge question me himself?", "Examination of the accused",
  "fed", "sindh", "answer",
  ["The court may question the accused at any stage, and shall question him generally after the prosecution "
   "witnesses are examined and before he is called on for his defence."],
  necessary=[(CRPC, "342", 3)], check=[r"after the witnesses for the prosecution have been examined"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5)
c("S6-U01", "urdu", "F6-remand", "liberty", ["ur-Latn"], "roman_urdu",
  "Police ne mere bhai ko Mardan mein pakra hai, magistrate kitne din tak police hirasat ki ijazat de sakta hai?",
  "Remand (Roman Urdu variant of S6-C13)", "fed", "kp", "answer",
  ["Not more than fifteen days in the whole."], necessary=[(CRPC, "167", 3)], check=[r"fifteen days in the whole"])
c("S6-U02", "urdu", "F6-police-confession", "liberty", ["ur"], "arabic",
  "کیا پولیس کے سامنے کیا گیا اقبالِ جرم عدالت میں ملزم کے خلاف ثابت کیا جا سکتا ہے؟",
  "A confession to police (Urdu variant of S6-C14)", "fed", "balochistan", "answer",
  ["No: a confession to a police officer may not be proved against the accused."],
  necessary=[(QSO, "38", 3)], check=[r"No confession made to a police-officer"])
c("S6-U03", "urdu", "F6-narcotics-sindh", "liberty", ["ur-Latn"], "roman_urdu",
  "Karachi mein police ne mere bete se aadha kilo bhang pakri hai, kya saza ho sakti hai?",
  "Bhang possession in Sindh (Roman Urdu variant of S6-C11)", "sindh", "sindh", "answer",
  ["Six months to three years and a fine of up to fifty thousand rupees under the Sindh Act."],
  necessary=[(CNSA_SD, "9", 3)], must_not_serve=[(CNSA_FED, "9")], check=[r"Fifty thousand rupees"])
c("S6-U04", "urdu", "F6-intimidation", "liberty", ["ur-Latn"], "roman_urdu",
  "Islamabad mein hamsaye ne mujhe jaan se marne ki dhamki di hai, kya yeh jurm hai?",
  "A threat to kill (Roman Urdu variant of S6-C08)", "fed", "ict", "answer",
  ["Yes: criminal intimidation, punished more heavily where the threat is to cause death."],
  necessary=[(PPC, "506", 3)], check=[r"threat be to cause death"])
c("S6-U05", "urdu", "F6-forgery", "property", ["ur-Latn"], "roman_urdu",
  "Kisi ne Karachi mein mere jaali dastakhat kar ke plot ki registry bana li, uski kya saza hai?",
  "Forgery (Roman Urdu variant of S6-C07)", "fed", "sindh", "answer",
  ["Forgery is punishable with up to two years, fine, or both."],
  necessary=[(PPC, "465", 3)], relevant=[(PPC, "463", 3)], check=[r"two years"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S6-X01", "unanswerable", "F6-x-fir-statistics", "routine", ["en"], "latin",
  "How many FIRs were registered in Lahore last month?", "Crime statistics", "punjab", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["inventing a figure", "answering with s.154 CrPC instead"],
                  why="police statistics are not in the statutory corpus"))
c("S6-X02", "unanswerable", "F6-x-hc-judgment", "liberty", ["en"], "latin",
  "What did the Lahore High Court rule in the Model Town inquiry case?", "A judgment's holding", "punjab", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["summarising from memory"], why="the corpus holds no judgments (D-100)"))
c("S6-X03", "unanswerable", "F6-x-foreign-narcotics", "liberty", ["en"], "latin",
  "What is the punishment for drug possession in Saudi Arabia?", "Foreign criminal law", "foreign", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["quoting Pakistan's CNSA as if it applied there"],
                  why="the corpus is Pakistani law only"))
c("S6-X04", "unanswerable", "F6-x-bail-prediction", "liberty", ["en"], "latin",
  "Will my brother's bail application in Karachi be accepted tomorrow?", "A prediction of a court's decision",
  "fed", None, "abstain", [],
  abstention=dict(code="professional_review_required", requiredClarification=["the facts", "the charge"],
                  unsafeAlternatives=["predicting the outcome"],
                  why="predicting a court's decision on particular facts is legal advice"))
c("S6-X05", "unanswerable", "F6-x-future-punishment", "liberty", ["en"], "latin",
  "What will the punishment for theft be after next year's criminal law reforms?", "The law at a future date",
  "fed", None, "abstain", [],
  abstention=dict(code="abstained", requiredClarification=[],
                  unsafeAlternatives=["guessing at a future amendment", "answering with today's s.379 as the future law"],
                  why="the corpus holds the law in force up to today"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 6: criminal law and procedure II -- hurt, qatl-i-khata and diyat, kidnapping, "
                              "extortion, breach of trust, forgery, intimidation, trespass, narcotics by province, "
                              "remand, confessions, evidence, habeas corpus, appeals and the complaint case."))
