"""The subject_matter facet, vocabulary version 1 (D-163; docs/03b §2.1, §8): assigned by rule where a law's short
title decides it, and left unassigned otherwise -- never guessed (a classifier for the rest is a later version).

    subjects_of(title) -> list[(value, evidence)]

A title may carry one to three subjects ('Banking Companies (Recovery of Loans) Ordinance' is finance; 'Income Tax
Ordinance' is tax). The rules are ordered; each is a pattern over the folded title. The vocabulary is data: bump
VERSION and record it in taxonomy_version when a value or a rule changes, so a stored value always says which
vocabulary made it.
"""
from __future__ import annotations

import re

VERSION = 1
RATIONALE = ("subject_matter v1 (26 Nov 2026): 22 areas a citizen or lawyer asks by; assigned only where the short "
             "title decides it (docs/03b §8); the rest unassigned until a classifier version")

# (value, pattern over the lowercased title). Order matters only for readability; every matching rule assigns.
SUBJECT_RULES: list[tuple[str, str]] = [
    ("family", r"\bmarriages?\b|\bdivorce\b|\bfamily\s+(?:courts?|laws?)\b|\bguardians?\s+and\s+wards\b|\bdowry\b|"
               r"\bbridal\s+gifts\b|\bkhula\b|\bmuslim\s+personal\s+law\b|\bdomestic\s+violence\b|\bmajority\s+act\b|"
               r"\banand\s+karaj\b|\bprotection\s+of\s+women\b|\bwakf|\bwaqf"),
    ("criminal", r"\bpenal\s+code\b|\bcriminal\s+(?:procedure|law)\b|\bnarcotic|\bterroris|\bhudood\b|\bqisas\b|"
                 r"\bprisons?\b|\bprobation\b|\barms\b|\bexplosives?\b|\boffences?\b|\bprevention\s+of\s+corruption\b|"
                 r"\baccountability\b|\bjuvenile\s+justice\b|\bmoney\s+laundering\b|\bcrimes?\b|\bprosecution\b"),
    ("tax", r"\bincome\s+tax\b|\bsales\s+tax\b|\bcustoms\b|\bexcise\b|\bstamp\s+act\b|\btax(?:es|ation)?\b|"
            r"\bzakat\b|\bushr\b|\bcapital\s+value\b|\bfinance\s+act\b"),
    ("finance_banking", r"\bbank(?:s|ing)?\b|\bfinancial\s+institutions?\b|\brecovery\s+of\s+(?:finances|loans)\b|"
                        r"\bnegotiable\s+instruments\b|\binsurance\b|\bmodaraba|\bsecurities\b|\bmicrofinance\b|"
                        r"\bforeign\s+exchange\b|\bpayment\s+systems?\b|\bcredit\b|\bstock\s+exchange\b|"
                        r"\bpublic\s+finance\b"),
    ("corporate_commercial", r"\bcompanies\b|\bpartnership\b|\bcompetition\b|\bcontract\s+act\b|\bsale\s+of\s+goods\b|"
                             r"\barbitration\b|\binsolvency\b|\bcorporate\b|\bconsumer\s+protection\b"),
    ("intellectual_property", r"\btrade\s*marks?\b|\bpatents?\b|\bcopyright\b|\bdesigns\s+ordinance\b|"
                              r"\bgeographical\s+indications\b|\bintellectual\s+property\b"),
    ("property_land", r"\bland\b|\btransfer\s+of\s+property\b|\bregistration\s+act\b|\bpre-?emption\b|"
                      r"\brented\s+premises\b|\btenancy\b|\brent\b|\bcoloni[sz]ation\b|\balienation\b|"
                      r"\burban\s+(?:immovable\s+)?property\b|\bbuildings?\s+control\b|\bdevelopment\s+authority\b|"
                      r"\bhousing\b|\bevacuee\b|\bsurvey\b"),
    ("labour_employment", r"\blabou?r\b|\bindustrial\s+relations\b|\bworkm[ae]n\b|\bfactories\s+act\b|\bminimum\s+wages?\b|"
                          r"\bold-?age\s+benefits\b|\bsocial\s+security\b|\bworkers\b|\bemployment\b|\bpayment\s+of\s+wages\b"),
    ("civil_service", r"\bcivil\s+servants?\b|\bservice\s+tribunals?\b|\bgovernment\s+servants\b|\bpension\b|"
                      r"\befficiency\s+and\s+discipline\b|\bpublic\s+service\s+commission\b"),
    ("elections", r"\belections?\b|\brepresentation\s+of\s+the\s+people\b|\bpolitical\s+parties\b"),
    ("local_government", r"\blocal\s+government\b|\bmunicipal\b|\bcantonments?\b|\bunion\s+councils?\b"),
    # the Constitution, never a body's 'constitution' ('Prosecution Service (Constitution, Functions and Powers)')
    ("constitutional", r"\bconstitution\s+of\s+(?:the\s+)?(?:islamic\s+republic\s+of\s+)?pakistan\b|"
                       r"\bconstitution\s*\(\s*\w+(?:[\s-]\w+)?\s+amendment\s*\)|\binterim\s+constitution\b|"
                       r"\bgilgit.baltistan\s+(?:governance|government)\s+order\b|\bconstitution\s+act\b"),
    ("civil_procedure", r"\bcivil\s+procedure\b|\bspecific\s+relief\b|\blimitation\s+act\b|\bcourt\s+fees\b|"
                        r"\bsuits\s+valuation\b|\bqanun-?e-?shahadat\b|\bevidence\s+act\b|\boaths\b"),
    ("courts_judiciary", r"\bhigh\s+court\b|\bsupreme\s+court\b|\bcivil\s+courts\b|\bjudicial\b|\blegal\s+practitioners\b|"
                         r"\bbar\s+councils?\b|\bcontempt\s+of\s+court\b|\bjudges\b"),
    ("education", r"\buniversit|\bcollege\b|\bschools?\b|\beducation\b|\bboard\s+of\s+intermediate\b|\bcurriculum\b"),
    ("health", r"\bhealth\b|\bmedical\b|\bdrugs?\b|\bhospitals?\b|\bpharmac|\bnursing\b|\bmental\s+health\b|"
               r"\bblood\s+transfusion\b|\bfood\s+(?:safety|authority)\b|\bpure\s+food\b"),
    ("environment", r"\benvironment|\bforests?\b|\bwildlife\b|\bfisher(?:y|ies)\b|\bclimate\b|\bpollution\b"),
    ("energy_utilities", r"\belectricity\b|\boil\b|\bgas\b|\bpetroleum\b|\bnepra\b|\bogra\b|\benergy\b|\bpower\b|"
                         r"\bwater\s+and\s+power\b|\bmines?\b|\bminerals?\b"),
    ("transport", r"\bmotor\s+vehicles?\b|\broad\b|\brailways?\b|\bcivil\s+aviation\b|\bmerchant\s+shipping\b|"
                  r"\bports?\b|\btransport\b|\bhighways?\b"),
    ("media_technology", r"\belectronic\b|\bmedia\b|\bpemra\b|\btelecommunication|\bbroadcast|\bpress\b|"
                         r"\bnewspapers?\b|\bdata\s+protection\b|\bcyber"),
    ("police_public_order", r"\bpolice\b|\bpublic\s+order\b|\blevies\b|\bfrontier\s+(?:constabulary|crimes)\b"),
    ("religious_affairs", r"\bauqaf\b|\bhajj\b|\bmadaris\b|\bdeeni\b|\bislamic\s+ideology\b|\bshariat\b|"
                          r"\bevacuee\s+trust\b|\bminorities\b"),
]
_COMPILED = [(v, re.compile(p, re.I)) for v, p in SUBJECT_RULES]
VOCABULARY = sorted({v for v, _ in SUBJECT_RULES})

# a title rule that would mislead: 'Finance Act' of a province is tax; 'Land Customs' is customs (tax), not land
_NOT = {("property_land", re.compile(r"\bland\s+customs\b", re.I)),
        ("energy_utilities", re.compile(r"\bpower\s+of\s+attorney\b|\bpowers\b", re.I)),
        ("health", re.compile(r"\bpublic\s+health\s+engineering\b", re.I))}
# Read 26 Nov 2026 (author check, D-163): 37 of 40 sampled assignments right before these three fixes
# (a body's 'constitution', 'Sugar Factories Control', 'Public Health Engineering' service rules).


def subjects_of(title: str | None) -> list[tuple[str, str]]:
    """the subjects a short title decides, each with the words that decided it; at most three, in rule order"""
    t = " ".join((title or "").split())
    out = []
    for value, rx in _COMPILED:
        m = rx.search(t)
        if m and not any(v == value and nx.search(t) for v, nx in _NOT):
            out.append((value, m.group(0)))
    return out[:3]
