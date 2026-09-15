from app.ingest.ddinter_coverage import (
    MentionRecord,
    RawMentionRow,
    build_class_code_by_name,
    class_codes_present,
    extract_mentions,
)


def test_extract_mentions_tags_drug_a_with_class_code():
    rows = [RawMentionRow(drug_a="Aspirin", drug_b="Warfarin", class_code="A")]
    mentions = extract_mentions(rows)
    assert MentionRecord(name="Aspirin", class_code="A") in mentions


def test_extract_mentions_does_not_tag_drug_b_with_class_code():
    rows = [RawMentionRow(drug_a="Aspirin", drug_b="Warfarin", class_code="A")]
    mentions = extract_mentions(rows)
    assert MentionRecord(name="Warfarin", class_code=None) in mentions


def test_extract_mentions_collapses_whitespace():
    rows = [RawMentionRow(drug_a="  Aspirin  ", drug_b="Warfarin", class_code="A")]
    mentions = extract_mentions(rows)
    assert mentions[0].name == "Aspirin"


def test_extract_mentions_skips_blank_names():
    rows = [RawMentionRow(drug_a="", drug_b="Warfarin", class_code="A")]
    mentions = extract_mentions(rows)
    assert len(mentions) == 1
    assert mentions[0].name == "Warfarin"


def test_extract_mentions_returns_two_records_per_row():
    rows = [RawMentionRow(drug_a="Aspirin", drug_b="Warfarin", class_code="A")]
    assert len(extract_mentions(rows)) == 2


def test_build_class_code_by_name_keeps_first_class_seen():
    mentions = [
        MentionRecord(name="Aspirin", class_code="A"),
        MentionRecord(name="Aspirin", class_code="B"),
    ]
    result = build_class_code_by_name(mentions)
    assert result["aspirin"] == "A"


def test_build_class_code_by_name_upgrades_from_none_when_a_class_appears_later():
    # Warfarin seen first as Drug_B (no class), later as Drug_A (class B) —
    # in a different row/file. Should end up tagged B, not stuck at None.
    mentions = [
        MentionRecord(name="Warfarin", class_code=None),
        MentionRecord(name="Warfarin", class_code="B"),
    ]
    result = build_class_code_by_name(mentions)
    assert result["warfarin"] == "B"


def test_build_class_code_by_name_stays_none_when_never_seen_as_drug_a():
    mentions = [MentionRecord(name="Warfarin", class_code=None)]
    result = build_class_code_by_name(mentions)
    assert result["warfarin"] is None


def test_build_class_code_by_name_is_case_insensitive_key():
    mentions = [MentionRecord(name="Aspirin", class_code="A"), MentionRecord(name="aspirin", class_code=None)]
    result = build_class_code_by_name(mentions)
    assert result["aspirin"] == "A"
    assert len(result) == 1


def test_class_codes_present_returns_unique_set():
    rows = [
        RawMentionRow(drug_a="A", drug_b="B", class_code="A"),
        RawMentionRow(drug_a="C", drug_b="D", class_code="A"),
        RawMentionRow(drug_a="E", drug_b="F", class_code="R"),
    ]
    assert class_codes_present(rows) == {"A", "R"}
