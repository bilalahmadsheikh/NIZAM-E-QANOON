"""The extent-clause reader records only what every word of the clause says (tools/record_territorial_extent.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from record_territorial_extent import ALL5, FOUR, first_clause, parse_extent  # noqa: E402


def test_whole_of_pakistan_and_its_print_variants():
    for ext in ("the whole of Pakistan", "the whole ofPakistan", "2[the whole of Pakistan]", "whole of Pakistan",
                "the whole of 3[Pakistan]", "the whole of Pakistan and applies to all citizens of Pakistan wherever "
                "they may be", "all the territories of Pakistan"):
        assert parse_extent(ext) == ALL5, ext


def test_ict_by_every_name():
    for ext in ("the Islamabad Capital Territory", "the whole of the Islamabad Capital Territory (ICT)"):
        assert parse_extent(ext) == ["ict"], ext
    for ext in ("the capital of the Federation", "the Federal Capital",
                "the Federal Capital, including the cantonments in the Federal Capital"):
        assert parse_extent(ext, 1985) == ["ict"], ext


def test_the_capital_before_1961_is_karachi():
    # The Karachi Rent Restriction Ordinance, 1953 'extends to the capital of the Federation': Karachi, not Islamabad
    assert parse_extent("the capital of the Federation", 1953) == ["sindh"]
    assert parse_extent("the Federal Capital", 1956) == ["sindh"]
    assert parse_extent("the Federal Capital", 1962) is None          # Rawalpindi interim: not read
    assert parse_extent("the Federal Capital") is None                # year unknown: not read
    assert parse_extent("all the Provinces and the capital of the Federation", 1950) is None


def test_the_hindu_marriage_act_list_excludes_sindh():
    assert parse_extent("the Islamabad Capital Territory and the Provinces of Balochistan, Khyber Pakhtunkhwa and "
                        "Punjab") == ["punjab", "kp", "balochistan", "ict"]


def test_west_pakistan_with_inner_exceptions_is_the_four_provinces():
    for ext in ("the whole of the Province of West Pakistan, except the Tribal Areas",
                "the whole of West Pakistan, except the Federal Capital and the Special Areas"):
        assert parse_extent(ext) == FOUR, ext


def test_single_provinces_by_old_names():
    assert parse_extent("the whole of Baluchistan") == ["balochistan"]
    assert parse_extent("the whole of the North-West Frontier Province") == ["kp"]
    assert parse_extent("the whole of the Punjab") == ["punjab"]


def test_all_the_provinces_needs_the_capital():
    assert parse_extent("all the Provinces and the capital of the Federation", 1990) == ALL5
    assert parse_extent("all the Provinces of Pakistan") is None       # whether ICT is meant is not printed


def test_anything_not_understood_is_not_read():
    for ext in ("the whole of British India", "the specified area", "all cantonments in Pakistan",
                "the whole of the port area", "the districts of Lahore, Gujrat and Jhelum",
                "such areas in the Federation as are not included in any Province", "the whole of East Bengal"):
        assert parse_extent(ext) is None, ext


def test_the_extent_of_some_sections_is_not_the_laws_extent():
    provs = [(2, "x.s_2", 12, 1, "Power to extend Act. Sections 13 and 17 of this Act shall extend to the whole of the "
                                 "Punjab; and it shall be competent to the Provincial Government ...")]
    assert first_clause(provs) is None


def test_first_clause_takes_the_extent_sentence_not_another_extends():
    provs = [(1, "x.s_1", 11, 1, "Short title, extent and commencement. (1) This Act may be called the X Act. "
                                 "It extends to the whole of Pakistan. It shall come into force at once.")]
    sentence, ext, block, page, path = first_clause(provs)
    assert parse_extent(ext) == ALL5 and block == 11 and sentence.startswith("It extends")
