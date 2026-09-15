from app.ingest.ddinter_parsing import (
    NormalizedPair,
    ParsedSeverity,
    RawPairRow,
    Severity,
    build_mechanism_text,
    dedupe_pairs,
    normalize_pair,
    parse_severity,
    severity_rank,
)


def graded(name_a: str, name_b: str, severity: Severity) -> NormalizedPair:
    return NormalizedPair(name_a=name_a, name_b=name_b, severity=severity, severity_ungraded=False)


def ungraded(name_a: str, name_b: str) -> NormalizedPair:
    return NormalizedPair(name_a=name_a, name_b=name_b, severity=None, severity_ungraded=True)


def test_parse_severity_maps_ddinter_levels():
    assert parse_severity("Major") == ParsedSeverity(severity=Severity.HIGH, ungraded=False)
    assert parse_severity("Moderate") == ParsedSeverity(severity=Severity.MODERATE, ungraded=False)
    assert parse_severity("Minor") == ParsedSeverity(severity=Severity.LOW, ungraded=False)


def test_parse_severity_is_case_and_whitespace_insensitive():
    assert parse_severity(" MAJOR ") == ParsedSeverity(severity=Severity.HIGH, ungraded=False)


def test_parse_severity_unknown_is_a_valid_ungraded_result_not_a_rejection():
    assert parse_severity("Unknown") == ParsedSeverity(severity=None, ungraded=True)
    assert parse_severity(" unknown ") == ParsedSeverity(severity=None, ungraded=True)


def test_parse_severity_returns_none_for_genuinely_unrecognized_text():
    assert parse_severity("Contraindicated") is None
    assert parse_severity("") is None


def test_normalize_pair_orders_names_case_insensitively():
    row = RawPairRow(drug_a="Warfarin", drug_b="aspirin", level="Major")
    pair = normalize_pair(row)
    assert pair == graded("aspirin", "Warfarin", Severity.HIGH)


def test_normalize_pair_keeps_unknown_severity_as_ungraded_pair():
    row = RawPairRow(drug_a="Warfarin", drug_b="aspirin", level="Unknown")
    pair = normalize_pair(row)
    assert pair == ungraded("aspirin", "Warfarin")
    assert pair.severity is None
    assert pair.severity_ungraded is True


def test_normalize_pair_rejects_self_pair():
    row = RawPairRow(drug_a="Aspirin", drug_b="aspirin", level="Major")
    assert normalize_pair(row) is None


def test_normalize_pair_rejects_blank_names():
    assert normalize_pair(RawPairRow(drug_a="", drug_b="Aspirin", level="Major")) is None
    assert normalize_pair(RawPairRow(drug_a="Aspirin", drug_b="   ", level="Major")) is None


def test_normalize_pair_rejects_genuinely_unrecognized_severity():
    row = RawPairRow(drug_a="Aspirin", drug_b="Warfarin", level="Contraindicated")
    assert normalize_pair(row) is None


def test_normalize_pair_collapses_internal_whitespace():
    row = RawPairRow(drug_a="  Bismuth   subsalicylate ", drug_b="Naproxen", level="Major")
    pair = normalize_pair(row)
    assert pair.name_a == "Bismuth subsalicylate"


def test_dedupe_pairs_removes_reordered_duplicate():
    # Same real-world pair, appearing as (A,B) in one category file and
    # (B,A) in another — exactly what the ATC-category split produces.
    pairs = [graded("aspirin", "warfarin", Severity.HIGH), graded("aspirin", "warfarin", Severity.HIGH)]
    assert dedupe_pairs(pairs) == [graded("aspirin", "warfarin", Severity.HIGH)]


def test_dedupe_pairs_keeps_highest_severity_on_conflict():
    pairs = [graded("aspirin", "warfarin", Severity.MODERATE), graded("aspirin", "warfarin", Severity.HIGH)]
    result = dedupe_pairs(pairs)
    assert len(result) == 1
    assert result[0].severity == Severity.HIGH


def test_dedupe_pairs_prefers_graded_over_ungraded_regardless_of_order():
    graded_first = dedupe_pairs([graded("aspirin", "warfarin", Severity.LOW), ungraded("aspirin", "warfarin")])
    ungraded_first = dedupe_pairs([ungraded("aspirin", "warfarin"), graded("aspirin", "warfarin", Severity.LOW)])
    assert graded_first == [graded("aspirin", "warfarin", Severity.LOW)]
    assert ungraded_first == [graded("aspirin", "warfarin", Severity.LOW)]


def test_dedupe_pairs_keeps_ungraded_when_thats_all_there_is():
    result = dedupe_pairs([ungraded("aspirin", "warfarin")])
    assert result == [ungraded("aspirin", "warfarin")]


def test_dedupe_pairs_preserves_first_seen_order():
    pairs = [graded("a", "b", Severity.LOW), graded("c", "d", Severity.LOW)]
    result = dedupe_pairs(pairs)
    assert [(p.name_a, p.name_b) for p in result] == [("a", "b"), ("c", "d")]


def test_build_mechanism_text_states_only_the_known_fact():
    text = build_mechanism_text("Aspirin", "Warfarin", Severity.HIGH, ungraded=False)
    assert text == "DDInter classifies concurrent use of Aspirin and Warfarin as a high-severity interaction."


def test_build_mechanism_text_for_ungraded_pair_does_not_claim_a_severity():
    text = build_mechanism_text("Aspirin", "Warfarin", None, ungraded=True)
    assert text == (
        "DDInter records a potential interaction between Aspirin and Warfarin "
        "but does not assign it a severity grade."
    )
    assert "high" not in text and "moderate" not in text and "low" not in text


# --- severity_rank (public, shared with app.ingest.ddinter's post-
# resolution collision dedup — see that module's docstring) -------------


def test_severity_rank_orders_high_above_moderate_above_low():
    assert severity_rank(Severity.HIGH, False) > severity_rank(Severity.MODERATE, False)
    assert severity_rank(Severity.MODERATE, False) > severity_rank(Severity.LOW, False)


def test_severity_rank_ungraded_ranks_below_every_graded_severity():
    ungraded_rank = severity_rank(None, True)
    assert ungraded_rank < severity_rank(Severity.LOW, False)
    assert ungraded_rank < severity_rank(Severity.MODERATE, False)
    assert ungraded_rank < severity_rank(Severity.HIGH, False)
