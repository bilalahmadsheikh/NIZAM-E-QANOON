"""Build golden-pk-v1 draft SET 10 (50 cases): welfare and regulation, by place, and Gilgit-Baltistan.

Environmental approval, emissions, protection orders, penalties and tribunals under each place's own Act (the federal
Act for Islamabad; Punjab's 1997 adaptation; Sindh, KP and Balochistan's own Acts -- the federal Act was repealed for
KP in 2014, D-103, so its penalty section is a trap for a KP question); KP's plastic bag ban; the rights of persons
with disabilities in Islamabad, Punjab and Balochistan (employment, quota, education, access, justice, fines and
appeals); medical negligence, complaints, fines and appeals before the Punjab, Sindh and KP healthcare commissions;
food business licensing, penalties and appeals in Punjab and KP; and Gilgit-Baltistan's own Acts on child marriage,
corporal punishment, information about tenants and guests, sound systems and pre-emption.

Left out: the Transgender Persons (Protection of Rights) Act, 2018 (parts declared repugnant by the Federal Shariat
Court, with the appeal's status not verified); Sindh's disability Act (its held text is mis-segmented); GB's
pre-emption sections after s.6 (labels shifted). Stage A0 + A3 by the lead (claude), 20 Nov 2026; propositions
written from the held text (peek.py) and re-verified by each case's `check` regexes at every build. Not gold until
A1/A2 (evals/golden/README.md).

    python evals/golden/build_set10.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set10")
c = S.case
EPA_FED, EPA_PB, EPA_SD, EPA_KP, EPA_BL = 4350, 6469, 2897, 4394, 1989
DIS_ICT, DIS_PB, DIS_BL = 3119, 3608, 981
HCC_PB, HCC_SD, HCC_KP = 6418, 1858, 3131
FOOD_PB, FOOD_KP = 6381, 3430
GB_CMR, GB_CORP, GB_TENANT, GB_SOUND, GB_PREEMPT = 11359, 11373, 11374, 11369, 11377

# ---------------------------------------------------------------- citizen scenarios (20)
c("S10-C01", "citizen", "F10-eia-punjab", "routine", ["en"], "latin",
  "A company has started building a factory next to our village in Sheikhupura. Did it need environmental "
  "approval first?", "Environmental approval before construction in Punjab", "punjab", "punjab", "answer",
  ["No proponent may begin construction or operation without filing an initial environmental examination (or an "
   "environmental impact assessment where adverse effects are likely) with the Provincial Agency and obtaining its "
   "approval."],
  necessary=[(EPA_PB, "12", 3)], check=[r"initial environmental examination", r"Provincial Agency"])
c("S10-C02", "citizen", "F10-eia-sindh", "routine", ["en"], "latin",
  "A builder in Karachi started a high-rise without any environmental clearance. Is that allowed?",
  "Environmental approval before construction in Sindh", "sindh", "sindh", "answer",
  ["No proponent may begin construction or operation without filing an IEE or EIA with the Agency and obtaining its "
   "approval."],
  necessary=[(EPA_SD, "17", 3)], check=[r"obtained from the Agency approval"])
c("S10-C03", "citizen", "F10-plastic-ban-kp", "routine", ["en"], "latin",
  "Shops in Peshawar still hand out plastic bags. Are plastic bags banned?", "KP's ban on plastic products", "kp",
  "kp", "answer",
  ["There is a complete ban on manufacturing, importing, selling, storing, distributing and using plastic bags and "
   "other notified plastic products in KP."],
  necessary=[(EPA_KP, "7B", 3)], check=[r"complete ban", r"plastic bags"])
c("S10-C04", "citizen", "F10-eia-balochistan", "routine", ["en"], "latin",
  "A mining company has begun work near Quetta. Must it have an environmental approval?",
  "Environmental approval before construction in Balochistan", "balochistan", "balochistan", "answer",
  ["No public or private project may begin construction or operation without filing an IEE (or an EIA where "
   "adverse effects are likely) and obtaining approval."],
  necessary=[(EPA_BL, "15", 3)], check=[r"Initial Environmental Examination"])
c("S10-C05", "citizen", "F10-eia-ict", "routine", ["en"], "latin",
  "A housing project in Islamabad began without an environmental study. Which agency should have approved it?",
  "Environmental approval in Islamabad under the federal Act", "fed", "ict", "answer",
  ["The proponent must file an IEE or EIA with the Federal Agency and obtain its approval before construction or "
   "operation."],
  necessary=[(EPA_FED, "12", 3)], check=[r"Federal Agency"])
c("S10-C06", "citizen", "F10-vehicle-emissions-punjab", "routine", ["en"], "latin",
  "Buses in Lahore blow out thick black smoke. Is that against the law?", "Regulation of motor vehicle emissions",
  "punjab", "punjab", "answer",
  ["No one may operate a motor vehicle emitting air pollutants or noise above the Punjab Environmental Quality "
   "Standards."],
  necessary=[(EPA_PB, "15", 3)], check=[r"air pollutants or noise"])
c("S10-C07", "citizen", "F10-protection-order-sindh", "routine", ["en"], "latin",
  "A factory in Korangi is dumping waste into the drain by our homes. Can the environmental agency stop it?",
  "Environmental Protection Order in Sindh", "sindh", "sindh", "answer",
  ["Where a discharge or disposal violates the Act or causes an adverse environmental effect, the Agency may, after "
   "hearing the person, issue an Environmental Protection Order."],
  necessary=[(EPA_SD, "21", 3)], check=[r"adverse environmental effect"])
c("S10-C08", "citizen", "F10-disability-employment-ict", "routine", ["en"], "latin",
  "A company in Islamabad refused me a job because I use a wheelchair. Is that lawful?",
  "No discrimination in employment on the ground of disability", "fed", "ict", "answer",
  ["No public or private employer may discriminate on the ground of disability in employment or promotion, and "
   "employers must provide reasonable accommodation."],
  necessary=[(DIS_ICT, "10", 3)], check=[r"discriminate against a person on the ground of disability",
                                         r"reasonable accommodation"])
c("S10-C09", "citizen", "F10-disability-quota-balochistan", "routine", ["en"], "latin",
  "Is there a job quota for persons with disabilities in Balochistan?", "The employment quota in Balochistan",
  "balochistan", "balochistan", "answer",
  ["The government must reserve a quota of five percent at various levels for persons with disabilities."],
  necessary=[(DIS_BL, "10", 3)], check=[r"five percent"])
c("S10-C10", "citizen", "F10-disability-admission-punjab", "routine", ["en"], "latin",
  "A school in Multan refused to admit my deaf daughter. Can it?", "No denial of admission on account of disability",
  "punjab", "punjab", "answer",
  ["No qualified person with disabilities may be denied admission to an educational institution because of the "
   "disability."],
  necessary=[(DIS_PB, "8", 3)], check=[r"denied admission"])
c("S10-C11", "citizen", "F10-disability-free-education-ict", "routine", ["en"], "latin",
  "My son in Islamabad has a disability. Is he entitled to free education?", "Free education for persons with "
  "disabilities in ICT", "fed", "ict", "answer",
  ["The government must provide free pre-primary to higher education to persons with disabilities and ensure equal "
   "access to institutions."],
  necessary=[(DIS_ICT, "9", 3)], check=[r"free pre-primary to higher education"])
c("S10-C12", "citizen", "F10-disability-access-ict", "routine", ["en"], "latin",
  "The government office in Islamabad has no ramp and I cannot get in. Is it obliged to fix that?",
  "Ease of access to public buildings", "fed", "ict", "answer",
  ["The government and private sector must make public buildings, hospitals, transport, streets and roads "
   "accessible, modifying old buildings and building new ones to standard."],
  necessary=[(DIS_ICT, "7", 3)], check=[r"ease of access", r"public buildings"])
c("S10-C13", "citizen", "F10-medical-negligence-punjab", "routine", ["en"], "latin",
  "My mother was harmed by careless treatment at a private hospital in Lahore. When is that medical negligence "
  "in law?", "Medical negligence before the Punjab Healthcare Commission", "punjab", "punjab", "answer",
  ["A provider may be held negligent if the establishment lacks the staff and equipment it professes to have, or "
   "the skill it possesses was not exercised with reasonable competence; known complications are not negligence."],
  necessary=[(HCC_PB, "19", 3)], check=[r"reasonable competence", r"known complications"])
c("S10-C14", "citizen", "F10-medical-negligence-sindh", "routine", ["en"], "latin",
  "A clinic in Karachi botched my surgery. Can the Healthcare Commission act?", "Medical negligence in Sindh",
  "sindh", "sindh", "answer",
  ["A provider may be held guilty of medical negligence if it lacks the staff and equipment it professes, or did "
   "not exercise its skill to the minimum service delivery standard."],
  necessary=[(HCC_SD, "19", 3)], check=[r"medical negligence", r"minimum service delivery standard"])
c("S10-C15", "citizen", "F10-health-complaint-kp", "routine", ["en"], "latin",
  "How long do I have to complain about a private clinic in Peshawar, and how?",
  "Complaints to the KP Health Care Commission", "kp", "kp", "answer",
  ["Within sixty days of knowing the cause, by a written application with an affidavit, NIC number and address; "
   "anonymous complaints against private providers are not entertained."],
  necessary=[(HCC_KP, "13", 3)], check=[r"sixty days", r"affidavit"])
c("S10-C16", "citizen", "F10-food-no-licence-punjab", "routine", ["en"], "latin",
  "A restaurant in Faisalabad operates with no food licence. What can it be punished with?",
  "Food business without a licence in Punjab", "punjab", "punjab", "answer",
  ["Selling, storing or distributing food without the prescribed registration or licence is punishable with three "
   "days to one year and a fine of ten thousand to five hundred thousand rupees."],
  necessary=[(FOOD_PB, "32", 3)], relevant=[(FOOD_PB, "15", 2)],
  check=[r"five hundred thousand rupees", r"three days"])
c("S10-C17", "citizen", "F10-child-marriage-gb", "family", ["en"], "latin",
  "In Gilgit a family is marrying off their 16-year-old daughter. Is that an offence there?",
  "Child marriage in Gilgit-Baltistan", "gb", "gb", "answer",
  ["A child is anyone under eighteen; whoever performs, conducts or facilitates a child marriage is punishable with "
   "two to three years' rigorous imprisonment and fine, and so is a parent who promotes or permits it."],
  necessary=[(GB_CMR, "4", 3)], relevant=[(GB_CMR, "2", 3), (GB_CMR, "5", 2)],
  check=[r"facilitates any child marriage", r"not be less than two years"])
c("S10-C18", "citizen", "F10-corporal-punishment-gb", "liberty", ["en"], "latin",
  "A teacher in Skardu beats students with a stick. Is that allowed?", "Corporal punishment is prohibited in GB",
  "gb", "gb", "answer",
  ["A child may not be subjected to corporal punishment or humiliating treatment, notwithstanding section 89 PPC; "
   "violations attract the PPC's punishments and further penalties in institutions."],
  necessary=[(GB_CORP, "3", 3)], relevant=[(GB_CORP, "4", 2)], check=[r"corporal punishment"])
c("S10-C19", "citizen", "F10-tenant-information-gb", "property", ["en"], "latin",
  "I am renting out my house in Gilgit. Do I have to tell the police about my tenant?",
  "Information about tenants to the police in GB", "gb", "gb", "answer",
  ["The property dealer, landlord and tenant must give the police information about the tenant within forty-eight "
   "hours of possession, in the prescribed manner."],
  necessary=[(GB_TENANT, "3", 3)], check=[r"forty eight hours"])
c("S10-C20", "citizen", "F10-sound-system-gb", "routine", ["en"], "latin",
  "The neighbours in Hunza play loud music through speakers late every night. Is that unlawful?",
  "Prohibition on noisy sound systems in GB", "gb", "gb", "answer",
  ["Using or allowing a sound system that makes loud or unusual noise disturbing the comfort, repose or peace of "
   "people nearby is unlawful, subject to the Act."],
  necessary=[(GB_SOUND, "3", 3)], check=[r"sound system", r"comfort, repose"])

# ---------------------------------------------------------------- professional lookups (12)
c("S10-P01", "professional", "F10-neqs-ict", "routine", ["en"], "latin",
  "Prohibition of discharges above the National Environmental Quality Standards", "Section 11 Pakistan "
  "Environmental Protection Act, 1997", "fed", "ict", "answer",
  ["No person may discharge or emit effluent, waste, air pollutants or noise above the National Environmental "
   "Quality Standards."],
  necessary=[(EPA_FED, "11", 3)], check=[r"National Environmental Quality Standards"])
c("S10-P02", "professional", "F10-epa-penalty-fed", "routine", ["en"], "latin",
  "Penalty under the federal environmental Act", "Section 17 Pakistan Environmental Protection Act, 1997", "fed",
  "ict", "answer",
  ["Fine up to one million rupees, plus up to one hundred thousand rupees a day for a continuing contravention."],
  necessary=[(EPA_FED, "17", 3)], check=[r"one million rupees", r"one hundred thousand rupees"])
c("S10-P03", "professional", "F10-epa-penalty-kp", "routine", ["en"], "latin",
  "Penalty under the KP environmental Act", "Section 18 Khyber Pakhtunkhwa Environmental Protection Act, 2014",
  "kp", "kp", "answer",
  ["A minimum fine of fifty thousand rupees, extendable to seventy million, and a compulsory daily fine for a "
   "continuing contravention."],
  necessary=[(EPA_KP, "18", 3)], must_not_serve=[(EPA_FED, "17")],
  check=[r"seventy million", r"fifty thousand rupees"])
c("S10-P04", "professional", "F10-protection-order-punjab", "routine", ["en"], "latin",
  "Environmental protection order in Punjab", "Section 16 Punjab Environmental Protection Act, 1997", "punjab",
  "punjab", "answer",
  ["Where the Provincial Agency is satisfied a discharge or act violates the Act or causes adverse effects, it may "
   "issue an environmental protection order."],
  necessary=[(EPA_PB, "16", 3)], check=[r"Provincial Agency is satisfied"])
c("S10-P05", "professional", "F10-tribunals-sindh", "routine", ["en"], "latin",
  "Environmental Protection Tribunals in Sindh", "Section 25 Sindh Environmental Protection Act, 2014", "sindh",
  "sindh", "answer",
  ["Government may by notification establish Environmental Protection Tribunals with territorial or class "
   "jurisdiction."],
  necessary=[(EPA_SD, "25", 3)], check=[r"Environmental Protection Tribunals"])
c("S10-P06", "professional", "F10-tribunals-fed", "routine", ["en"], "latin",
  "Environmental Tribunals under the federal Act", "Section 20 Pakistan Environmental Protection Act, 1997",
  "fed", "ict", "answer",
  ["The Federal Government may establish Environmental Tribunals by notification, specifying their territorial "
   "limits or classes of cases."],
  necessary=[(EPA_FED, "20", 3)], check=[r"Environmental Tribunals"])
c("S10-P07", "professional", "F10-disability-fine-punjab", "routine", ["en"], "latin",
  "Fine for contravening the Punjab disability regulations or Code", "Section 36 Punjab Empowerment of Persons "
  "with Disabilities Act, 2022", "punjab", "punjab", "answer",
  ["The Council may impose a fine of one hundred thousand to five hundred thousand rupees."],
  necessary=[(DIS_PB, "36", 3)], check=[r"one hundred thousand rupees"])
c("S10-P08", "professional", "F10-hcc-fine-punjab", "routine", ["en"], "latin",
  "Fines the Punjab Healthcare Commission may impose", "Section 28 Punjab Healthcare Commission Act, 2010",
  "punjab", "punjab", "answer",
  ["For contravening the Act, rules or regulations, up to five hundred thousand rupees, after an opportunity of "
   "hearing."],
  necessary=[(HCC_PB, "28", 3)], check=[r"five hundred thousand rupees"])
c("S10-P09", "professional", "F10-food-licence-kp", "routine", ["en"], "latin",
  "Licensing of a food business in KP", "Section 15 KP Food Safety Authority Act, 2014", "kp", "kp", "answer",
  ["Apply to the Food Safety and Halal Food Authority in the prescribed manner and fee before using any place for "
   "food business."],
  necessary=[(FOOD_KP, "15", 3)], check=[r"Food Safety and Halal Food Authority"])
c("S10-P10", "professional", "F10-food-licence-punjab", "routine", ["en"], "latin",
  "Registration or licence for a food business in Punjab", "Section 15 Punjab Food Authority Act, 2011",
  "punjab", "punjab", "answer",
  ["No place may be used for food business except under the prescribed registration or licence, save classes the "
   "Authority exempts."],
  necessary=[(FOOD_PB, "15", 3)], check=[r"registration or licence"])
c("S10-P11", "professional", "F10-preemption-gb", "property", ["en"], "latin",
  "In whom does the right of pre-emption vest in Gilgit-Baltistan?", "Section 6 Gilgit-Baltistan Pre-emption Act, "
  "2010", "gb", "gb", "answer",
  ["Firstly in the Shafi Sharik (co-owner), secondly in the Shafi Khalit (participant in special rights such as "
   "passage), thirdly in the Shafi Jar (neighbour)."],
  necessary=[(GB_PREEMPT, "6", 3)], check=[r"Shafi Sharik", r"Shafi Khalit"])
c("S10-P12", "professional", "F10-adult-groom-gb", "family", ["en"], "latin",
  "Punishment for an adult man who contracts a child marriage in GB", "Section 3 Gilgit-Baltistan Child "
  "Marriages Restraint Act, 2015", "gb", "gb", "answer",
  ["A male above eighteen who contracts a child marriage is punishable with two to three years' rigorous "
   "imprisonment and fine."],
  necessary=[(GB_CMR, "3", 3)], check=[r"male above eighteen years"])

# ---------------------------------------------------------------- procedural (8)
c("S10-R01", "procedural", "F10-disability-appeal-punjab", "routine", ["en"], "latin",
  "The disability Council in Punjab fined my company. How do we appeal and by when?",
  "Appeal to the High Court", "punjab", "punjab", "answer",
  ["Within thirty days of the order's communication, to the High Court."],
  necessary=[(DIS_PB, "42", 3)], check=[r"within thirty days", r"High Court"])
c("S10-R02", "procedural", "F10-hcc-appeal-sindh", "routine", ["en"], "latin",
  "The Sindh Healthcare Commission fined my clinic. Can I appeal?", "Appeals from the Sindh Commission", "sindh",
  "sindh", "answer",
  ["A person aggrieved by a licence refusal, suspension or revocation, a closure or improvement order, an equipment "
   "order or a fine may appeal as the section provides."],
  necessary=[(HCC_SD, "31", 3)], check=[r"imposition of fine by the Commission"])
c("S10-R03", "procedural", "F10-hcc-appeal-kp", "routine", ["en"], "latin",
  "The KP Health Care Commission suspended my hospital's licence. What can I do?",
  "Appeals from the KP Commission", "kp", "kp", "answer",
  ["A person aggrieved by suspension or revocation of a licence, among other orders, may appeal within the time the "
   "section sets."],
  necessary=[(HCC_KP, "21", 3)], check=[r"suspend or revoke a license"])
c("S10-R04", "procedural", "F10-guest-information-gb", "routine", ["en"], "latin",
  "I run a guest house in Hunza. What must I do when a guest checks in?", "Reporting guests to the police in GB",
  "gb", "gb", "answer",
  ["The owner or manager must inform the police about the guest within three hours of arrival or check-in."],
  necessary=[(GB_TENANT, "3", 3)], check=[r"three hours"])
c("S10-R05", "procedural", "F10-hostel-guests-gb", "routine", ["en"], "latin",
  "Can a visitor stay overnight at an institution's hostel in Gilgit?", "Guests at institutional hostels in GB",
  "gb", "gb", "answer",
  ["Not without the manager's prior written permission; the manager must inform the police within three hours."],
  necessary=[(GB_TENANT, "4", 3)], check=[r"prior permission in writing"])
c("S10-R06", "procedural", "F10-disability-justice-ict", "routine", ["en"], "latin",
  "I am deaf and have a court hearing in Islamabad. Will I get a sign language interpreter?",
  "Access to justice for persons with disabilities", "fed", "ict", "answer",
  ["The government must provide assistance, including sign language interpreters and attendants, to access the "
   "justice system."],
  necessary=[(DIS_ICT, "17", 3)], check=[r"sign language interpreters"])
c("S10-R07", "procedural", "F10-food-appeal-punjab", "routine", ["en"], "latin",
  "The Special Court convicted me under the Punjab food law. Where and when can I appeal?",
  "Appeal against conviction by a food Special Court", "punjab", "punjab", "answer",
  ["Within thirty days of the order's communication, to the Lahore High Court."],
  necessary=[(FOOD_PB, "45A", 3)], check=[r"within thirty days", r"Lahore High Court"])
c("S10-R08", "procedural", "F10-protection-order-kp", "routine", ["en"], "latin",
  "How can the KP environmental agency stop a brick kiln polluting our area in Charsadda?",
  "Environmental Protection Order in KP", "kp", "kp", "answer",
  ["Where a discharge or act violates the Act, rules or approval conditions and causes adverse effects, the Agency "
   "may issue an Environmental Protection Order."],
  necessary=[(EPA_KP, "17", 3)], check=[r"Agency is satisfied", r"adverse environmental"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5)
c("S10-U01", "urdu", "F10-plastic-ban-kp", "routine", ["ur-Latn"], "roman_urdu",
  "Kya Peshawar mein plastic ke shoppers par pabandi hai?", "KP's plastic ban (Roman Urdu variant of S10-C03)",
  "kp", "kp", "answer", ["Yes, a complete ban."], necessary=[(EPA_KP, "7B", 3)], check=[r"plastic bags"])
c("S10-U02", "urdu", "F10-disability-employment-ict", "routine", ["ur"], "arabic",
  "کیا اسلام آباد میں کوئی کمپنی معذوری کی وجہ سے مجھے نوکری دینے سے انکار کر سکتی ہے؟",
  "Disability and employment (Urdu variant of S10-C08)", "fed", "ict", "answer",
  ["No: discrimination on the ground of disability is prohibited."], necessary=[(DIS_ICT, "10", 3)],
  check=[r"ground of disability"])
c("S10-U03", "urdu", "F10-medical-negligence-punjab", "routine", ["ur-Latn"], "roman_urdu",
  "Lahore ke private hospital ki laparwahi se meri ammi ko nuqsan hua, qanoon mein medical negligence kya hai?",
  "Medical negligence in Punjab (Roman Urdu variant of S10-C13)", "punjab", "punjab", "answer",
  ["Lack of professed staff or equipment, or skill not exercised with reasonable competence."],
  necessary=[(HCC_PB, "19", 3)], check=[r"reasonable competence"])
c("S10-U04", "urdu", "F10-child-marriage-gb", "family", ["ur-Latn"], "roman_urdu",
  "Gilgit mein solah saal ki larki ki shadi karwana kya jurm hai?",
  "Child marriage in GB (Roman Urdu variant of S10-C17)", "gb", "gb", "answer",
  ["Yes: two to three years' rigorous imprisonment and fine."], necessary=[(GB_CMR, "4", 3)],
  check=[r"child marriage"])
c("S10-U05", "urdu", "F10-food-no-licence-punjab", "routine", ["ur-Latn"], "roman_urdu",
  "Faisalabad mein bagair license ke restaurant chalane ki kya saza hai?",
  "Food business without a licence (Roman Urdu variant of S10-C16)", "punjab", "punjab", "answer",
  ["Three days to a year and a fine of up to five hundred thousand rupees."], necessary=[(FOOD_PB, "32", 3)],
  check=[r"five hundred thousand rupees"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S10-X01", "unanswerable", "F10-x-aqi", "routine", ["en"], "latin",
  "What is Lahore's air quality index right now?", "A live measurement", "punjab", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["quoting a figure"],
                  why="a live reading is not law"))
c("S10-X02", "unanswerable", "F10-x-hospital-recommendation", "routine", ["en"], "latin",
  "Which hospital in Karachi is best for heart surgery?", "A recommendation", "sindh", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["recommending"],
                  why="not a question of law"))
c("S10-X03", "unanswerable", "F10-x-foreign-plastic", "routine", ["en"], "latin",
  "What are the rules on plastic bags in China?", "Foreign environmental law", "foreign", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from KP's ban"], why="the corpus is Pakistani law only"))
c("S10-X04", "unanswerable", "F10-x-licence-lookup", "routine", ["en"], "latin",
  "Does the Karachi restaurant 'Spice Garden' hold a valid food licence?", "A register lookup", "sindh", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["guessing"],
                  why="licence registers are not in the corpus"))
c("S10-X05", "unanswerable", "F10-x-negligence-outcome", "routine", ["en"], "latin",
  "How much compensation will the Healthcare Commission award me for my father's death?",
  "A prediction of an award", "punjab", None, "abstain", [],
  abstention=dict(code="professional_review_required", requiredClarification=["the facts"],
                  unsafeAlternatives=["predicting an amount"],
                  why="predicting an adjudicator's award on particular facts is legal advice"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 10: welfare and regulation by place -- environment, disability, healthcare "
                              "commissions, food authorities, and Gilgit-Baltistan's own Acts."))
