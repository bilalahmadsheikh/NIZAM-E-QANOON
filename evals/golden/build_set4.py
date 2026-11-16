"""Build golden-pk-v1 draft SET 4 (50 cases): work, money, business, rights and regulation — and subordinate law.

Labour (wages, maternity, child and domestic work, unions) across provinces, tax and company filings, intellectual
property, banking, ombudsmen, the Constitution's rights articles, and Rules (the West Pakistan Family Courts Rules,
the Punjab Transparency and RTI Rules, the Punjab Consumer Protection Rules, the ICT Consumers Protection Rules), so
retrieval is measured on subordinate legislation too (README: "widen into Rules").

Stage A0 + A3 by the lead (claude), 16 Nov 2026; propositions written from the held text (peek.py) and re-verified
by each case's `check` regexes at every build. Not gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set4.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set4")
c = S.case

# ---------------------------------------------------------------- citizen scenarios (20)
c("S4-C01", "citizen", "F4-minwage-punjab", "money", ["en"], "latin",
  "My employer in Faisalabad pays me less than the government minimum wage. Is that allowed?",
  "Prohibition on paying below the declared minimum wage in Punjab", "punjab", "punjab", "answer",
  ["No employer may pay any worker, including an unskilled worker, at a rate lower than the minimum rate declared "
   "under the Punjab Minimum Wages Act, 2019 (subject to authorised deductions)."],
  necessary=[(6194, "11", 3)], relevant=[(6194, "12", 2)], check=[r"rate lower than the rate declared"])
c("S4-C02", "citizen", "F4-wages-sindh", "money", ["en"], "latin",
  "I was fired from a factory in Karachi. By when must they pay my remaining salary?",
  "Payment of wages on termination in Sindh", "sindh", "sindh", "answer",
  ["Wages earned by a person whose employment is terminated must be paid before the expiry of the second working "
   "day after termination; ordinary wages are due within seven days of the wage period (ten in larger "
   "establishments)."],
  necessary=[(2503, "5", 3)], check=[r"second working day", r"seventh day"])
c("S4-C03", "citizen", "F4-maternity-punjab", "money", ["en"], "latin",
  "I work in a factory in Lahore and I'm pregnant. Am I entitled to paid maternity leave?",
  "Maternity benefit under the Punjab Maternity Benefit Ordinance, 1958", "punjab", "punjab", "conditional",
  ["A woman employed in an establishment is entitled to maternity benefit at her last-paid wage for six weeks "
   "before and including the day of delivery and six weeks after, provided she has worked there at least four "
   "months before delivery."],
  necessary=[(3755, "4", 3)], omitted=["length of employment"], check=[r"six weeks", r"four months"])
c("S4-C04", "citizen", "F4-maternity-sindh", "money", ["en"], "latin",
  "How much maternity leave must an employer in Sindh give?", "Mandatory maternity leave in Sindh", "sindh",
  "sindh", "answer",
  ["An employer must grant mandatory maternity leave of four weeks before the expected delivery date and twelve "
   "weeks after delivery."],
  necessary=[(1184, "3", 3)], relevant=[(1184, "4", 1)], check=[r"Four weeks", r"Twelve.weeks"])
c("S4-C05", "citizen", "F4-maternity-kp", "money", ["en"], "latin",
  "Is maternity pay a legal right for women workers in Peshawar?",
  "Maternity benefit under the KP Maternity Benefits Act, 2013", "kp", "kp", "conditional",
  ["Every woman employed in an establishment is entitled to maternity benefit at her last-paid wage for six weeks "
   "before and six weeks after delivery, subject to the minimum period of prior employment."],
  necessary=[(2201, "4", 3)], check=[r"six weeks"])
c("S4-C06", "citizen", "F4-maternity-federal", "money", ["en"], "latin",
  "I am a federal government employee in Islamabad expecting my first child. How much maternity leave do I get?",
  "Maternity leave under the Maternity and Paternity Leave Act, 2023", "fed", "ict", "answer",
  ["Maternity leave on full pay outside the leave account is 180 days on the first birth, 120 on the second and "
   "90 on the third."],
  necessary=[(3049, "3", 3)], check=[r"one hundred and eighty days", r"first birth"])
c("S4-C07", "citizen", "F4-maternity-dismissal-punjab", "money", ["en"], "latin",
  "Can my employer in Punjab dismiss me while I am on maternity leave?",
  "No notice of dismissal during maternity absence", "punjab", "punjab", "answer",
  ["While a woman is absent under the Ordinance her employer may not give her notice of dismissal during the "
   "absence or so that it expires during it; a dismissal without sufficient cause within six months before "
   "delivery does not deprive her of maternity benefit."],
  necessary=[(3755, "7", 3)], check=[r"notice of dismissal", r"six months before delivery"])
c("S4-C08", "citizen", "F4-childlabour-punjab", "liberty", ["en"], "latin",
  "A workshop in Gujranwala employs 12-year-old boys. Is that illegal?",
  "Prohibition on employing children in Punjab", "punjab", "punjab", "answer",
  ["An occupier may not employ or permit a child to work in an establishment, nor an adolescent to do hazardous "
   "work."],
  necessary=[(6235, "3", 3)], check=[r"shall not employ or permit a child", r"hazardous work"])
c("S4-C09", "citizen", "F4-domestic-wage-ict", "money", ["en"], "latin",
  "I work as a maid in Islamabad. Is my employer bound to pay me a minimum wage?",
  "Minimum wage for domestic workers in ICT", "fed", "ict", "answer",
  ["A domestic worker must be paid on a designated day for all hours worked, never less than the wages the "
   "Government specifies, and without less favourable pay than the opposite sex for equal work."],
  necessary=[(2977, "8", 3)], relevant=[(2977, "4", 1)], check=[r"less than the wages specified", r"opposite sex"])
c("S4-C10", "citizen", "F4-trade-union-ict", "money", ["en"], "latin",
  "Can workers at our company in Islamabad form a union without the management's permission?",
  "Freedom of association under the Industrial Relations Act, 2012", "fed", "ict", "answer",
  ["Workers, without distinction, have the right to establish and join associations of their own choice without "
   "previous authorisation, subject to the Act; where women are employed, the union's executive must include them "
   "proportionately."],
  necessary=[(3927, "3", 3)], check=[r"without previous authorization", r"women"])
c("S4-C11", "citizen", "F4-smoking-public", "routine", ["en"], "latin",
  "Is smoking allowed in government offices and public places in Islamabad?",
  "Prohibition of smoking in places of public work or use", "fed", "ict", "answer",
  ["No person may smoke or use tobacco in any form in a place of public work or use; the Federal Government may "
   "permit designated smoking areas with protection for non-smokers."],
  necessary=[(4162, "5", 3)], check=[r"place of public work or use"])
c("S4-C12", "citizen", "F4-arms-licence-punjab", "liberty", ["en"], "latin",
  "Can I keep a pistol at home in Lahore without a licence?", "Unlicensed possession of arms in Punjab",
  "punjab", "punjab", "answer",
  ["No person may possess or control any arms or ammunition except under a licence and as it permits; unlicensed "
   "possession is an offence under section 13."],
  necessary=[(3593, "9", 3)], relevant=[(3593, "13", 2)], check=[r"except under a licence"])
c("S4-C13", "citizen", "F4-copyright-term", "money", ["en"], "latin",
  "I wrote a novel. How long will my copyright last?", "Term of copyright in a published literary work", "fed",
  "sindh", "answer",
  ["Copyright in a literary work published in the author's lifetime lasts until fifty years from the beginning of "
   "the calendar year after the author's death."],
  necessary=[(3896, "18", 3)], check=[r"fifty years", r"author dies"])
c("S4-C14", "citizen", "F4-trademark-term", "money", ["en"], "latin",
  "I registered a trademark for my bakery. How long is it valid?", "Duration and renewal of trademark "
  "registration", "fed", "sindh", "answer",
  ["A trade mark is registered for ten years from the date of registration and may be renewed for further periods "
   "of ten years."],
  necessary=[(4338, "34", 3)], relevant=[(4338, "35", 1)], check=[r"ten years"])
c("S4-C15", "citizen", "F4-passport-impound", "liberty", ["en"], "latin",
  "The passport office wants to cancel my passport. Do they have to hear me first?",
  "Cancellation or impounding of a passport", "fed", "ict", "answer",
  ["A passport is Federal Government property and may be cancelled, impounded or confiscated by order; before "
   "such an order the holder must ordinarily be given written notice to show cause, subject to sub-section (3)."],
  necessary=[(2735, "8", 3)], check=[r"show cause", r"impounded"])
c("S4-C16", "citizen", "F4-dual-nationality", "routine", ["en"], "latin",
  "I am Pakistani and want to take British citizenship. Will I lose my Pakistani citizenship?",
  "Dual citizenship under the Pakistan Citizenship Act, 1951", "fed", "punjab", "conditional",
  ["A Pakistani citizen who is also a citizen of another country ceases to be a Pakistani citizen unless he "
   "renounces the other citizenship under that country's law, subject to the exceptions in section 14."],
  necessary=[(2168, "14", 3)], omitted=["whether the other country is covered by the section's exceptions"],
  check=[r"renouncing", r"cease to be a citizen"])
c("S4-C17", "citizen", "F4-tax-return", "money", ["en"], "latin",
  "I am salaried in Karachi. Do I have to file an income tax return?", "Who must furnish a return of income",
  "fed", "sindh", "conditional",
  ["A return is required from, among others, every company, every person whose taxable income exceeds the maximum "
   "amount not chargeable to tax, and persons charged to tax in either of the two preceding tax years, as section "
   "114 lists."],
  necessary=[(4489, "114", 3)], omitted=["taxable income for the year"],
  check=[r"every company", r"not chargeable to tax"])
c("S4-C18", "citizen", "F4-journalist-harassment", "privacy", ["en"], "latin",
  "I am a reporter in Islamabad being harassed over my stories. Where can I complain and by when?",
  "Harassment complaint under the Protection of Journalists and Media Professionals Act, 2021", "fed", "ict",
  "answer",
  ["A journalist or media professional who is harassed may complain to the Federal Ombudsman within fourteen days; "
   "the Ombudsman or relevant authority must act within fourteen days of receiving the information."],
  necessary=[(2855, "8", 3)], check=[r"fourteen \(14\) days", r"Federal Ombudsman"])
c("S4-C19", "citizen", "F4-small-claims", "money", ["en"], "latin",
  "Someone owes me fifty thousand rupees in Islamabad. Is there a small claims court?",
  "Jurisdiction of the Small Claims and Minor Offences Court", "fed", "ict", "answer",
  ["The Court has exclusive jurisdiction over the suits in Part I of the Schedule whose value does not exceed one "
   "hundred thousand rupees (variable by the High Court), and over the offences in Part II."],
  necessary=[(3200, "5", 3)], check=[r"one hundred thousand rupees", r"exclusive jurisdiction"])
c("S4-C20", "citizen", "F4-refund-ict-rules", "money", ["en"], "latin",
  "A shop in Islamabad refuses to take back an unused item I bought yesterday. What do the rules say?",
  "Return and refund policy under the ICT (Consumers Protection) Rules, 2011", "fed", "ict", "conditional",
  ["A seller must disclose its return and refund policy before the sale and print it on the receipt, and must take "
   "back an item not changed, altered or damaged by the buyer on proof of purchase within the warranty period or a "
   "reasonable time."],
  necessary=[(8766, "10", 3)], check=[r"return and refund policy", r"proof of purchase"])

# ---------------------------------------------------------------- professional lookups (12)
c("S4-P01", "professional", "F4-company-return-date", "deadline", ["en"], "latin",
  "Due date for a company's income tax return", "Section 118 Income Tax Ordinance, 2001", "fed", "punjab",
  "answer",
  ["A company whose tax year ends between 1 January and 30 June files by 31 December following; otherwise by 30 "
   "September following the end of the tax year."],
  necessary=[(4489, "118", 3)], check=[r"thirty-first day of December", r"thirtieth day of September"])
c("S4-P02", "professional", "F4-company-incorporation", "money", ["en"], "latin",
  "What must be filed to incorporate a company?", "Section 16 Companies Act, 2017", "fed", "sindh", "answer",
  ["An application on the specified form is filed with the registrar with a declaration of compliance and the "
   "memorandum of association signed by all subscribers, among the other documents section 16 lists."],
  necessary=[(4486, "16", 3)], check=[r"memorandum of association", r"registrar"])
c("S4-P03", "professional", "F4-trademark-forum", "money", ["en"], "latin",
  "Forum for a trademark infringement suit", "Section 117 Trade Marks Ordinance, 2001", "fed", "punjab", "answer",
  ["No suit for infringement of a trade mark, or otherwise relating to a right in it, may be instituted in any "
   "court except an IP Tribunal having jurisdiction."],
  necessary=[(4338, "117", 3)], check=[r"IP Tribunal"])
c("S4-P04", "professional", "F4-ni-presumptions", "money", ["en"], "latin",
  "Presumptions as to negotiable instruments", "Section 118 Negotiable Instruments Act, 1881", "fed", "kp",
  "answer", ["Until the contrary is proved, a negotiable instrument is presumed to have been made for "
             "consideration and on its date, among the other presumptions section 118 lists."],
  necessary=[(4192, "118", 3)], check=[r"made or drawn for consideration"])
c("S4-P05", "professional", "F4-banking-court", "money", ["en"], "latin",
  "How does a bank sue a defaulting customer for recovery of finance?", "Section 9 Financial Institutions "
  "(Recovery of Finances) Ordinance, 2001", "fed", "sindh", "answer",
  ["On a default, the financial institution (or the customer) institutes a suit in the Banking Court by a plaint "
   "verified on oath and supported by a certified statement of account."],
  necessary=[(2176, "9", 3)], check=[r"Banking Court", r"verified on oath", r"statement of account"])
c("S4-P06", "professional", "F4-wafaqi-mohtasib", "routine", ["en"], "latin",
  "Jurisdiction of the Wafaqi Mohtasib", "Article 9 Wafaqi Mohtasib (Ombudsman) Order, 1983", "fed", "ict",
  "answer", ["The Mohtasib investigates allegations of maladministration by an Agency or its officers on a "
             "complaint, a reference or his own motion, but has no jurisdiction over matters sub judice before a "
             "court or tribunal, among the stated exclusions."],
  necessary=[(3477, "9", 3)], check=[r"maladministration", r"sub judice"])
c("S4-P07", "professional", "F4-adr-pre-suit", "money", ["en"], "latin",
  "Reference to ADR before legal proceedings — ICT", "Section 8 Alternative Dispute Resolution Act, 2017", "fed",
  "ict", "answer",
  ["If the parties agree on ADR before going to court, they may apply to the Court or an ADR Centre, which refers "
   "the matter to a Neutral or other agreed person."],
  necessary=[(2632, "8", 3)], check=[r"ADR Centre", r"Neutral"])
c("S4-P08", "professional", "F4-mental-health-admission", "liberty", ["en"], "latin",
  "Grounds for admitting a patient to a psychiatric facility for assessment", "Section 10 Mental Health "
  "Ordinance, 2001", "fed", "ict", "answer",
  ["A patient may be admitted and detained for assessment on an application showing mental disorder warranting "
   "detention for at least a limited period, in the interests of his health or safety or to protect others."],
  necessary=[(4257, "10", 3)], check=[r"admission for assessment", r"mental disorder"])
c("S4-P09", "professional", "F4-lease-definition", "property", ["en"], "latin",
  "Definition of a lease of immovable property", "Section 105 Transfer of Property Act", "fed", "sindh", "answer",
  ["A lease is a transfer of a right to enjoy immovable property for a certain time, express or implied, or in "
   "perpetuity, in consideration of a price paid or promised or of money, crops, service or other value rendered "
   "periodically."],
  necessary=[(3991, "105", 3)], check=[r"transfer of a right to enjoy"])
c("S4-P10", "professional", "F4-art19a", "routine", ["en"], "latin",
  "Constitutional right to information", "Article 19A", "fed", "punjab", "answer",
  ["Every citizen has the right of access to information in all matters of public importance, subject to "
   "regulation and reasonable restrictions imposed by law."],
  necessary=[(4419, "19A", 3)], relevant=[(6185, "10", 1)], check=[r"matters of public importance"])
c("S4-P11", "professional", "F4-art25", "routine", ["en"], "latin",
  "Equality before law and the bar on sex discrimination", "Article 25", "fed", "sindh", "answer",
  ["All citizens are equal before law and entitled to equal protection; there is no discrimination on the basis "
   "of sex, but the State may make special provision for women and children."],
  necessary=[(4419, "25", 3)], check=[r"equal before law", r"discrimination on the basis of sex"])
c("S4-P12", "professional", "F4-land-acq-notification", "property", ["en"], "latin",
  "First step in compulsory acquisition of land", "Section 4 Land Acquisition Act, 1894", "fed", "sindh",
  "answer", ["When land is needed for a public purpose or a company, a notification is published in the official "
             "Gazette and public notice of its substance is given in the locality; authorised officers may then "
             "enter and survey."],
  necessary=[(4099, "4", 3)], check=[r"public purpose", r"official Gazette"])

# ---------------------------------------------------------------- procedural (8)
c("S4-R01", "procedural", "F4-family-court-venue", "family", ["en"], "latin",
  "I live with my parents in Swat but married in Peshawar. Where can I file for dissolution of marriage?",
  "Territorial jurisdiction of Family Courts (West Pakistan Family Courts Rules, 1965, KP text)", "kp", "kp",
  "answer",
  ["A suit lies where the cause of action arose or where the parties reside or last resided together; in a suit "
   "for dissolution of marriage or dower, the court where the wife ordinarily resides also has jurisdiction."],
  necessary=[(4727, "6", 3)], check=[r"wife ordinarily resides", r"cause of action"])
c("S4-R02", "procedural", "F4-rti-rules-electronic", "routine", ["en"], "latin",
  "Can I send my information request to a Punjab public body by email?",
  "Mode of application under the Punjab Transparency and RTI Rules, 2014", "punjab", "punjab", "answer",
  ["Yes, where the public body has the facility: a citizen or legal person may apply on plain paper or the sample "
   "form, and may also apply by email, web portal or other electronic system the body has set up."],
  necessary=[(1714, "5", 3)], check=[r"email", r"plain paper"])
c("S4-R03", "procedural", "F4-consumer-authority-punjab", "money", ["en"], "latin",
  "A shop in Lahore is breaking consumer law. Can I complain to the Consumer Protection Authority rather than sue?",
  "Complaint to the Authority under the Punjab Consumer Protection Rules, 2009", "punjab", "punjab", "answer",
  ["A person may complain to the Authority of violations of sections 11, 16, 18 and 19 of the Act; the Authority "
   "inquires, and if satisfied issues notice and hears the defendant before passing an order."],
  necessary=[(2802, "3", 3)], check=[r"complaint to the Authority", r"11, 16, 18 and 19"])
c("S4-R04", "procedural", "F4-minwage-claim-punjab", "money", ["en"], "latin",
  "I was paid below minimum wage in Punjab. Who hears my claim and who can file it for me?",
  "Claims for under-payment of minimum wages in Punjab", "punjab", "punjab", "answer",
  ["The Authority hears and decides claims for wages paid below the minimum; the worker may apply himself or "
   "through another person, a legal practitioner or an authorised office bearer of a registered trade union."],
  necessary=[(6194, "12", 3)], check=[r"Authority shall hear", r"registered trade union"])
c("S4-R05", "procedural", "F4-copyright-registration", "money", ["en"], "latin",
  "How do I register the copyright in my song?", "Registration of copyright", "fed", "sindh", "answer",
  ["The author, publisher, owner or other interested person applies in the prescribed form with the fee to the "
   "Registrar, who enters the work in the Register of Copyrights and issues a certificate unless he records "
   "reasons for refusing."],
  necessary=[(3896, "39", 3)], check=[r"Register of Copyrights", r"certificate"])
c("S4-R06", "procedural", "F4-trademark-application", "money", ["en"], "latin",
  "What goes into a trademark application?", "Application for registration of a trade mark", "fed", "sindh",
  "answer", ["The application is made in writing to the Registrar and contains a request for registration, the "
             "applicant's name and address, the goods or services and their classification, a representation of "
             "the mark, and the agent's details if filed through one."],
  necessary=[(4338, "22", 3)], check=[r"in writing to the Registrar", r"representation of the trade mark"])
c("S4-R07", "procedural", "F4-partition-punjab", "property", ["en"], "latin",
  "My siblings and I co-own a house in Lahore and cannot agree. How long will a partition suit take?",
  "Time limit and internal auction under the Punjab Partition of Immovable Property Act, 2012", "punjab",
  "punjab", "answer",
  ["The Court must finally dispose of the suit within six months of institution, or seek an extension from the "
   "District Judge; where the property is not partible the Court fixes a reserve price and orders an internal "
   "auction among the co-owners."],
  necessary=[(6137, "14", 3), (6137, "10", 2)], check=[r"six months", r"internal auction"])
c("S4-R08", "procedural", "F4-consumer-notice-punjab", "money", ["en"], "latin",
  "Before I go to the consumer court in Lahore about a faulty service, what do I have to do first?",
  "Prior notice under the Punjab Consumer Protection Act, 2005", "punjab", "punjab", "answer",
  ["The consumer must first give written notice calling on the manufacturer or service provider to remedy the "
   "defect or pay damages; it must reply within fifteen days, and no claim is entertained without that notice."],
  necessary=[(6267, "28", 3)], check=[r"written notice", r"fifteen days", r"No claim shall be entertained"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5), each in its family
c("S4-U01", "urdu", "F4-maternity-punjab", "money", ["ur-Latn"], "roman_urdu",
  "Punjab mein factory mein kaam karne wali aurat ko maternity benefit kitne hafton ka milta hai?",
  "Maternity benefit in Punjab (Roman Urdu variant of S4-C03)", "punjab", "punjab", "conditional",
  ["Six weeks before and six weeks after delivery, after four months' employment."],
  necessary=[(3755, "4", 3)], check=[r"six weeks"])
c("S4-U02", "urdu", "F4-tax-return", "money", ["ur"], "arabic",
  "کیا مجھے انکم ٹیکس ریٹرن جمع کروانا ضروری ہے؟",
  "Who must file a return (Urdu variant of S4-C17)", "fed", "punjab", "conditional",
  ["Section 114 lists who must file, including every person whose taxable income exceeds the untaxed maximum."],
  necessary=[(4489, "114", 3)], check=[r"not chargeable to tax"])
c("S4-U03", "urdu", "F4-childlabour-punjab", "liberty", ["ur-Latn"], "roman_urdu",
  "Kya Punjab mein bachon se workshop mein kaam karwana jurm hai?",
  "Child labour in Punjab (Roman Urdu variant of S4-C08)", "punjab", "punjab", "answer",
  ["An occupier may not employ or permit a child to work in an establishment."],
  necessary=[(6235, "3", 3)], check=[r"shall not employ or permit a child"])
c("S4-U04", "urdu", "F4-wages-sindh", "money", ["ur"], "arabic",
  "سندھ میں نوکری ختم ہونے کے بعد بقایا تنخواہ کب تک ملنی چاہیے؟",
  "Wages on termination in Sindh (Urdu variant of S4-C02)", "sindh", "sindh", "answer",
  ["Before the end of the second working day after termination."], necessary=[(2503, "5", 3)],
  check=[r"second working day"])
c("S4-U05", "urdu", "F4-trademark-term", "money", ["ur-Latn"], "roman_urdu",
  "Trademark kitne saal ke liye register hota hai?", "Trademark term (Roman Urdu variant of S4-C14)", "fed",
  "sindh", "answer", ["Ten years, renewable for further ten-year periods."], necessary=[(4338, "34", 3)],
  check=[r"ten years"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S4-X01", "unanswerable", "F4-x-live-rate", "money", ["en"], "latin",
  "What is today's US dollar to rupee exchange rate?", "Live market data", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["guessing a rate"],
                  why="a market rate is not law and is not in the corpus"))
c("S4-X02", "unanswerable", "F4-x-recommend", "money", ["en"], "latin",
  "Which tax consultant in Lahore should I hire?", "A recommendation of a person", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["naming practitioners"], why="not a question of law"))
c("S4-X03", "unanswerable", "F4-x-ombudsman-decision", "money", ["en"], "latin",
  "What did the Federal Tax Ombudsman decide in complaint No. 1234/LHR/IT/2024?",
  "A specific adjudicative decision", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["describing the Ombudsman's powers instead", "inventing an outcome"],
                  why="the corpus holds statutes, not ombudsman or court decisions"),
  negatives=[(4067, "9", 0)])
c("S4-X04", "unanswerable", "F4-x-foreign-labour", "money", ["en"], "latin",
  "What are the labour laws in Saudi Arabia for Pakistani workers there?", "Foreign labour law", "foreign", None,
  "abstain", [], abstention=dict(code="unsupported_scope", requiredClarification=[],
                                 unsafeAlternatives=["answering from the Emigration Ordinance as if it governed "
                                                     "Saudi employment"],
                                 why="the corpus is Pakistani law only"))
c("S4-X05", "unanswerable", "F4-x-guarantee", "money", ["en"], "latin",
  "If I file my company's return a month late, can you guarantee I won't be penalised?",
  "A guarantee about an enforcement outcome", "fed", None, "abstain", [],
  abstention=dict(code="professional_review_required", requiredClarification=["facts", "notices received"],
                  unsafeAlternatives=["promising no penalty"],
                  why="predicting or guaranteeing an enforcement outcome is legal advice"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 4: work, money, business, rights and regulation — labour across provinces, tax "
                              "and company filings, IP, banking, ombudsmen, constitutional rights, and Rules."))
