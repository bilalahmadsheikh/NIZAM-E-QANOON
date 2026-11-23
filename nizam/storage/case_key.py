"""The key of a case, as printed (D-125): '<court>/<type>/<number>/<year>', e.g. 'SC/CA/1507/2024'.

It lives in storage so that the builder (L1, nizam.corpus.judgment_case), the linker and the API (L6) build the same
key from the same words. It is built from printed words, never from a row id, so a rebuild never changes it.
Leading zeros are not part of a number ('No.05/2012' is case 5 of 2012).
"""
from __future__ import annotations

import re


def norm_number(number: str) -> str:
    """'05' -> '5', '801-l' -> '801-L', '0780' -> '780'. Keeps a trailing letter suffix (a registry's seat)."""
    n = re.sub(r"\s+", "", number).upper()
    return re.sub(r"^0+(?=\d)", "", n)


def case_key(court: str, case_type_code: str, number: str, year: int) -> str:
    kind = case_type_code.split(":", 1)[1] if ":" in case_type_code else case_type_code
    return f"{court}/{kind}/{norm_number(number)}/{year}"
