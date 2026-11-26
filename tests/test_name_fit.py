"""D-149: a law named without an alias resolves by how well a title fits the printed name, before the court's
territory is preferred. Pure: nizam.storage.citations.name_fit."""
from nizam.storage.citations import name_fit


def test_the_wrong_links_found_on_26_nov_never_match():
    # Peshawar 'section 5 of the Limitation Act' had resolved to KP's School Bags Act (its words are in a bracket)
    assert name_fit("Limitation Act", "The Khyber Pakhtunkhwa School Bags (Limitation of Weight) Act, 2020") == 4
    # AJK 'the Limitation Act' had resolved to an LLP adaptation Act
    assert name_fit("Limitation Act", "XVILimited Liability Partnership (Adaptaton) Act, 2021") == 4
    # Sindh 'Sales Tax Act' fits Sindh's services Act only loosely, so the Sales Tax Act itself ranks above it
    assert name_fit("Sales Tax Act", "SINDH SALES TAX ON SERVICES ACT, 2011") == 3
    assert name_fit("Sales Tax Act", "Sales Tax Act, 1990") == 1


def test_the_same_name_under_its_variants():
    assert name_fit("Limitation Act, 1908", "LIMITATION ACT, 1908") == 1
    assert name_fit("Anti-Terrorism Act, 1997", "Anti Terrorism Act (ATA),1997") == 1
    assert name_fit("Election Act, 2017", "Elections Act, 2017") == 1
    assert name_fit("Guardian and Wards Act, 1890", "Guardians and Wards Act, 1890") == 1
    assert name_fit("Cantonment Act, 1924", "Cantonments Act, 1924") == 1
    assert name_fit("Qanun-e- Shahadat Order, 1984", "QANUN-E-SHAHADAT ORDER, 1984") == 1
    # a territory's copy carries its place as a prefix
    assert name_fit("Land Revenue Act, 1967", "West Pakistan Land-Revenue Act, 1967") == 1
    assert name_fit("Sindh Building Control Ordinance, 1979", "SINDH BUILDINGS CONTROL ORDINANCE, 1979 Codified") == 1
    assert name_fit("Pakistan Penal Code", "Pakistan Penal Code (XLV of 1860)") == 1


def test_a_run_or_an_ordered_subset_ranks_below_the_same_name():
    assert name_fit("Limitation Act", "The Indian Limitation Act, 1877") == 2
    assert name_fit("Islamic Republic of Pakistan, 1973",
                    "THE CONSTITUTION OF THE ISLAMIC REPUBLIC OF PAKISTAN") == 2
    assert name_fit("Colonization Act", "COLONIZATION OF GOVERNMENT LANDS (PUNJAB) ACT, 1912") == 3


def test_an_acronym_printed_as_the_name_and_a_short_plural():
    # 26 Nov relink: these had become 'law not held' under the first form of the rule
    assert name_fit("PEMRA Ordinance, 2002",
                    "Pakistan Electronic Media Regulatory Authority Ordinance (PEMRA), 2002") == 1
    assert name_fit("FIA Act", "Federal Investigation Agency Act (FIA), 1974") == 1
    assert name_fit("OGRA Ordinance", "Oil and Gas Regulatory Authority (OGRA) Ordinance , 2002") == 1
    assert name_fit("Muslim Family Law Ordinance, 1961", "Muslim Family Laws Ordinance, 1961") == 1
    # the display title drops the acronym; the short title keeps it
    from nizam.storage.citations import name_fit_any
    assert name_fit_any("FIA Act", ["Federal Investigation Agency Act (FIA), 1974",
                                    "Federal Investigation Agency Act, 1974"]) == 1
    # an acronym never lends itself to a law that does not print it
    assert name_fit("PEMRA Ordinance", "Oil and Gas Regulatory Authority (OGRA) Ordinance , 2002") == 4


def test_words_out_of_order_or_missing_are_no_match():
    assert name_fit("Act Limitation", "Limitation Act, 1908") == 4
    assert name_fit("Customs Act", "Limitation Act, 1908") == 4
    assert name_fit("", "Limitation Act, 1908") == 4
