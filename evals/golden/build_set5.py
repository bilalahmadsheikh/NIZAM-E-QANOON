"""Build golden-pk-v1 draft SET 5 (50 cases): property and land.

Sale, mortgage, lease, gift and exchange under the Transfer of Property Act; registration and its time limits; stamp
duty and admissibility; easements and licences; cancellation of instruments; the record-of-rights, revenue appeals
and the computerised land record in Punjab; agricultural tenancy; urban property tax; and the women's property
rights Acts of Islamabad, KP and Punjab (an Ombudsperson's remedy, each confined to its own territory -- the ICT Act
is a trap for a Punjab question).

Federal codes that Punjab and KP also print as their own copies (PROVINCIAL_COPY) are asked in Sindh or Islamabad, so
each case has one text. Stage A0 + A3 by the lead (claude), 20 Nov 2026; propositions written from the held text
(peek.py) and re-verified by each case's `check` regexes at every build. Not gold until A1/A2 (evals/golden/README.md).

    python evals/golden/build_set5.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_common import CaseSet, build  # noqa: E402

S = CaseSet("set5")
c = S.case
TPA, REG, STAMP, EAS, SRA = 3991, 3876, 4345, 3951, 3944
PLRA67, PLRA17, PTA, PUIPT = 4389, 6367, 3974, 4045
WPR_ICT, WPR_KP, WPR_PB = 3212, 4256, 2442

# ---------------------------------------------------------------- citizen scenarios (20)
c("S5-C01", "citizen", "F5-women-property-punjab", "property", ["en"], "latin",
  "My brothers in Lahore will not give me my share of our late father's house. Is there anyone other than a court "
  "I can go to?", "A woman deprived of her property may complain to the Punjab Ombudsperson", "punjab", "punjab",
  "answer",
  ["A woman deprived of ownership or possession of her property by any means may complain to the Ombudsperson if no "
   "court proceedings about that property are pending; if the Ombudsperson finds she was illegally deprived, the "
   "Deputy Commissioner or others are directed to restore possession or title."],
  necessary=[(WPR_PB, "4", 3)], relevant=[(WPR_PB, "5", 2)], must_not_serve=[(WPR_ICT, "4")],
  check=[r"deprived of ownership or possession", r"no proceedings in a court of law are pending"])
c("S5-C02", "citizen", "F5-women-property-ict", "property", ["en"], "latin",
  "My uncle has occupied the plot in Islamabad I inherited from my mother. What can I do as a woman without filing "
  "a suit?", "The ICT Ombudsman's remedy for a woman deprived of property", "fed", "ict", "answer",
  ["She may complain to the Ombudsman if no court case about the property is pending; on finding illegal "
   "deprivation the Ombudsman directs the Deputy Commissioner or others to restore possession or title, and may "
   "order the person who deprived her to pay the market rent for the period."],
  necessary=[(WPR_ICT, "4", 3)], relevant=[(WPR_ICT, "5", 2), (WPR_ICT, "8", 2)],
  check=[r"file a complaint to the Ombudsman", r"no proceedings in a court of law are pending"])
c("S5-C03", "citizen", "F5-women-property-kp-appeal", "property", ["en"], "latin",
  "The Ombudsperson in Peshawar ordered my brothers to hand over my share of the land. Can they challenge the "
  "order, and by when?", "Appeal from the KP women's property Ombudsperson", "kp", "kp", "answer",
  ["A person aggrieved by the Ombudsperson's order may appeal to the Peshawar High Court within forty-five days of "
   "the order."],
  necessary=[(WPR_KP, "8", 3)], check=[r"forty five", r"Peshawar High Court"])
c("S5-C04", "citizen", "F5-seller-defect", "property", ["en"], "latin",
  "I bought a house in Karachi and found the seller hid that the foundations are cracked. Did he have a duty to "
  "tell me?", "The seller's duty to disclose material defects", "fed", "sindh", "conditional",
  ["Unless the contract says otherwise, the seller must disclose any material defect in the property or in his "
   "title that he knows of and the buyer does not and could not discover with ordinary care."],
  necessary=[(TPA, "55", 3)], omitted=["what the contract says", "whether the defect was discoverable"],
  check=[r"disclose to the buyer any material defect", r"ordinary care"])
c("S5-C05", "citizen", "F5-oral-sale", "property", ["en"], "latin",
  "I paid the full price for a house in Hyderabad and the seller gave me the keys, but nothing was written or "
  "registered. Do I own it?", "Sale of immovable property only by registered instrument", "fed", "sindh", "answer",
  ["A sale of tangible immovable property worth one hundred rupees or more can be made only by a registered "
   "instrument; delivery alone transfers ownership only below that value."],
  necessary=[(TPA, "54", 3)], relevant=[(REG, "17", 2)], check=[r"only by a registered instrument",
                                                                  r"one hundred rupees"])
c("S5-C06", "citizen", "F5-unregistered-deed", "property", ["en"], "latin",
  "We signed a written sale deed for a plot in Islamabad but never registered it. Does it give me any right in the "
  "plot?", "Effect of not registering a document that must be registered", "fed", "ict", "answer",
  ["A document that must be registered does not create, assign or extinguish any right, title or interest in "
   "immovable property unless it has been registered."],
  necessary=[(REG, "49", 3)], relevant=[(TPA, "54", 2)], check=[r"unless it has been registered",
                                                                  r"right, title or interest"])
c("S5-C07", "citizen", "F5-redeem-mortgage", "property", ["en"], "latin",
  "I mortgaged my house in Karachi for a loan. Now I want to repay it. What must the lender do when I pay?",
  "The mortgagor's right to redeem", "fed", "sindh", "answer",
  ["Once the money is due, on paying or tendering it the mortgagor may require the mortgagee to deliver up the "
   "mortgage-deed and documents, to give back possession if he holds it, and to re-transfer the property."],
  necessary=[(TPA, "60", 3)], check=[r"right, on payment or tender", r"deliver possession thereof"])
c("S5-C08", "citizen", "F5-mortgage-sale", "property", ["en"], "latin",
  "I could not repay the loan secured on my shop in Sukkur. Can the lender just sell the shop himself?",
  "The mortgagee's remedy is a court decree for foreclosure or sale", "fed", "sindh", "conditional",
  ["Unless the contract provides otherwise, after the money is due the mortgagee's right is to obtain from the "
   "Court a decree debarring redemption or a decree that the property be sold."],
  necessary=[(TPA, "67", 3)], omitted=["the kind of mortgage", "the contract's terms"],
  check=[r"right to obtain from the Court", r"property be sold"])
c("S5-C09", "citizen", "F5-oral-lease", "property", ["en"], "latin",
  "My landlord in Thatta agreed by word of mouth to lease me his farmland for three years. Is that lease valid?",
  "A lease for more than a year needs a registered instrument", "fed", "sindh", "answer",
  ["A lease from year to year, for a term exceeding one year or reserving a yearly rent can be made only by a "
   "registered instrument; other leases may be oral with delivery of possession."],
  necessary=[(TPA, "107", 3)], check=[r"exceeding one year", r"only by a registered instrument"])
c("S5-C10", "citizen", "F5-property-tax-punjab", "money", ["en"], "latin",
  "Do I have to pay property tax on my house in Lahore?", "Levy of urban immovable property tax in Punjab",
  "punjab", "punjab", "conditional",
  ["Property tax is levied on the taxable value of buildings and land in rating areas the Government notifies, at "
   "the rate in the Schedule (local councils may set a higher rate)."],
  necessary=[(PUIPT, "3", 3)], relevant=[(PUIPT, "4", 2)], omitted=["whether the area is a notified rating area"],
  check=[r"taxable value of a building and land", r"rating area"])
c("S5-C11", "citizen", "F5-right-of-way-prescription", "property", ["en"], "latin",
  "For 25 years I have walked across my neighbour's land in Larkana to reach the road. Now he has put up a wall. "
  "Do I have a right of way?", "Acquiring an easement by prescription", "fed", "sindh", "conditional",
  ["A right of way peaceably and openly enjoyed as an easement, as of right and without interruption, for twenty "
   "years is acquired by prescription."],
  necessary=[(EAS, "15", 3)], omitted=["whether the use was as of right and uninterrupted"],
  check=[r"twenty years", r"peaceably and openly enjoyed"])
c("S5-C12", "citizen", "F5-easement-necessity", "property", ["en"], "latin",
  "I bought a plot from a man whose land surrounds it on every side. There is no way to reach my plot except over "
  "his land. Can he refuse me passage?", "Easement of necessity on a transfer", "fed", "sindh", "answer",
  ["Where a transferor's other land must be crossed to enjoy the property transferred, the transferee is entitled "
   "to the easement of necessity."],
  necessary=[(EAS, "13", 3)], check=[r"necessary for enjoying the subject of the transfer"])
c("S5-C13", "citizen", "F5-licence-revoke", "property", ["en"], "latin",
  "I let a friend run a tea stall on my land in Islamabad. Can I take back the permission?",
  "A licence and when it may be revoked", "fed", "ict", "conditional",
  ["A permission to do something on another's land that is not an easement or interest is a licence; the grantor "
   "may revoke it unless it is coupled with a transfer in force, or the licensee has built a permanent work at "
   "expense acting on it."],
  necessary=[(EAS, "60", 3)], relevant=[(EAS, "52", 2)], omitted=["whether a permanent structure was built"],
  check=[r"may be revoked by the grantor", r"permanent character"])
c("S5-C14", "citizen", "F5-fard-wrong-entry", "property", ["en"], "latin",
  "The fard (land record) in Sheikhupura shows someone else's name on land I possess. What can I do?",
  "A suit for declaration against a wrong entry; corrections before the Revenue Officer", "punjab", "punjab",
  "answer",
  ["A person in possession aggrieved by an entry in the record-of-rights may sue for a declaration of his right "
   "under the Specific Relief Act; correction of an entry, other than declaring a right, is pursued before the "
   "Revenue Officer."],
  necessary=[(PLRA67, "53", 3)], relevant=[(PLRA67, "52", 2)],
  check=[r"suit for a declaration", r"pursued before the Revenue Officer"])
c("S5-C15", "citizen", "F5-revenue-appeal-punjab", "property", ["en"], "latin",
  "The Assistant Collector in Okara rejected my land application. Where do I appeal and how long do I have?",
  "Appeals from revenue officers in Punjab and their limitation", "punjab", "punjab", "answer",
  ["An appeal from an Assistant Collector's order lies to the Collector, and must be filed within thirty days of "
   "the order."],
  necessary=[(PLRA67, "161", 3), (PLRA67, "162", 3)], check=[r"to the Collector", r"thirty days"])
c("S5-C16", "citizen", "F5-computerised-fard", "property", ["en"], "latin",
  "I got a computerised fard from the Arazi Record Centre in Multan. Is it good proof of ownership?",
  "Presumption of truth of the Punjab land records", "punjab", "punjab", "answer",
  ["The land records the Authority maintains, computerised ones included, are presumed true until the contrary is "
   "proved or a new entry is lawfully substituted."],
  necessary=[(PLRA17, "16", 3)], relevant=[(PLRA17, "17", 1)],
  check=[r"presumed to be true until the contrary is proved"])
c("S5-C17", "citizen", "F5-unstamped-agreement", "property", ["en"], "latin",
  "I have a sale agreement for a plot in Karachi written on plain paper with no stamp. Can the court still rely on "
  "it?", "Unstamped instruments in evidence", "fed", "sindh", "answer",
  ["An instrument chargeable with duty is not admitted in evidence unless duly stamped, but subject to exceptions "
   "it may be admitted on payment of the duty and a penalty."],
  necessary=[(STAMP, "35", 3)], check=[r"unless such instrument is duly stamped", r"on payment of the dut"])
c("S5-C18", "citizen", "F5-coowner-sale", "property", ["en"], "latin",
  "My cousin, who owns the house in Quetta jointly with me, sold his share to a stranger. What rights does the "
  "buyer get?", "Transfer by one co-owner", "fed", "balochistan", "answer",
  ["The buyer of a co-owner's share takes the seller's right to joint possession or common enjoyment and to enforce "
   "a partition, subject to the conditions affecting the share."],
  necessary=[(TPA, "44", 3)], check=[r"right to joint possession", r"enforce a partition"])
c("S5-C19", "citizen", "F5-sell-expected-inheritance", "property", ["en"], "latin",
  "Can I sell now the share I expect to inherit from my father's land in Hyderabad?",
  "The chance of an heir-apparent cannot be transferred", "fed", "sindh", "answer",
  ["The chance of an heir-apparent succeeding to an estate, or any mere possibility of that kind, cannot be "
   "transferred."],
  necessary=[(TPA, "6", 3)], check=[r"chance of an heir-apparent", r"cannot be transferred"])
c("S5-C20", "citizen", "F5-tenant-eject-punjab", "property", ["en"], "latin",
  "The landowner in Bahawalpur threw me off the land I have cultivated as his tenant for years, without going to "
  "court. What can I do?", "No ejectment of an agricultural tenant without a decree; suit for possession",
  "punjab", "punjab", "conditional",
  ["A tenant may not be ejected otherwise than in execution of a decree, save in listed cases; a tenant "
   "dispossessed without consent may sue to recover possession within one year of dispossession."],
  necessary=[(PTA, "42", 3), (PTA, "50", 3)], omitted=["the tenancy's terms", "any decree for arrears"],
  check=[r"otherwise than in execution of a decree", r"within one year"])

# ---------------------------------------------------------------- professional lookups (12)
c("S5-P01", "professional", "F5-compulsory-registration", "property", ["en"], "latin",
  "Documents of which registration is compulsory", "Section 17 Registration Act, 1908", "fed", "sindh", "answer",
  ["Instruments of gift of immovable property, and other non-testamentary instruments creating, declaring, "
   "assigning, limiting or extinguishing a right in immovable property, among others, must be registered."],
  necessary=[(REG, "17", 3)], check=[r"instruments of gift of immoveable property", r"non.testamentary"])
c("S5-P02", "professional", "F5-registration-time", "deadline", ["en"], "latin",
  "Time limit for presenting a document for registration", "Section 23 Registration Act, 1908", "fed", "sindh",
  "answer",
  ["A document other than a will must be presented within four months of its execution (a decree copy within four "
   "months of the decree or of its becoming final)."],
  necessary=[(REG, "23", 3)], check=[r"within four months from the date of its execution"])
c("S5-P03", "professional", "F5-registration-delay-fine", "deadline", ["en"], "latin",
  "Registration after the four-month period because of unavoidable delay", "Section 25 Registration Act, 1908",
  "fed", "sindh", "answer",
  ["Where delay from urgent necessity or unavoidable accident does not exceed four months, the Registrar may accept "
   "the document on a fine of up to ten times the registration fee."],
  necessary=[(REG, "25", 3)], check=[r"unavoidable accident", r"ten times the amount"])
c("S5-P04", "professional", "F5-registration-place", "property", ["en"], "latin",
  "Office where a document affecting land must be registered", "Section 28 Registration Act, 1908", "fed", "ict",
  "answer",
  ["It is presented to the Sub-Registrar of the sub-district in which the whole or part of the property lies."],
  necessary=[(REG, "28", 3)], check=[r"Sub-Registrar within whose sub-district"])
c("S5-P05", "professional", "F5-registration-relation-back", "property", ["en"], "latin",
  "From when does a registered document operate?", "Section 47 Registration Act, 1908", "fed", "sindh", "answer",
  ["From the time it would have operated without registration, not from the time of registration."],
  necessary=[(REG, "47", 3)], check=[r"not from the time of its registration"])
c("S5-P06", "professional", "F5-gift-formalities", "property", ["en"], "latin",
  "Formalities for a gift of immovable property under the Transfer of Property Act",
  "Sections 122-123 and the Muslim-law saving in section 129", "fed", "sindh", "answer",
  ["A gift of immovable property must be made by a registered instrument signed by the donor and attested by at "
   "least two witnesses; acceptance must be in the donor's lifetime. The Chapter does not affect any rule of Muslim "
   "law."],
  necessary=[(TPA, "123", 3)], relevant=[(TPA, "122", 2), (TPA, "129", 3)],
  check=[r"registered instrument signed by or on behalf of the donor", r"two witnesses"])
c("S5-P07", "professional", "F5-gift-revocation", "property", ["en"], "latin",
  "When may a gift be revoked?", "Section 126 Transfer of Property Act, 1882", "fed", "ict", "answer",
  ["A gift may be suspended or revoked on an agreed event not dependent on the donor's will, or in cases where a "
   "contract could be rescinded; a gift revocable at the donor's mere will is void to that extent."],
  necessary=[(TPA, "126", 3)], check=[r"mere will of the donor", r"cannot be revoked"])
c("S5-P08", "professional", "F5-restraint-alienation", "property", ["en"], "latin",
  "Validity of a condition absolutely restraining alienation", "Section 10 Transfer of Property Act, 1882", "fed",
  "sindh", "answer",
  ["A condition absolutely restraining the transferee from disposing of his interest is void, except in a lease "
   "where it benefits the lessor."],
  necessary=[(TPA, "10", 3)], check=[r"condition or limitation is void", r"except in the case of a lease"])
c("S5-P09", "professional", "F5-ostensible-owner", "property", ["en"], "latin",
  "Protection of a transferee from an ostensible owner", "Section 41 Transfer of Property Act, 1882", "fed",
  "sindh", "answer",
  ["A transfer for consideration by an ostensible owner holding with the consent of those interested is not "
   "voidable for want of authority, if the transferee took reasonable care and acted in good faith."],
  necessary=[(TPA, "41", 3)], check=[r"ostensible owner", r"acted in good faith"])
c("S5-P10", "professional", "F5-lease-notice", "property", ["en"], "latin",
  "Default duration and notice for a lease with no written contract", "Section 106 Transfer of Property Act, 1882",
  "fed", "ict", "answer",
  ["Absent contract, local law or usage, an agricultural or manufacturing lease is from year to year, ended by six "
   "months' notice; any other lease is from month to month, ended by fifteen days' notice expiring with a month of "
   "the tenancy."],
  necessary=[(TPA, "106", 3)], check=[r"six months' notice", r"fifteen days"])
c("S5-P11", "professional", "F5-mortgage-kinds", "property", ["en"], "latin",
  "Definition and kinds of mortgage", "Sections 58-59 Transfer of Property Act, 1882", "fed", "sindh", "answer",
  ["A mortgage transfers an interest in specific immovable property to secure a loan, debt or engagement; the kinds "
   "include simple, conditional sale, usufructuary, English and by deposit of title-deeds. A mortgage securing one "
   "hundred rupees or more (other than by deposit of title-deeds) needs a registered instrument attested by two "
   "witnesses."],
  necessary=[(TPA, "58", 3)], relevant=[(TPA, "59", 2)],
  check=[r"transfer of an interest in specific immoveable property", r"deposit of title-deeds"])
c("S5-P12", "professional", "F5-cancellation-instrument", "property", ["en"], "latin",
  "Suit for cancellation of a void or voidable instrument", "Section 39 Specific Relief Act, 1877", "fed", "sindh",
  "answer",
  ["A person against whom a written instrument is void or voidable, fearing serious injury if it is left "
   "outstanding, may sue to have it adjudged void and cancelled; if it was registered, the decree is sent to the "
   "registering officer."],
  necessary=[(SRA, "39", 3)], check=[r"adjudged void or voidable", r"delivered up and cancelled"])

# ---------------------------------------------------------------- procedural (8)
c("S5-R01", "procedural", "F5-who-presents", "property", ["en"], "latin",
  "Who can take a sale deed to the registration office in Karachi?", "Persons who may present a document",
  "fed", "sindh", "answer",
  ["A person executing or claiming under the document, or that person's representative or assign, or an agent "
   "authorised by power of attorney, presents it."],
  necessary=[(REG, "32", 3)], check=[r"by some person executing or claiming under the same", r"power-of attorney"])
c("S5-R02", "procedural", "F5-revenue-revision-punjab", "property", ["en"], "latin",
  "How do I ask the Board of Revenue in Punjab to revise a revenue officer's order, and within what time?",
  "Revision in the Punjab Land Revenue Act", "punjab", "punjab", "answer",
  ["The Board of Revenue, and a Commissioner or Collector for officers under him, may call for the record on its "
   "own motion or on an application made within thirty days of the order."],
  necessary=[(PLRA67, "164", 3)], check=[r"Board of Revenue", r"thirty"])
c("S5-R03", "procedural", "F5-women-property-pending-ict", "property", ["en"], "latin",
  "My property case is already in court in Islamabad. Can I still go to the Ombudsman as a woman?",
  "Complaint to the Ombudsman while court proceedings are pending", "fed", "ict", "answer",
  ["Yes: where court proceedings about a woman's property are pending she may still complain to the Ombudsman under "
   "the separate provision for pending cases."],
  necessary=[(WPR_ICT, "7", 3)], check=[r"proceedings in a court of law are pending in relation to"])
c("S5-R04", "procedural", "F5-women-property-kp", "property", ["en"], "latin",
  "How do I complain to the Ombudsperson in Mardan that my in-laws took my land?",
  "Complaint and its outcome under the KP women's property Act", "kp", "kp", "answer",
  ["A woman deprived of ownership or possession may complain to the Ombudsperson when no court case is pending; "
   "after a preliminary assessment, if illegal deprivation is found the Deputy Commissioner or others are directed "
   "to restore possession or title."],
  necessary=[(WPR_KP, "4", 3)], relevant=[(WPR_KP, "5", 2)], must_not_serve=[(WPR_ICT, "4")],
  check=[r"complaint to the Ombudsperson", r"preliminary assessment"])
c("S5-R05", "procedural", "F5-impounding", "property", ["en"], "latin",
  "What happens if I hand an unstamped agreement to a government office in Karachi?",
  "Examination and impounding of instruments not duly stamped", "fed", "sindh", "answer",
  ["A person in charge of a public office (not a police officer) before whom an instrument chargeable with duty "
   "comes must impound it if it is not duly stamped."],
  necessary=[(STAMP, "33", 3)], check=[r"impound the same", r"except an officer of police"])
c("S5-R06", "procedural", "F5-land-record-appeal-punjab", "property", ["en"], "latin",
  "How do I appeal against an entry made by the Punjab Land Records Authority?",
  "Appeals against land records follow the Punjab Land Revenue Act", "punjab", "punjab", "answer",
  ["The appeal, review and revision provisions of Chapter XIII of the Punjab Land Revenue Act, 1967 apply to land "
   "records prepared under the 2017 Act."],
  necessary=[(PLRA17, "19", 3)], relevant=[(PLRA67, "161", 2)], check=[r"Chapter XIII of the Punjab Land Revenue Act"])
c("S5-R07", "procedural", "F5-lease-ending", "property", ["en"], "latin",
  "In what ways does a lease of a shop in Islamabad come to an end?", "Determination of lease", "fed", "ict",
  "answer",
  ["A lease ends by efflux of its time, by a limiting event, by merger of the interests, by express or implied "
   "surrender, by forfeiture, or on expiry of a notice to quit."],
  necessary=[(TPA, "111", 3)], check=[r"efflux of the time", r"express surrender"])
c("S5-R08", "procedural", "F5-exchange", "property", ["en"], "latin",
  "We want to swap our plots in Quetta. How is the exchange completed legally?",
  "An exchange of immovable property is made as a sale is", "fed", "balochistan", "answer",
  ["An exchange is completed in the manner provided for transfer of such property by sale, so for immovable "
   "property worth one hundred rupees or more by a registered instrument."],
  necessary=[(TPA, "118", 3)], relevant=[(TPA, "54", 2)], check=[r"manner provided for the transfer of such property "
                                                                  r"by sale"])

# ---------------------------------------------------------------- Urdu / Roman Urdu (5)
c("S5-U01", "urdu", "F5-women-property-punjab", "property", ["ur-Latn"], "roman_urdu",
  "Mere bhai Lahore mein abbu ke ghar mein mera hissa nahi de rahe, court ke ilawa kahan shikayat kar sakti hoon?",
  "Women's property complaint in Punjab (Roman Urdu variant of S5-C01)", "punjab", "punjab", "answer",
  ["She may complain to the Punjab Ombudsperson if no court case is pending."],
  necessary=[(WPR_PB, "4", 3)], must_not_serve=[(WPR_ICT, "4")], check=[r"deprived of ownership or possession"])
c("S5-U02", "urdu", "F5-oral-lease", "property", ["ur"], "arabic",
  "کیا تین سال کے لیے زمین کا زبانی پٹہ درست ہے یا رجسٹری ضروری ہے؟",
  "Registration of a lease for more than a year (Urdu variant of S5-C09)", "fed", "sindh", "answer",
  ["A lease for more than one year can be made only by a registered instrument."],
  necessary=[(TPA, "107", 3)], check=[r"exceeding one year"])
c("S5-U03", "urdu", "F5-fard-wrong-entry", "property", ["ur-Latn"], "roman_urdu",
  "Meri zameen ki fard mein kisi aur ka naam likha hai, mein kya karoon?",
  "A wrong record-of-rights entry in Punjab (Roman Urdu variant of S5-C14)", "punjab", "punjab", "answer",
  ["A suit for declaration lies; a correction of the entry is pursued before the Revenue Officer."],
  necessary=[(PLRA67, "53", 3)], check=[r"suit for a declaration"])
c("S5-U04", "urdu", "F5-right-of-way-prescription", "property", ["ur-Latn"], "roman_urdu",
  "Mein 25 saal se hamsaye ki zameen se guzar kar sadak tak jata hoon, kya ab yeh rasta mera haq hai?",
  "A right of way by prescription (Roman Urdu variant of S5-C11)", "fed", "sindh", "conditional",
  ["Twenty years' peaceable, open use as of right without interruption acquires the easement."],
  necessary=[(EAS, "15", 3)], check=[r"twenty years"])
c("S5-U05", "urdu", "F5-unstamped-agreement", "property", ["ur-Latn"], "roman_urdu",
  "Sade kaghaz par likha plot ka iqrarnama, jis par stamp nahi, kya court mein saboot ban sakta hai?",
  "An unstamped agreement in evidence (Roman Urdu variant of S5-C17)", "fed", "sindh", "answer",
  ["Not unless duly stamped, but it may be admitted on payment of the duty and a penalty."],
  necessary=[(STAMP, "35", 3)], check=[r"duly stamped"])

# ---------------------------------------------------------------- deliberately unanswerable (5)
c("S5-X01", "unanswerable", "F5-x-market-value", "property", ["en"], "latin",
  "What is a 10-marla house in DHA Lahore worth right now?", "A market price, not law", "punjab", None,
  "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["quoting a price", "quoting a valuation table as the market price"],
                  why="a live market price is not in any statute"))
c("S5-X02", "unanswerable", "F5-x-hiba-judgment", "property", ["en"], "latin",
  "What did the Supreme Court hold about an oral gift (hiba) of land without possession?",
  "A judgment's holding", "fed", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["summarising case law from memory", "answering from TPA s.123 instead"],
                  why="the corpus holds no judgments (D-100)"))
c("S5-X03", "unanswerable", "F5-x-foreign-inheritance", "property", ["en"], "latin",
  "What are the inheritance rules in Dubai for a flat there owned by my late father?",
  "Foreign succession law", "foreign", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["applying Pakistani succession law to property in Dubai"],
                  why="the corpus is Pakistani law only"))
c("S5-X04", "unanswerable", "F5-x-deed-records", "property", ["en"], "latin",
  "Has anyone registered a sale deed for plot 112, Block C, Johar Town in the last year?",
  "A search of the registration records", "punjab", None, "abstain", [],
  abstention=dict(code="unsupported_scope", requiredClarification=[],
                  unsafeAlternatives=["guessing", "answering with the Registration Act's rules"],
                  why="registration records of particular properties are not in the corpus"))
c("S5-X05", "unanswerable", "F5-x-false-act", "property", ["en"], "latin",
  "Under the Pakistan Property Inheritance Act, 2015, what share does a daughter get?",
  "A statute that does not exist (false premise)", "fed", None, "abstain", [],
  abstention=dict(code="abstained", requiredClarification=["the law the question means"],
                  unsafeAlternatives=["answering as if the Act existed", "quoting inheritance shares from memory"],
                  why="no such Act is in the corpus or the federal statute book; the premise is false"))

if __name__ == "__main__":
    raise SystemExit(build(S, "Set 5: property and land -- sale, mortgage, lease, gift, registration, stamp duty, "
                              "easements, the Punjab land record and tenancy, and the women's property rights Acts."))
