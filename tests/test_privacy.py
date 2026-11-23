"""Names withheld in sensitive judgments (D-131): the pure rules. Printed forms are from the released judgments."""
from __future__ import annotations

from nizam.storage.privacy import (WITHHELD, is_institution, minor_names, names_of, names_queried, parties, redact,
                                   victim_names)


def test_the_parties_pair_is_found_and_role_words_dropped():
    assert parties("Saba Sarwar. Versus Govt. of Punjab, etc. Order with signature of Judge") == \
        ("Saba Sarwar", "Govt. of Punjab, etc")
    assert parties("(Against the judgment of Lahore High Court, Lahore, dated 18.05.2022, passed in C.R. No.24617/2022) "
                   "Meera Shafi ...…. Petitioner Versus Ali Zafar ……. Respondent") == ("Meera Shafi", "Ali Zafar")
    assert parties("Criminal Appeal No.812 of 2022. Abdul Basit vs The State etc. Date of hearing: 14.10.2024") == \
        ("Abdul Basit", "The State etc")
    assert parties("no parties here") is None


def test_institutions_are_kept_and_persons_named():
    assert is_institution("The State etc") and is_institution("Govt. of Punjab") and is_institution("M/s Nordex Ltd")
    assert not is_institution("Muhammad Riaz")
    assert names_of("Ch. Muhammad Farooq (deceased) through his widow Mst. Nadia Farooq") == \
        ["Muhammad Farooq", "Nadia Farooq"]
    assert names_of("Rizwan Akhtar alias Razi Bawa & another") == ["Rizwan Akhtar", "Razi Bawa"]
    assert names_of("Arshad Ali, etc.") == ["Arshad Ali"]


def test_the_victim_and_the_minor_are_found_in_the_body():
    body = ["The prosecutrix namely Mst. Sughran Bibi was abducted.", "Allah Ditta (the victim) deposed as PW-2.",
            "Mst. Kausar Parveen, mother of the victim, appeared."]
    assert set(victim_names(body)) >= {"Sughran Bibi", "Allah Ditta", "Kausar Parveen"}
    assert "Ali Raza" in minor_names(["the minor namely Ali Raza was in the custody of his mother"])
    assert minor_names(["The Court held that the law applies."]) == []


def test_redaction_replaces_whole_names_and_spares_common_single_words():
    text = "Muhammad Arslan was convicted. Muhammad Ashraf, Inspector, investigated. Arslan absconded."
    out = redact(text, ["Muhammad Arslan", "Arslan"], common=frozenset({"muhammad"}))
    assert out == f"{WITHHELD} was convicted. Muhammad Ashraf, Inspector, investigated. {WITHHELD} absconded."
    assert redact("Muhammad appeared.", ["Muhammad"], common=frozenset({"muhammad"})) == "Muhammad appeared."
    assert redact(text, []) == text


def test_a_query_naming_a_withheld_person_is_recognised():
    assert names_queried("judgment about Sughran Bibi abduction", ["Sughran Bibi"])
    assert names_queried("bibi sughran case", ["Sughran Bibi"])
    assert not names_queried("abduction and zina bail", ["Sughran Bibi"])
    assert not names_queried("Sughran", ["Sughran Bibi"])          # one word of a name is not a name


def test_a_long_run_of_spaces_in_ocr_text_does_not_hang_the_name_finder():
    import time
    text = "Abdul " + " " * 5000 + "Rehman Khan Bibi Wali " * 200 + " the victim"
    t = time.time()
    victim_names([text]), minor_names([text])
    assert time.time() - t < 2.0


def test_a_party_line_ending_in_a_run_of_dashes_is_read_at_once():
    import time
    t = time.time()
    assert parties("Sanaullah Versus Zia Ullah etc. " + "-" * 60) == ("Sanaullah", "Zia Ullah etc")
    assert time.time() - t < 0.5


def test_header_words_beside_a_name_never_make_a_side_an_institution_and_judge_is_a_party():
    left, right = parties("IN THE PESHAWAR HIGH COURT, PESHAWAR, [Judicial Department]. Cr.Misc.BA No.3315-P/2021 "
                          "Ahmad Khan son of Tanveer Ahmad, r/o Togh Bala Kohat. Petitioner (s) VERSUS The State")
    assert "Ahmad Khan" in left and names_of(left)               # a person is named: the builder withholds the side
    assert names_of(right) == []                                  # 'The State' names no person
    assert parties("AHMED AMIN versus Learned DISTRICT JUDGE, ATTOCK and others")[1].startswith(
        "Learned DISTRICT JUDGE")
    assert parties("W. P. No. 7340 / 2024 Saba Gul & 02 others Versus Additional District Judge")[0].startswith("Saba Gul")
    assert names_of("Saba Gul & 02 others") == ["Saba Gul"]


def test_a_child_victim_is_found_and_a_sentence_opener_is_not_a_name():
    assert "Zaryab Khan" in minor_names(["the dead body of minor Zaryab Khan son of Fida Muhammad Khan"])
    assert "Arsalan" in minor_names(["complainant Gul Khan alongwith his minor son namely Arsalan aged 11"])
    assert "Tooba Zahra" in minor_names(["real father of Tooba Zahra (“the minor daughter”)"])
    assert "Oftentimes" not in victim_names(["Oftentimes the victim’s husband or family are the perpetrators."])


def test_column_labels_stuck_to_a_name_are_not_part_of_it():
    assert names_of("that of parties or counsel, where necessary. Munawar Hussain") == ["Munawar Hussain"]
    assert names_of("Mst. Nadia Farooq") == ["Nadia Farooq"]
