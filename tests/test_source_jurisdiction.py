"""A source's instruments are filed under its own jurisdiction; an unknown source is refused, never filed as federal.

docs/02 §2.2: the Gilgit-Baltistan and AJK assemblies add jurisdictions, and "ingestion must not mislabel it as
federal". Until 14 Nov 2026 nizam.workers.segment fell back to 'fed' for any source it did not know.
"""
import pytest

from nizam.workers.segment import JURISDICTION, jurisdiction_of


def test_every_corpus_source_maps_to_its_jurisdiction():
    assert jurisdiction_of("pk-federal") == "fed"
    assert jurisdiction_of("pk-punjab") == "punjab"
    assert jurisdiction_of("pk-sindh") == "sindh"
    assert jurisdiction_of("pk-kp") == "kp"
    assert jurisdiction_of("pk-balochistan") == "balochistan"


def test_territories_are_their_own_jurisdictions():
    assert jurisdiction_of("pk-ajk") == "ajk"
    assert jurisdiction_of("pk-gb") == "gb"
    assert jurisdiction_of("pk-ict") == "ict"


def test_unknown_source_is_refused_not_filed_as_federal():
    with pytest.raises(ValueError, match="no jurisdiction"):
        jurisdiction_of("pk-ajk-assembly")


def test_every_value_is_in_the_enum():
    # doc 03 §1.1: CREATE TYPE jurisdiction AS ENUM ('fed','punjab','sindh','kp','balochistan','ict','ajk','gb')
    assert set(JURISDICTION.values()) <= {"fed", "punjab", "sindh", "kp", "balochistan", "ict", "ajk", "gb"}
