"""Build golden-pk-v1 draft SET 9 (50 cases): commerce, money and private lending.

The prohibition of interest on private loans in each place that enacted its own Act (Punjab 2022, KP 2016, Sindh
2023, Islamabad 2023, Balochistan's 2014 ban on private money lending) -- each a trap for the others; guarantee,
indemnity, bailment, pledge and agency (Contract Act); passing of property and the unpaid seller (Sale of Goods);
dissolution of partnerships; limited liability partnerships; life insurance claims, nomination and the Insurance
Ombudsman; cartels, dominance, deceptive marketing and appeals (Competition Act); electronic documents and signatures;
cheques, presentment and notice of dishonour.

Punjab labour law is left out: the Punjab Labour Code 2026 s.435 repeals the Punjab labour statutes from a date fixed
by notification, and that notification is not yet verified (D-104, open question). Contract, Sale of Goods and
Partnership cases are asked outside Punjab (PROVINCIAL_COPY). Stage A0 + A3 by the lead (claude), 20 Nov 2026;
propositions written from the held text (peek.py) and re-verified by each case's `check` regexes at every build. Not
gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set9.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set9")
c = S.case
CA, SOG, PA, LLP, INS, COMP, ETO, NIA = 4337, 3617, 4075, 4220, 4414, 3067, 3526, 4192
INT_PB, INT_KP, INT_SD, INT_ICT, LEND_BL = 3675, 2729, 2273, 2122, 159

# ---------------------------------------------------------------- citizen scenarios (20)
c("S9-C01", "citizen", "F9-interest-loan-punjab", "money", ["en"], "latin",
  "A man in Lahore lends money on interest to people in our street. Is that allowed?",
  "Interest-based private lending is an offence in Punjab", "punjab", "punjab", "answer",
  ["No money lender may lend for the purpose of receiving interest or carry on an interest-based transaction in "
   "Punjab; it is punishable with three to ten years' imprisonment and a fine, and borrowers' obligations to pay "
   "interest stand extinguished."],
  necessary=[(INT_PB, "3", 3)], relevant=[(INT_PB, "7", 2)], must_not_serve=[(INT_KP, "3")],
  check=[r"receiving interest thereon", r"ten years"])
c("S9-C02", "citizen", "F9-interest-loan-kp", "money", ["en"], "latin",
  "I borrowed from a private lender in Peshawar who now demands double back as interest. Is his business legal?",
  "Interest-based private lending is an offence in KP", "kp", "kp", "answer",
  ["No money lender may advance a loan for interest or carry on an interest-based transaction in the Province; it is "
   "punishable with three to ten years and a fine."],
  necessary=[(INT_KP, "3", 3)], must_not_serve=[(INT_PB, "3")],
  check=[r"interest based transaction in the Province", r"ten years"])
c("S9-C03", "citizen", "F9-interest-extinguished-sindh", "money", ["en"], "latin",
  "I agreed to pay interest to a private lender in Karachi. Do I still have to pay the interest?",
  "The obligation to pay interest stands extinguished in Sindh", "sindh", "sindh", "answer",
  ["On the Act's commencement every debtor's obligation to pay interest on a private debt stands extinguished."],
  necessary=[(INT_SD, "7", 3)], check=[r"stand extinguished"])
c("S9-C04", "citizen", "F9-money-lending-balochistan", "money", ["en"], "latin",
  "Is private money lending allowed in Quetta?", "Private money lending is prohibited in Balochistan",
  "balochistan", "balochistan", "answer",
  ["No one may engage in private money lending in Balochistan; it is punishable with up to ten years, a fine of up "
   "to one million rupees, or both, doubled on a later conviction."],
  necessary=[(LEND_BL, "3", 3), (LEND_BL, "4", 3)],
  check=[r"private money lending in the Province of Balochistan", r"one million rupees"])
c("S9-C05", "citizen", "F9-lender-molestation-punjab", "money", ["en"], "latin",
  "A lender's men in Faisalabad keep threatening me at my door to make me pay. What does the law say?",
  "Molesting a borrower to force repayment", "punjab", "punjab", "answer",
  ["Molesting a borrower to force repayment of a loan or interest is punishable with up to five years and a fine of "
   "up to five hundred thousand rupees."],
  necessary=[(INT_PB, "5", 3)], check=[r"molests any borrower", r"five years"])
c("S9-C06", "citizen", "F9-guarantor-liability", "money", ["en"], "latin",
  "I signed as guarantor for my friend's loan in Karachi. If he doesn't pay, how much can be claimed from me?",
  "Contract of guarantee and the surety's liability", "fed", "sindh", "answer",
  ["A guarantee is a promise to discharge a third person's liability on his default; unless the contract says "
   "otherwise, the surety's liability is co-extensive with the principal debtor's."],
  necessary=[(CA, "128", 3)], relevant=[(CA, "126", 2)], check=[r"co-extensive with that of the principal debtor"])
c("S9-C07", "citizen", "F9-bailee-care", "money", ["en"], "latin",
  "I left my car at a workshop in Islamabad and they damaged it through carelessness. Are they responsible?",
  "The care a bailee must take", "fed", "ict", "answer",
  ["A bailee must take as much care of the goods as a man of ordinary prudence would of his own goods of the same "
   "bulk, quality and value."],
  necessary=[(CA, "151", 3)], check=[r"man of ordinary prudence"])
c("S9-C08", "citizen", "F9-pledge", "money", ["en"], "latin",
  "I handed my gold to a jeweller in Mardan as security for a loan. What is that arrangement called in law?",
  "Pledge", "fed", "kp", "answer",
  ["Bailment of goods as security for a debt is a pledge; the bailor is the pawnor and the bailee the pawnee."],
  necessary=[(CA, "172", 3)], check=[r"security for payment of a debt", r"pawnee"])
c("S9-C09", "citizen", "F9-agent-personal-liability", "money", ["en"], "latin",
  "A property dealer in Hyderabad signed a deal for the owner he represented. Can I sue the dealer personally?",
  "An agent is not personally bound by contracts made for his principal", "fed", "sindh", "conditional",
  ["Absent a contract to that effect, an agent can neither personally enforce nor be bound by contracts made for "
   "his principal, save the presumed cases the section lists."],
  necessary=[(CA, "230", 3)], omitted=["the contract's terms"], check=[r"agent cannot personally enforce"])
c("S9-C10", "citizen", "F9-passing-of-property", "money", ["en"], "latin",
  "I bought a particular sofa set in Karachi to collect next week, paying later. Whose is it now?",
  "Property in specific goods passes when the contract is made", "fed", "sindh", "answer",
  ["In an unconditional contract for specific goods in a deliverable state, property passes to the buyer when the "
   "contract is made, even if payment or delivery is postponed."],
  necessary=[(SOG, "20", 3)], check=[r"property in the goods passes to the buyer when the contract is made"])
c("S9-C11", "citizen", "F9-unpaid-seller", "money", ["en"], "latin",
  "The buyer's cheque for my goods in Islamabad bounced, but the goods are still in my store. Can I keep them?",
  "The unpaid seller and his lien", "fed", "ict", "answer",
  ["A seller is unpaid where a cheque taken as conditional payment is dishonoured; while in possession he has a lien "
   "on the goods for the price."],
  necessary=[(SOG, "45", 3), (SOG, "46", 3)], check=[r"dishonour of the instrument", r"lien on the goods"])
c("S9-C12", "citizen", "F9-partnership-at-will", "money", ["en"], "latin",
  "Our business partnership in Peshawar has no fixed term. How can I leave it?",
  "Dissolution of a partnership at will by notice", "fed", "kp", "answer",
  ["A partnership at will is dissolved by any partner's written notice to all the others, from the date in the "
   "notice or, if none, from its communication."],
  necessary=[(PA, "43", 3)], check=[r"notice in writing to all the other partners"])
c("S9-C13", "citizen", "F9-partner-death", "money", ["en"], "latin",
  "My business partner in Sukkur died. Is our firm automatically over?", "Dissolution on a partner's death",
  "fed", "sindh", "conditional",
  ["Subject to the partners' contract, a firm is dissolved by the death of a partner."],
  necessary=[(PA, "42", 3)], omitted=["the partnership deed"], check=[r"by the death of a partner"])
c("S9-C14", "citizen", "F9-insurance-claim-delay", "money", ["en"], "latin",
  "My late father's life insurance claim in Rawalpindi has been pending for five months after we gave every "
  "document. What can we claim?", "Liquidated damages for late settlement of claims", "fed", "punjab", "answer",
  ["If an insurer fails to pay within ninety days of the claim falling due and complete papers being filed, it must "
   "pay liquidated damages on the amount, as the section provides."],
  necessary=[(INS, "118", 3)], check=[r"ninety days", r"liquidated damages"])
c("S9-C15", "citizen", "F9-lender-harassment-sindh", "money", ["en"], "latin",
  "A private lender in Karachi keeps harassing me and my family to pay back with interest. Is that a crime?",
  "Harassing a borrower to force repayment in Sindh", "sindh", "sindh", "answer",
  ["Harassing a borrower to force repayment of a loan or interest is punishable with up to five years and a fine of "
   "up to five hundred thousand rupees."],
  necessary=[(INT_SD, "5", 3)], check=[r"harasses any borrower", r"five years"])
c("S9-C16", "citizen", "F9-insurance-ombudsman", "money", ["en"], "latin",
  "The insurance company in Islamabad keeps losing my papers and ignoring me. Is there an ombudsman?",
  "The Insurance Ombudsman's jurisdiction", "fed", "ict", "answer",
  ["The Insurance Ombudsman may, on a complaint, investigate allegations of mal-administration by an insurance "
   "company (save matters within the Wafaqi Mohtasib's jurisdiction)."],
  necessary=[(INS, "127", 3)], check=[r"mal-administration"])
c("S9-C17", "citizen", "F9-price-fixing", "money", ["en"], "latin",
  "All the cement makers in Punjab raised prices by the same amount on the same day. Is that legal?",
  "Prohibited agreements such as price fixing", "fed", "punjab", "conditional",
  ["Undertakings may not agree, or an association decide, to prevent, restrict or reduce competition, including by "
   "fixing purchase or selling prices, unless exempted."],
  necessary=[(COMP, "4", 3)], omitted=["whether there was an agreement or decision"],
  check=[r"preventing, restricting, or reducing competition", r"fixing the purchase or selling pr"])
c("S9-C18", "citizen", "F9-deceptive-marketing", "money", ["en"], "latin",
  "A company in Karachi advertises its water filter as removing all disease, which is false. Is that unlawful?",
  "Deceptive marketing practices", "fed", "sindh", "answer",
  ["No undertaking may engage in deceptive marketing, including distributing false or misleading information to "
   "consumers about a product's character or properties."],
  necessary=[(COMP, "10", 3)], check=[r"false or misleading information to consumers"])
c("S9-C19", "citizen", "F9-electronic-contract", "money", ["en"], "latin",
  "We agreed a supply deal by email in Abbottabad and never signed paper. Is it valid?",
  "Legal recognition of electronic documents and writing", "fed", "kp", "answer",
  ["A document or transaction may not be denied recognition or enforceability because it is electronic, and a legal "
   "requirement of writing is met by an electronic form accessible for later reference."],
  necessary=[(ETO, "3", 3)], relevant=[(ETO, "4", 3)], check=[r"electronic form"])
c("S9-C20", "citizen", "F9-bank-refuses-cheque", "money", ["en"], "latin",
  "My bank in Islamabad refused to pay my cheque though I had enough money in my account. Is the bank liable?",
  "The drawee bank's liability", "fed", "ict", "answer",
  ["A drawee bank holding sufficient funds of the drawer must pay the cheque when duly required and, in default, "
   "compensate the drawer for the loss caused."],
  necessary=[(NIA, "31", 3)], check=[r"must compensate the drawer"])

# ---------------------------------------------------------------- professional lookups (12)
c("S9-P01", "professional", "F9-indemnity", "money", ["en"], "latin",
  "Definition of a contract of indemnity", "Section 124 Contract Act, 1872", "fed", "sindh", "answer",
  ["A contract by which one party promises to save the other from loss caused by the promisor's conduct or anyone "
   "else's."],
  necessary=[(CA, "124", 3)], check=[r"save the other from loss"])
c("S9-P02", "professional", "F9-agent-definition", "money", ["en"], "latin",
  "Definition of agent and principal", "Section 182 Contract Act, 1872", "fed", "kp", "answer",
  ["An agent is a person employed to do any act for another or to represent another in dealings with third persons; "
   "that other is the principal."],
  necessary=[(CA, "182", 3)], check=[r"employed to do any act for another"])
c("S9-P03", "professional", "F9-bailment-definition", "money", ["en"], "latin",
  "Definition of bailment", "Section 148 Contract Act, 1872", "fed", "ict", "answer",
  ["Bailment is delivery of goods for a purpose on a contract that they be returned or disposed of as directed when "
   "the purpose is accomplished."],
  necessary=[(CA, "148", 3)], check=[r"delivery of goods by one person to another"])
c("S9-P04", "professional", "F9-abuse-dominance", "money", ["en"], "latin",
  "Abuse of dominant position", "Section 3 Competition Act, 2010", "fed", "ict", "answer",
  ["No person may abuse a dominant position; practices preventing, restricting, reducing or distorting competition, "
   "such as unreasonable price increases or price discrimination, are abuse."],
  necessary=[(COMP, "3", 3)], check=[r"abuse dominant position", r"price discrimination"])
c("S9-P05", "professional", "F9-competition-appellate-bench", "money", ["en"], "latin",
  "Appeal against an order of a single Member of the Competition Commission", "Section 41 Competition Act, 2010",
  "fed", "ict", "answer",
  ["An appeal lies to an Appellate Bench of at least two Members within thirty days of the order."],
  necessary=[(COMP, "41", 3)], check=[r"within thirty days of the passing of the order"])
c("S9-P06", "professional", "F9-electronic-signature", "money", ["en"], "latin",
  "Legal recognition of electronic signatures", "Section 7 Electronic Transactions Ordinance, 2002", "fed",
  "sindh", "answer",
  ["A legal requirement to sign is satisfied by an electronic or advanced electronic signature."],
  necessary=[(ETO, "7", 3)], check=[r"electronic signatures or advanced electronic signature"])
c("S9-P07", "professional", "F9-notice-of-dishonour", "money", ["en"], "latin",
  "Who must give notice of dishonour, and to whom?", "Section 93 Negotiable Instruments Act, 1881", "fed",
  "sindh", "answer",
  ["On dishonour by non-acceptance or non-payment, the holder or a party still liable must give notice of dishonour "
   "to every party he seeks to make severally liable."],
  necessary=[(NIA, "93", 3)], check=[r"notice that the instrument has been so dishonoured"])
c("S9-P08", "professional", "F9-cheque-presentment-delay", "money", ["en"], "latin",
  "Effect of not presenting a cheque within a reasonable time", "Section 84 Negotiable Instruments Act, 1881",
  "fed", "kp", "answer",
  ["If a cheque is not presented within a reasonable time and the drawer suffers actual damage through the delay, "
   "he is discharged to the extent of that damage."],
  necessary=[(NIA, "84", 3)], check=[r"reasonable time of its issue"])
c("S9-P09", "professional", "F9-llp-minimum-partners", "money", ["en"], "latin",
  "Minimum number of partners in an LLP", "Section 9 Limited Liability Partnership Act, 2017", "fed", "ict",
  "answer",
  ["At least two; a sole partner who carries on business for more than six months after the number falls below two "
   "becomes liable as the section provides."],
  necessary=[(LLP, "9", 3)], check=[r"at least two partners"])
c("S9-P10", "professional", "F9-llp-offence", "money", ["en"], "latin",
  "Liability for breaching the LLP partner requirements", "Section 11 Limited Liability Partnership Act, 2017",
  "fed", "sindh", "answer",
  ["The LLP and every designated partner commit an offence punishable with a fine of up to one million rupees."],
  necessary=[(LLP, "11", 3)], check=[r"one million rupees", r"designated partner"])
c("S9-P11", "professional", "F9-interest-loan-ict", "money", ["en"], "latin",
  "Prohibition of private interest-based lending in Islamabad", "Section 3 ICT Prohibition of Interest of Private "
  "Loans Act, 2023", "fed", "ict", "answer",
  ["No money lender may lend for interest or carry on an interest-based transaction in the Islamabad Capital "
   "Territory; punishable with three to ten years and a fine."],
  necessary=[(INT_ICT, "3", 3)], check=[r"interest based transaction in the Islamabad Capital Territory"])
c("S9-P12", "professional", "F9-unpaid-seller-rights", "money", ["en"], "latin",
  "Rights of an unpaid seller against the goods", "Section 46 Sale of Goods Act, 1930", "fed", "balochistan",
  "answer",
  ["A lien while in possession, stoppage in transit on the buyer's insolvency, and a limited right of re-sale, even "
   "after property has passed."],
  necessary=[(SOG, "46", 3)], check=[r"lien on the goods", r"right of re-sale"])

# ---------------------------------------------------------------- procedural (8)
c("S9-R01", "procedural", "F9-interest-complaint-ict", "money", ["en"], "latin",
  "How do I report a private interest lender in Islamabad?", "Complaint to a justice of the peace", "fed", "ict",
  "answer",
  ["A justice of the peace, within three days of receiving the complaint, orders the local police to register a "
   "case."],
  necessary=[(INT_ICT, "6", 3)], check=[r"within three days", r"justice of peace"])
c("S9-R02", "procedural", "F9-interest-complaint-punjab", "money", ["en"], "latin",
  "Where do I complain about a lender charging interest in Gujranwala?", "Complaint under the Punjab Act", "punjab",
  "punjab", "answer",
  ["To a justice of the peace, who within three days orders the local police to register a case."],
  necessary=[(INT_PB, "6", 3)], check=[r"within three days", r"register a case"])
c("S9-R03", "procedural", "F9-interest-complaint-kp", "money", ["en"], "latin",
  "How is a case against a private interest lender started in Swat?", "Complaint under the KP Act", "kp", "kp",
  "answer",
  ["A justice of the peace orders the local police to register a case within three days of the complaint."],
  necessary=[(INT_KP, "6", 3)], must_not_serve=[(INT_PB, "6")], check=[r"within three days"])
c("S9-R04", "procedural", "F9-court-reference-ombudsman", "money", ["en"], "latin",
  "Can the court hearing my insurance case in Karachi send the matter to the Insurance Ombudsman?",
  "Reference to the Insurance Ombudsman by a court", "fed", "sindh", "answer",
  ["A court or tribunal that finds the insurer's management prima facie acted mala fide or against the rules may "
   "refer the matter to the Insurance Ombudsman."],
  necessary=[(INS, "128", 3)], check=[r"make reference to the Insurance Ombudsman"])
c("S9-R05", "procedural", "F9-competition-tribunal-appeal", "money", ["en"], "latin",
  "How long do I have to appeal an order of the Competition Commission's Appellate Bench?",
  "Appeal to the Competition Appellate Tribunal", "fed", "ict", "answer",
  ["Within sixty days of the communication of the order, to the Competition Appellate Tribunal."],
  necessary=[(COMP, "42", 3)], check=[r"sixty days", r"Competition Appellate Tribunal"])
c("S9-R06", "procedural", "F9-competition-penalty", "money", ["en"], "latin",
  "Before the Competition Commission fines my company in Lahore, must it hear us?", "Penalty after a hearing",
  "fed", "punjab", "answer",
  ["The Commission may order a penalty only after giving the undertaking an opportunity of being heard."],
  necessary=[(COMP, "38", 3)], check=[r"opportunity of being heard"])
c("S9-R07", "procedural", "F9-partnership-fixed-term", "money", ["en"], "latin",
  "Our partnership in Karachi was for five years, which have now passed. Is the firm dissolved?",
  "Dissolution on expiry of a fixed term", "fed", "sindh", "conditional",
  ["Subject to the partners' contract, a firm constituted for a fixed term is dissolved by the expiry of that term."],
  necessary=[(PA, "42", 3)], omitted=["whether the partners carried on afterwards"],
  check=[r"by the expiry of that term"])
c("S9-R08", "procedural", "F9-insurance-nomination", "money", ["en"], "latin",
  "How do I make sure my life insurance money in Karachi goes to my wife if I die?",
  "Nomination by the policy holder", "fed", "sindh", "answer",
  ["The holder of a policy on his own life may, when taking it or before it matures, nominate the person to be paid "
   "on his death (and appoint someone to receive for a minor nominee)."],
  necessary=[(INS, "72", 3)], check=[r"nominate the person"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5)
c("S9-U01", "urdu", "F9-interest-loan-punjab", "money", ["ur-Latn"], "roman_urdu",
  "Lahore mein ek shakhs logon ko sood par qarz deta hai, kya yeh jurm hai?",
  "Private interest lending in Punjab (Roman Urdu variant of S9-C01)", "punjab", "punjab", "answer",
  ["Yes: three to ten years and a fine."], necessary=[(INT_PB, "3", 3)], must_not_serve=[(INT_KP, "3")],
  check=[r"receiving interest thereon"])
c("S9-U02", "urdu", "F9-insurance-claim-delay", "money", ["ur"], "arabic",
  "انشورنس کمپنی کاغذات مکمل ہونے کے باوجود کئی مہینوں سے میرا کلیم ادا نہیں کر رہی، قانون کیا کہتا ہے؟",
  "A delayed insurance claim (Urdu variant of S9-C14)", "fed", "punjab", "answer",
  ["After ninety days the insurer owes liquidated damages."], necessary=[(INS, "118", 3)],
  check=[r"ninety days"])
c("S9-U03", "urdu", "F9-guarantor-liability", "money", ["ur-Latn"], "roman_urdu",
  "Mein dost ke qarz ka zamin bana hoon, agar woh ada na kare to mujh se kitna wasool ho sakta hai?",
  "A guarantor's liability (Roman Urdu variant of S9-C06)", "fed", "sindh", "answer",
  ["As much as the principal debtor owes, unless the contract limits it."], necessary=[(CA, "128", 3)],
  check=[r"co-extensive"])
c("S9-U04", "urdu", "F9-bank-refuses-cheque", "money", ["ur-Latn"], "roman_urdu",
  "Bank ne mere account mein paise hone ke bawajood mera cheque wapas kar diya, kya bank zimmedar hai?",
  "A bank refusing a funded cheque (Roman Urdu variant of S9-C20)", "fed", "ict", "answer",
  ["Yes: it must compensate the drawer for the loss."], necessary=[(NIA, "31", 3)],
  check=[r"compensate the drawer"])
c("S9-U05", "urdu", "F9-electronic-contract", "money", ["ur-Latn"], "roman_urdu",
  "Kya email par kiya gaya karobari muahida qanooni tor par jaiz hai?",
  "An email contract (Roman Urdu variant of S9-C19)", "fed", "kp", "answer",
  ["Yes: it is not denied effect for being electronic."], necessary=[(ETO, "3", 3)], check=[r"electronic form"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S9-X01", "unanswerable", "F9-x-policy-rate", "money", ["en"], "latin",
  "What is the State Bank's policy rate today?", "A live market figure", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["quoting a rate"],
                  why="a current rate is not statute"))
c("S9-X02", "unanswerable", "F9-x-investment-advice", "money", ["en"], "latin",
  "Should I invest my savings in gold or in shares this year?", "Investment advice", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["recommending"],
                  why="not a question of law"))
c("S9-X03", "unanswerable", "F9-x-uae-company", "money", ["en"], "latin",
  "What are the requirements to register a company in the UAE?", "Foreign company law", "foreign", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from the Companies Act, 2017"], why="the corpus is Pakistani law only"))
c("S9-X04", "unanswerable", "F9-x-company-records", "money", ["en"], "latin",
  "Is ABC Traders (Private) Limited registered with the SECP, and who are its directors?", "A registry lookup",
  "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[], unsafeAlternatives=["guessing"],
                  why="the companies register is not in the corpus"))
c("S9-X05", "unanswerable", "F9-x-cartel-decision", "money", ["en"], "latin",
  "What did the Competition Appellate Tribunal decide in the cement cartel case?", "A tribunal's decision", "fed",
  None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["answering from section 4 as if it were the decision"],
                  why="decisions are not in the corpus (D-100)"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 9: commerce, money and private lending -- the interest bans by place, guarantee, "
                              "bailment, pledge, agency, sale of goods, partnership, LLPs, insurance, competition, "
                              "electronic transactions and cheques."))
