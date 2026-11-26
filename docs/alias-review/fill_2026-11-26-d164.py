"""The decisions read on the 26 Nov 2026 'd164' alias sheet (D-164): each row's printed forms, candidates and passages
were read; this writes them into law-aliases-2026-11-26-d164.csv. A = alias (target document, basis).

Most rows are a bare year ('Section 19 of the 2001 Ordinance', 'Art. 69 of the 1973 Constitution'): a judgment's
own short form for a law it named in full earlier ('... Ordinance, 2001 ("the 2001 Ordinance")'). The same year means
a different law in each judgment, so none is an alias: they are 'ambiguous' here, and the linker reads each
judgment's own definition instead (D-164)."""
import csv
from pathlib import Path

SHEET = Path(__file__).with_name("law-aliases-2026-11-26-d164.csv")
A = "alias"
YEAR_ONLY = "a bare year: each judgment's own short form for a law it named in full; not one law (D-164 linker rule)"
D = {
    20: (A, 3126, "abbreviation", "IRRO 2001 = Islamabad Rent Restriction Ordinance 2001 (IHC rent passages, s.21(6))"),
    39: (A, 3408, "abbreviation", "C.A.A. Ordinance = Pakistan Civil Aviation Authority Ordinance 1982 (s.27: the "
                                  "Authority's regulations on its officers); not the Chhamb Area Ordinance offered"),
    40: ("ambiguous", None, None, "DHA Act: the Islamabad, Lahore and Karachi DHA Acts all print so; an alias would "
                                  "apply in every court"),
    42: (A, 3769, "abbreviation", "PM&DC Act 2022 = Pakistan Medical and Dental Council Act 2022 (s.14, the Registrar)"),
    43: (A, 3542, "abbreviation", "S.B.P. Act = State Bank of Pakistan Act 1956 (s.10: the Governor's appointment)"),
    44: (A, 4248, "short_name", "Telecom Act = Pakistan Telecommunication (Re-organization) Act 1996 (s.57(1): the "
                                "PTA Appointment Rules)"),
    45: (A, 4424, "abbreviation", "I.C.T.-L.G. Act = Islamabad Capital Territory Local Government Act 2015 (s.37(2): "
                                  "election petitions)"),
}

rows = list(csv.DictReader(SHEET.open(encoding="utf-8")))
for i, r in enumerate(rows):
    d = D.get(i, ("ambiguous", None, None, YEAR_ONLY))
    r["decision"], doc, basis, note = d
    r["target_document_id"] = "" if doc is None else str(doc)
    r["basis"] = basis or ""
    r["reviewer_note"] = note
with SHEET.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print({k: sum(1 for r in rows if r["decision"] == k) for k in ("alias", "ambiguous")})
