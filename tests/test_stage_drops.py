"""D-113, tools/acquire/stage_drops.py: which drop files are one instrument, which amend another, which is newest."""
import importlib.util
import sys
import types
from pathlib import Path

sys.modules.setdefault("requests", types.ModuleType("requests"))
_p = Path(__file__).resolve().parents[1] / "tools/acquire/stage_drops.py"
_spec = importlib.util.spec_from_file_location("stage_drops", _p)
S = importlib.util.module_from_spec(_spec)
sys.path.insert(0, str(_p.parent))
_spec.loader.exec_module(S)


def test_amended_upto_is_a_consolidation_not_an_amending_instrument():
    assert not S.AMENDS.search("Income Tax Rules, 2002 Amended upto 8th September, 2020")
    assert S.AMENDS.search("SRO 243 of 2024 - Amendments to CRC Rules 2019")
    assert S.AMENDS.search("Anti-Terrorism (Third Amendment) Act, 2020")


def test_the_newest_consolidation_sorts_first():
    titles = ["Income Tax Rules, 2002 Amended upto 10th, December, 2015.",
              "Income Tax Rules, 2002 Amended upto 8th September, 2020",
              "Income Tax Rules, 2002 Amended upto 10th February, 2017"]
    assert max(titles, key=S.as_of_key).endswith("2020")
    assert S.as_of_key("Customs Act, 1969 as amended up to 30.06.2024") == (2024, 6, 30)


def test_one_instrument_under_its_sro_number_and_amended_tail():
    assert S.law_key("SRO 709 Research Analyst Regulations, 2015") == \
        S.law_key("Research Analyst Regulations, 2015 (as amended upto 2020)")


def test_drafts_and_guidance_are_recognised():
    assert S.DRAFT.search("SRO1214 (I)2019 Draft amendments in the Private Funds Regulations, 2015")
    assert S.PSX_RULE_BOOK.match("English Version (Updated on August 27, 2025)")
    assert not S.PSX_RULE_BOOK.match("Guidelines on Stock Split")
