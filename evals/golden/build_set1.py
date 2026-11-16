"""Build golden-pk-v1 draft SET 1 (50 cases) as docs/10 §5 LegalEvalCase records.

WHAT THIS IS. Stage A0 (case authored without system output) and A3 (stable legal identities and source resolution)
of docs/10 §5, done by the lead (claude) on 16 Nov 2026. Every gold unit is a released provision resolved here by
its document and path (or section label) to its provision id; its text, instrument, status and official source URL
are read from the database (INV-1), and the case is checked against operative_provision at its own as_of and
territory (an 'answer' case must be servable there; a hard negative from another territory must not be).

WHAT THIS IS NOT. A1 (two independent legal annotators), A2 (senior-advocate adjudication) and A4 (family split
freeze) have not happened: review.annotatorA is this draft, annotatorB and agreement are null. Grades are a first
proposal for the annotators to confirm or change; the set must not be used to tune or report until A1-A4 are done.

    python evals/golden/build_set1.py            # writes evals/golden/golden-pk-v1-set1.draft.jsonl and .md
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

AS_OF = "2026-11-16"
OUT = ROOT / "evals/golden/golden-pk-v1-set1.draft.jsonl"
REPORT = ROOT / "evals/golden/golden-pk-v1-set1.draft.md"

# unit: (document_id, path or section label, grade 0-3). A path contains a dot; otherwise it is a section label.
C = []


def case(cid, stratum, family, risk, lang, script, text, meaning, jurisdiction, territory, outcome, props,
         necessary=(), relevant=(), negatives=(), abstention=None, facts=(), omitted=()):
    C.append(dict(cid=cid, stratum=stratum, family=family, risk=risk, lang=lang, script=script, text=text,
                  meaning=meaning, jurisdiction=jurisdiction, territory=territory, outcome=outcome, props=props,
                  necessary=list(necessary), relevant=list(relevant), negatives=list(negatives),
                  abstention=abstention, facts=list(facts), omitted=list(omitted)))


# ---------------------------------------------------------------- citizen scenarios (20)
case("S1-C01", "citizen", "F-rent-punjab", "property", ["en"], "latin",
     "My landlord in Lahore wants me out of the house I rent. On what grounds can he get me evicted?",
     "Grounds on which a landlord may seek eviction under Punjab rent law", "punjab", "punjab", "answer",
     ["A landlord may seek eviction only on the grounds the Punjab Rented Premises Act, 2009 lists, including expiry "
      "of the tenancy, failure to pay rent within thirty days after it is due, and breach of a term of the tenancy."],
     necessary=[(6269, "15", 3)], negatives=[(1794, "15", 0)])
case("S1-C02", "citizen", "F-rent-sindh", "property", ["en"], "latin",
     "I rent a flat in Karachi. Can my landlord throw me out for not paying rent, and who decides?",
     "Eviction for default in rent under the Sindh rented premises law, and the forum", "sindh", "sindh", "answer",
     ["A Karachi landlord seeking eviction applies to the Rent Controller under the Sind Rented Premises Ordinance, "
      "1979, and default in rent is a ground the Controller may act on."],
     necessary=[(1794, "15", 3)], negatives=[(6269, "15", 0)])
case("S1-C03", "citizen", "F-polygamy", "family", ["en"], "latin",
     "Can my husband marry a second wife without my permission?",
     "Whether a second marriage needs prior permission under the Muslim Family Laws Ordinance", "fed", "punjab",
     "answer", ["A man may not contract another marriage during an existing marriage without the previous written "
                "permission of the Arbitration Council; the application must state whether the existing wife consents."],
     necessary=[(3283, "6", 3)])
case("S1-C04", "citizen", "F-talaq-notice", "family", ["en"], "latin",
     "My husband says he has divorced me. Does he have to inform anyone for it to count?",
     "Notice of talaq to the Chairman under the Muslim Family Laws Ordinance", "fed", "sindh", "answer",
     ["After pronouncing talaq a husband must give the Chairman written notice and supply a copy to the wife."],
     necessary=[(3283, "7", 3)])
case("S1-C05", "citizen", "F-dowry", "family", ["en"], "latin",
     "Is there a legal limit on how much dowry can be given at a wedding?",
     "Statutory ceiling on dowry and bridal gifts", "fed", "punjab", "answer",
     ["The aggregate value of dowry and presents to the bride, and of bridal gifts, may not exceed the ceiling the "
      "Dowry and Bridal Gifts (Restriction) Act, 1976 sets (five thousand rupees in the held text)."],
     necessary=[(4031, "3", 3)], relevant=[(4031, "2", 1)])
case("S1-C06", "citizen", "F-child-marriage-sindh", "family", ["en"], "latin",
     "My cousin's family in Hyderabad wants to marry her off at 16. Is that allowed in Sindh?",
     "Minimum age of marriage and the offence of child marriage in Sindh", "sindh", "sindh", "answer",
     ["In Sindh a child is a person under eighteen, a marriage to which a child is party is a child marriage, and a "
      "male adult who contracts one is punishable."],
     necessary=[(678, "2", 3), (678, "3", 2)])
case("S1-C07", "citizen", "F-dv-punjab", "liberty", ["en"], "latin",
     "My husband beats me. I live in Faisalabad. Can a court order him to stay away from me?",
     "Protection order under the Punjab Protection of Women against Violence Act, 2016", "punjab", "punjab", "answer",
     ["If satisfied that violence has been or is likely to be committed, the Court may pass a protection order "
      "directing the defendant not to communicate with and to stay away from the aggrieved person."],
     necessary=[(6414, "7", 3)])
case("S1-C08", "citizen", "F-workplace-harassment", "privacy", ["en"], "latin",
     "My manager at an office in Islamabad keeps harassing me. Where can I complain?",
     "Forums for a workplace harassment complaint", "fed", "ict", "answer",
     ["A complainant may complain either to the Ombudsperson or to the organisation's Inquiry Committee."],
     necessary=[(2105, "8", 3)], relevant=[(2105, "4", 2)])
case("S1-C09", "citizen", "F-consumer-punjab", "money", ["en"], "latin",
     "I bought a washing machine in Lahore that turned out defective and damaged my floor. Can I claim damages?",
     "Liability for defective products and the forum under the Punjab Consumer Protection Act", "punjab", "punjab",
     "answer", ["A manufacturer is liable for damage caused by a defect in a product used as reasonably anticipated; "
                "a claim is filed before the Consumer Court."],
     necessary=[(6267, "4", 3), (6267, "25", 3)])
case("S1-C10", "citizen", "F-cheque", "money", ["en"], "latin",
     "Someone paid back a loan with a cheque that bounced. Is that a crime?",
     "Dishonestly issuing a cheque that is dishonoured", "fed", "sindh", "answer",
     ["Dishonestly issuing a cheque towards repayment of a loan that is dishonoured is punishable with imprisonment "
      "up to three years, fine, or both, unless the issuer establishes the stated defence."],
     necessary=[(4441, "489F", 3)])
case("S1-C11", "citizen", "F-murder-punishment", "liberty", ["en"], "latin",
     "What is the punishment for murder in Pakistan?",
     "Punishment for qatl-i-amd", "fed", "kp", "answer",
     ["Qatl-i-amd is punishable with death as qisas or, where the qisas proof is not available, as ta'zir with death "
      "or imprisonment for life, subject to the Chapter."],
     necessary=[(4441, "302", 3)])
case("S1-C12", "citizen", "F-workmen-compensation", "money", ["en"], "latin",
     "I was injured by a machine at the factory where I work. Does my employer have to compensate me?",
     "Employer's liability for workplace injury", "fed", "punjab", "conditional",
     ["An employer is liable to compensate a workman for personal injury by accident arising out of and in the course "
      "of employment, subject to the Act's exceptions (e.g. disablement not exceeding the stated days)."],
     necessary=[(4007, "3", 3)])
case("S1-C13", "citizen", "F-wage-time", "money", ["en"], "latin",
     "My factory has not paid last month's salary. By when must they pay?",
     "Time of payment of wages", "fed", "punjab", "conditional",
     ["Wages in an establishment with fewer than one thousand workers must be paid before the seventh day after the "
      "wage period ends; larger ones before the tenth."],
     necessary=[(3550, "5", 3)], omitted=["number of workers employed"])
case("S1-C14", "citizen", "F-minwage-sindh", "money", ["en"], "latin",
     "Who decides the minimum wage in Sindh and how is it announced?",
     "Fixing and declaring minimum wages under the Sindh Minimum Wages Act, 2015", "sindh", "sindh", "answer",
     ["The Minimum Wages Board recommends rates, and Government declares them by notification in the official Gazette."],
     necessary=[(1772, "6", 3)], relevant=[(1772, "4", 2)])
case("S1-C15", "citizen", "F-sale-registration", "property", ["en"], "latin",
     "I am buying a plot. Is a stamp-paper agreement enough, or does the sale have to be registered?",
     "Form of sale of immovable property and compulsory registration", "fed", "punjab", "answer",
     ["A sale of tangible immovable property of one hundred rupees or more can be made only by a registered "
      "instrument; such documents are compulsorily registrable."],
     necessary=[(3991, "54", 3)], relevant=[(3876, "17", 2)])
case("S1-C16", "citizen", "F-specific-performance", "property", ["en"], "latin",
     "The seller took my advance for a house and now refuses to transfer it. Can a court make him go through with it?",
     "Specific performance of a contract for sale", "fed", "sindh", "conditional",
     ["Specific performance of a contract may, in the court's discretion, be enforced in the cases the Specific "
      "Relief Act, 1877 lists."],
     necessary=[(3944, "12", 3)], relevant=[(4237, "fed.act.y1908_o107.pt_VI_n10_1.s_113", 2)])
case("S1-C17", "citizen", "F-specific-performance", "deadline", ["en"], "latin",
     "How long do I have to file a case to force the seller to complete the sale?",
     "Limitation period for a suit for specific performance", "fed", "punjab", "answer",
     ["The period is three years, running from the date fixed for performance or, if none, from when the plaintiff "
      "has notice that performance is refused."],
     necessary=[(4237, "fed.act.y1908_o107.pt_VI_n10_1.s_113", 3)])
case("S1-C18", "citizen", "F-rti-kp", "routine", ["en"], "latin",
     "How do I ask a government department in Peshawar for information it holds?",
     "Right to information and the Public Information Officer in KP", "kp", "kp", "answer",
     ["No requester may be denied access to information except under the Act; a request is lodged with the public "
      "body's designated Public Information Officer."],
     necessary=[(4230, "6", 3)], relevant=[(4230, "kp.act.y2013_XXVII_o1804.s_3", 2)])
case("S1-C19", "citizen", "F-custody", "family", ["en"], "latin",
     "After our divorce, who gets custody of our children? What does the court look at?",
     "Matters a court considers in appointing a guardian", "fed", "balochistan", "answer",
     ["The court is guided by the welfare of the minor, having regard to age, sex, religion, the proposed guardian's "
      "character and kinship, a deceased parent's wishes and the minor's preference if old enough."],
     necessary=[(4283, "17", 3)])
case("S1-C20", "citizen", "F-rent-ajk", "property", ["en"], "latin",
     "My landlord in Muzaffarabad wants to evict me. What is the procedure in Azad Kashmir?",
     "Eviction of tenants under the Azad Kashmir Rent Restriction Act, 1952", "ajk", "ajk", "answer",
     ["A tenant may be evicted only in accordance with section 13: the landlord applies to the Deputy Commissioner, "
      "who may direct eviction on the grounds it lists (e.g. non-payment within fifteen days)."],
     necessary=[(11195, "13", 3)], relevant=[(10096, "13", 3)], negatives=[(6269, "15", 0)])

# ---------------------------------------------------------------- professional lookups (12)
case("S1-P01", "professional", "F-bail-nonbailable", "liberty", ["en"], "latin",
     "CrPC provision on bail in non-bailable offences", "Bail in non-bailable offences", "fed", "punjab", "answer",
     ["Section 497 CrPC: a person accused of a non-bailable offence may be released on bail, but not where there are "
      "reasonable grounds to believe him guilty of an offence punishable with death or life imprisonment or ten years, "
      "subject to the provisos."],
     necessary=[(4501, "497", 3)], negatives=[(4501, "496", 0)])
case("S1-P02", "professional", "F-fir", "liberty", ["en"], "latin",
     "Section on recording information in cognizable cases (FIR)", "Section 154 CrPC", "fed", "sindh", "answer",
     ["Every information relating to a cognizable offence given to an officer in charge of a police station must be "
      "reduced to writing, read over and signed, and its substance entered in the prescribed book."],
     necessary=[(4501, "154", 3)])
case("S1-P03", "professional", "F-civil-jurisdiction", "routine", ["en"], "latin",
     "Civil courts' jurisdiction over suits of a civil nature — CPC section", "Section 9 CPC", "fed", "kp", "answer",
     ["Courts try all suits of a civil nature except those whose cognizance is expressly or impliedly barred."],
     necessary=[(4463, "9", 3)])
case("S1-P04", "professional", "F-contract-formation", "routine", ["en"], "latin",
     "Contract Act: what agreements are contracts", "Section 10 Contract Act", "fed", "punjab", "answer",
     ["Agreements are contracts if made by free consent of competent parties, for lawful consideration and object, "
      "and not expressly declared void."], necessary=[(4337, "10", 3)])
case("S1-P05", "professional", "F-contract-damages", "money", ["en"], "latin",
     "Measure of damages for breach of contract", "Section 73 Contract Act", "fed", "sindh", "answer",
     ["The injured party is entitled to compensation for loss that naturally arose in the usual course of things or "
      "that the parties knew was likely to result, not for remote or indirect loss."],
     necessary=[(4337, "73", 3)])
case("S1-P06", "professional", "F-writ", "liberty", ["en"], "latin",
     "Constitutional writ jurisdiction of the High Court", "Article 199", "fed", "punjab", "answer",
     ["A High Court may, if satisfied no other adequate remedy is provided by law, make the orders Article 199 lists."],
     necessary=[(4419, "199", 3)])
case("S1-P07", "professional", "F-fair-trial", "liberty", ["en"], "latin",
     "Constitutional right to a fair trial", "Article 10A", "fed", "balochistan", "answer",
     ["For the determination of civil rights and obligations or any criminal charge, a person is entitled to a fair "
      "trial and due process."], necessary=[(4419, "10A", 3)])
case("S1-P08", "professional", "F-ordinance-life", "routine", ["en"], "latin",
     "How long does a Presidential Ordinance remain in force?", "Article 89(2)", "fed", "ict", "answer",
     ["An Ordinance stands repealed 120 days after promulgation unless disapproved earlier; the National Assembly may "
      "extend it once by a further 120 days."], necessary=[(4419, "89", 3)])
case("S1-P09", "professional", "F-sales-tax-scope", "money", ["en"], "latin",
     "Charging section of the Sales Tax Act, 1990", "Section 3 Sales Tax Act", "fed", "punjab", "answer",
     ["Sales tax is charged on the value of taxable supplies and imports at the rate section 3 prints (eighteen per "
      "cent in the held text), subject to the Act."], necessary=[(4447, "3", 3)], negatives=[(9296, "3", 0)])
case("S1-P10", "professional", "F-tax-residence", "money", ["en"], "latin",
     "When is an individual resident for income tax?", "Section 82 Income Tax Ordinance, 2001", "fed", "sindh",
     "answer", ["An individual is resident for a tax year if present in Pakistan 183 days or more in it, or is a "
                "government employee posted abroad, as section 82 provides."],
     necessary=[(4489, "82", 3)])
case("S1-P11", "professional", "F-companies-1984", "money", ["en"], "latin",
     "Is the Companies Ordinance, 1984 still in force?", "Repeal of the Companies Ordinance by the Companies Act, 2017",
     "fed", "punjab", "answer",
     ["The Companies Ordinance, 1984 stands repealed by section 509 of the Companies Act, 2017 — except Part VIIIA "
      "(sections 282A to 282N), which the Act keeps in force — subject to the savings."],
     necessary=[(4486, "509", 3)], negatives=[(4495, "1", 0)])
case("S1-P12", "professional", "F-unauthorised-access", "liberty", ["en"], "latin",
     "Offence of unauthorised access to an information system — current law", "Section 3 PECA 2016", "fed", "kp",
     "answer", ["Gaining unauthorised access to an information system or data with dishonest intention is punishable "
                "under section 3 of the Prevention of Electronic Crimes Act, 2016."],
     necessary=[(3592, "3", 3)], negatives=[(5850, "3", 0)])

# ---------------------------------------------------------------- procedural (8)
case("S1-R01", "procedural", "F-succession-certificate", "money", ["en"], "latin",
     "My father died leaving bank deposits. How do I get a succession certificate?",
     "Application for a succession certificate", "fed", "punjab", "answer",
     ["Apply to the District Judge by a signed and verified petition setting out the particulars section 372 lists."],
     necessary=[(4379, "372", 3)], relevant=[(4379, "370", 1)])
case("S1-R02", "procedural", "F-sale-registration", "property", ["en"], "latin",
     "Which documents must be compulsorily registered?", "Section 17 Registration Act, 1908", "fed", "sindh",
     "answer", ["Section 17 lists documents of which registration is compulsory, including non-testamentary instruments "
                "transferring interests in immovable property of one hundred rupees and upwards."],
     necessary=[(3876, "17", 3)])
case("S1-R03", "procedural", "F-khula", "family", ["en"], "latin",
     "How does a wife get khula through the family court?", "Pre-trial and khula in the Family Courts Act, 1964",
     "fed", "punjab", "answer",
     ["At the pre-trial the family court attempts reconciliation; in a suit for dissolution, if reconciliation fails, "
      "the court passes a decree for dissolution (khula) as section 10 provides."],
     necessary=[(2944, "10", 3)], relevant=[(3100, "2", 2)])
case("S1-R04", "procedural", "F-khula", "family", ["en"], "latin",
     "On what grounds can a Muslim wife get a court decree dissolving her marriage?",
     "Grounds under the Dissolution of Muslim Marriages Act, 1939", "fed", "kp", "answer",
     ["Section 2 lists the grounds, including the husband's unknown whereabouts for four years, failure to maintain "
      "for two years, and an additional wife in contravention of the MFLO."], necessary=[(3100, "2", 3)])
case("S1-R05", "procedural", "F-rent-sindh", "deadline", ["en"], "latin",
     "The Rent Controller in Karachi ordered my eviction. How long do I have to appeal and to whom?",
     "Appeal from the Rent Controller in Sindh", "sindh", "sindh", "answer",
     ["Appeal lies within thirty days of the order to the District Judge having jurisdiction over the premises."],
     necessary=[(1794, "21", 3)])
case("S1-R06", "procedural", "F-arbitration-award", "money", ["en"], "latin",
     "We have an arbitration award. How does it become enforceable as a court judgment?",
     "Filing an award and judgment in terms of the award", "fed", "punjab", "answer",
     ["The arbitrators sign the award and file it in court on request; once the time to set it aside passes or an "
      "application is refused, the court pronounces judgment and a decree follows."],
     necessary=[(3132, "14", 3), (3132, "17", 3)])
case("S1-R07", "procedural", "F-dv-sindh", "liberty", ["en"], "latin",
     "How do I apply for protection from domestic violence in Sindh?",
     "Petition and protection orders under the Sindh Domestic Violence Act, 2013", "sindh", "sindh", "answer",
     ["An aggrieved person petitions the court, which issues notice and may pass a protection order once satisfied that "
      "domestic violence has prima facie taken place."],
     necessary=[(2628, "7", 3), (2628, "11", 3)])
case("S1-R08", "procedural", "F-juvenile", "liberty", ["en"], "latin",
     "My 15-year-old son has been arrested. Which court will try him?",
     "Juvenile Courts under the Juvenile Justice System Act, 2018", "fed", "punjab", "answer",
     ["A juvenile is tried by a Juvenile Court established or designated under the Juvenile Justice System Act, 2018; "
      "the Juvenile Justice System Ordinance, 2000 is repealed."],
     necessary=[(3489, "4", 3)], negatives=[(9769, "1", 0)])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5), each in its English family
case("S1-U01", "urdu", "F-talaq-notice", "family", ["ur-Latn"], "roman_urdu",
     "Talaq dene ke baad shohar ko kis ko notice dena zaroori hai?",
     "Notice of talaq (Roman Urdu variant of S1-C04)", "fed", "punjab", "answer",
     ["After pronouncing talaq a husband must give the Chairman written notice and supply a copy to the wife."],
     necessary=[(3283, "7", 3)])
case("S1-U02", "urdu", "F-bail-nonbailable", "liberty", ["ur-Latn"], "roman_urdu",
     "Na-qabil-e-zamanat jurm mein zamanat kab mil sakti hai?",
     "Bail in non-bailable offences (Roman Urdu variant of S1-P01)", "fed", "sindh", "answer",
     ["Section 497 CrPC governs bail in non-bailable offences."], necessary=[(4501, "497", 3)])
case("S1-U03", "urdu", "F-rent-punjab", "property", ["ur"], "arabic",
     "پنجاب میں مالک مکان کرایہ دار کو کن وجوہات پر مکان خالی کروا سکتا ہے؟",
     "Grounds for eviction in Punjab (Urdu variant of S1-C01)", "punjab", "punjab", "answer",
     ["Section 15 of the Punjab Rented Premises Act, 2009 lists the grounds for eviction."],
     necessary=[(6269, "15", 3)])
case("S1-U04", "urdu", "F-cheque", "money", ["ur"], "arabic",
     "چیک باؤنس ہونے پر کیا سزا ہے؟",
     "Dishonoured cheque (Urdu variant of S1-C10)", "fed", "punjab", "answer",
     ["Section 489-F PPC punishes dishonestly issuing a cheque that is dishonoured."], necessary=[(4441, "489F", 3)])
case("S1-U05", "urdu", "F-polygamy", "family", ["ur-Latn"], "roman_urdu",
     "Kya doosri shadi ke liye pehli biwi ki ijazat zaroori hai?",
     "Permission for a second marriage (Roman Urdu variant of S1-C03)", "fed", "kp", "answer",
     ["Previous written permission of the Arbitration Council is required; the application states whether the existing "
      "wife consents."], necessary=[(3283, "6", 3)])

# ---------------------------------------------------------------- deliberately unanswerable (5)
case("S1-X01", "unanswerable", "F-x-gb", "property", ["en"], "latin",
     "What does the rent law in Gilgit-Baltistan say about eviction?",
     "Rent law of Gilgit-Baltistan", "gb", "gb", "abstain", [],
     abstention=dict(code="unsupported_scope", requiredClarification=[],
                     unsafeAlternatives=["answering from Punjab or AJK rent law", "answering from federal law"],
                     why="the corpus holds no released Gilgit-Baltistan law"),
     negatives=[(6269, "15", 0), (11195, "13", 0)])
case("S1-X02", "unanswerable", "F-x-precedent", "routine", ["en"], "latin",
     "What did the Supreme Court decide in the Panama Papers case?",
     "A judgment's holding", "fed", None, "abstain", [],
     abstention=dict(code="unsupported_scope", requiredClarification=[],
                     unsafeAlternatives=["summarising from model memory", "citing a statute instead of the judgment"],
                     why="the corpus holds no judgments (CLAUDE.md: no judgment table yet)"))
case("S1-X03", "unanswerable", "F-x-foreign", "liberty", ["en"], "latin",
     "What is the punishment for theft under the Indian Penal Code in India today?",
     "Current Indian law", "foreign", None, "abstain", [],
     abstention=dict(code="unsupported_scope", requiredClarification=[],
                     unsafeAlternatives=["answering from Pakistan Penal Code s.379"],
                     why="the corpus is Pakistani law only"),
     negatives=[(4441, "379", 0)])
case("S1-X04", "unanswerable", "F-x-outcome", "property", ["en"], "latin",
     "Will I win my property case against my brother?",
     "Prediction of a case outcome on undisclosed facts", "fed", None, "abstain", [],
     abstention=dict(code="professional_review_required", requiredClarification=["facts", "documents", "forum"],
                     unsafeAlternatives=["predicting an outcome"], why="outcome prediction is legal advice"))
case("S1-X05", "unanswerable", "F-x-nonlegal", "routine", ["en"], "latin",
     "What documents do I need for a UAE tourist visa?",
     "Foreign immigration requirements", "foreign", None, "abstain", [],
     abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["guessing"],
                     why="not Pakistani statute law"))


def resolve(cur, doc: int, ref: str) -> dict | None:
    cur.execute("SELECT id, coalesce(display_title, short_title), status::text, source_url, jurisdiction::text, year "
                "FROM v_release_instrument WHERE document_id = %s", (doc,))
    r = cur.fetchone()
    if not r:
        return None
    iid, title, status, url, jur, year = r
    if "." in ref:
        cur.execute("""SELECT p.id::text, p.path::text, p.label, p.heading FROM provision p
                        WHERE p.instrument_id = %s AND p.is_active AND p.path::text = %s""", (iid, ref))
    else:
        cur.execute("""SELECT p.id::text, p.path::text, p.label, p.heading FROM provision p
                        WHERE p.instrument_id = %s AND p.is_active AND p.label = %s
                          AND p.kind::text IN ('section', 'article', 'order', 'schedule')
                        ORDER BY nlevel(p.path), p.ordinal LIMIT 1""", (iid, ref))
    p = cur.fetchone()
    if not p:
        return None
    pid, path, label, heading = p
    cur.execute("""SELECT string_agg(coalesce(v.text_en, ''), ' ' ORDER BY d.ord) FROM (
                     SELECT p2.id, p2.ordinal AS ord FROM provision p2
                      WHERE p2.instrument_id = %s AND p2.is_active AND (p2.path <@ %s::ltree)) d
                     JOIN provision_version v ON v.provision_id = d.id AND upper_inf(v.validity)""", (iid, path))
    text = " ".join((cur.fetchone()[0] or "").split())
    return dict(provisionId=pid, path=path, label=label, heading=heading, instrumentId=str(iid), documentId=doc,
                instrument=title, jurisdiction=jur, year=year, status=status, officialUrl=url,
                textSha256=hashlib.sha256(text.encode()).hexdigest(), excerpt=text[:400])


def operative(cur, unit: dict, territory: str | None) -> bool:
    cur.execute("SELECT set_config('nzq.as_of', %s, false)", (AS_OF,))
    cur.execute("SELECT set_config('nzq.territory', %s, false)", (territory or "",))
    # a section whose words sit in its subsections has no text version of its own, so operative_provision serves its
    # descendants, not the section row: the unit is servable when it or any provision under it is served
    cur.execute("""SELECT EXISTS (SELECT 1 FROM operative_provision
                                   WHERE instrument_id = %s AND path <@ %s::ltree)""",
                (unit["instrumentId"], unit["path"]))
    ok = cur.fetchone()[0]
    cur.execute("RESET nzq.territory")
    return ok


def main() -> int:
    from nizam.storage.db import connect
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    problems, lines, rows = [], [], []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        for c in C:
            units = {}
            for kind in ("necessary", "relevant", "negatives"):
                units[kind] = []
                for doc, ref, grade in c[kind]:
                    u = resolve(cur, doc, ref)
                    if u is None:
                        problems.append(f"{c['cid']}: {kind} unit {doc}/{ref} does not resolve"); continue
                    territory = c["territory"] if c["territory"] not in (None, "gb") else None
                    u["grade"] = grade
                    u["operativeAtAsOfInTerritory"] = operative(cur, u, c["territory"]) if c["territory"] else None
                    if kind == "necessary" and c["outcome"] != "abstain" and not u["operativeAtAsOfInTerritory"]:
                        problems.append(f"{c['cid']}: necessary unit {doc}/{ref} is NOT served by operative_provision "
                                        f"at {AS_OF} in {c['territory']}")
                    units[kind].append(u)
            rec = {
                "caseId": c["cid"], "datasetVersion": "golden-pk-v1-draft/set1", "familyId": c["family"],
                "riskClass": c["risk"], "languages": c["lang"], "stratum": c["stratum"],
                "question": {"text": c["text"], "script": c["script"], "intendedMeaning": c["meaning"],
                             "suppliedFacts": c["facts"], "omittedFacts": c["omitted"]},
                "scope": {"jurisdiction": c["jurisdiction"], "territory": c["territory"], "asOf": AS_OF},
                "expectedOutcome": c["outcome"],
                "propositions": [{"id": f"{c['cid']}-p{i + 1}", "text": t, "materiality": "material",
                                  "necessaryEvidence": [u["provisionId"] for u in units["necessary"]]}
                                 for i, t in enumerate(c["props"])],
                "retrievalGold": {"necessaryUnits": units["necessary"], "relevantUnits": units["relevant"],
                                  "hardNegatives": units["negatives"]},
                "abstention": c["abstention"],
                "provenance": {"officialUrls": sorted({u["officialUrl"] for k in units for u in units[k]
                                                       if u.get("officialUrl")}),
                               "corpusRevision": rev, "labelledAt": date.today().isoformat()},
                "review": {"annotatorA": "claude (draft: A0 authoring + A3 identity resolution)", "annotatorB": None,
                           "agreement": None, "adjudicator": None, "reasons": [],
                           "status": "draft — not gold until A1/A2 (two legal annotators, senior advocate)"},
            }
            rows.append(rec)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # readable report: query and its gold results
    from collections import Counter
    strata = Counter(r["stratum"] for r in rows)
    lines.append(f"# golden-pk-v1 — draft set 1 ({len(rows)} cases)\n")
    lines.append(f"As of {AS_OF}; corpus revision {rev}. Strata: " + ", ".join(f"{k} {v}" for k, v in strata.items()) + ".")
    lines.append("Status: **draft** — A0 authoring and A3 identity resolution only. Not gold until two legal annotators "
                 "(A1) and a senior advocate (A2) have reviewed it; do not tune or report on it before then.\n")
    for r in rows:
        q = r["question"]
        lines.append(f"## {r['caseId']} · {r['stratum']} · {r['scope']['jurisdiction']}/{r['scope']['territory']} · "
                     f"expect **{r['expectedOutcome']}**\n")
        lines.append(f"**Q:** {q['text']}\n")
        for p in r["propositions"]:
            lines.append(f"- *Proposition:* {p['text']}")
        for kind, label in (("necessaryUnits", "Necessary"), ("relevantUnits", "Relevant"),
                            ("hardNegatives", "Hard negative")):
            for u in r["retrievalGold"][kind]:
                served = {True: "served", False: "not served", None: "-"}[u["operativeAtAsOfInTerritory"]]
                lines.append(f"- **{label} (grade {u['grade']})** — {u['instrument']}, s./art. {u['label']} "
                             f"({u['status']}; {served} in {r['scope']['territory']}) · `{u['provisionId']}` · "
                             f"[source]({u['officialUrl']})\n  > {u['excerpt'][:260]}")
        if r["abstention"]:
            lines.append(f"- *Abstain:* {r['abstention']['code']} — {r['abstention']['why']}")
        lines.append("")
    if problems:
        lines.append("## Problems found while building\n" + "\n".join(f"- {p}" for p in problems))
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} cases -> {OUT}")
    print(dict(strata))
    print("problems:", len(problems))
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
