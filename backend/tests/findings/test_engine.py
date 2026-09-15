"""Unit tests for the interaction rules engine (app.findings.engine).

Pure in-memory fixtures only — no DB, no FastAPI, no LLM. This is exactly the
guarantee the architecture is supposed to provide: findings are a pure
function of (detected ingredient ids, rule rows).
"""

from app.findings.engine import check_all_pairs, check_pair, dedupe_ingredients, find_interactions
from app.findings.models import Finding, IngredientRef, InteractionRule, PairState, Severity, SourceRef

SOURCE = SourceRef(id=1, name="DrugBank", url="https://drugbank.ca", reference="DB00945")

ASPIRIN = IngredientRef(id=1, name="Aspirin")
IBUPROFEN = IngredientRef(id=2, name="Ibuprofen")
WARFARIN = IngredientRef(id=3, name="Warfarin")
CALCIUM = IngredientRef(id=4, name="Calcium")
IRON = IngredientRef(id=5, name="Iron")


def rule(a: IngredientRef, b: IngredientRef, severity: Severity) -> InteractionRule:
    return InteractionRule(
        ingredient_a=a,
        ingredient_b=b,
        severity=severity,
        severity_ungraded=False,
        mechanism=f"{a.name} + {b.name} mechanism",
        source=SOURCE,
        source_text=f"Excerpt discussing {a.name} and {b.name}.",
    )


def ungraded_rule(a: IngredientRef, b: IngredientRef) -> InteractionRule:
    return InteractionRule(
        ingredient_a=a,
        ingredient_b=b,
        severity=None,
        severity_ungraded=True,
        mechanism=f"{a.name} + {b.name}: source records a potential interaction, ungraded",
        source=SOURCE,
        source_text=f"Excerpt discussing {a.name} and {b.name}, no severity assigned.",
    )


ASPIRIN_IBUPROFEN = rule(ASPIRIN, IBUPROFEN, Severity.MODERATE)
WARFARIN_ASPIRIN = rule(WARFARIN, ASPIRIN, Severity.HIGH)
WARFARIN_IBUPROFEN = rule(WARFARIN, IBUPROFEN, Severity.HIGH)
CALCIUM_IRON = rule(CALCIUM, IRON, Severity.LOW)

ALL_RULES = [ASPIRIN_IBUPROFEN, WARFARIN_ASPIRIN, WARFARIN_IBUPROFEN, CALCIUM_IRON]


def test_returns_empty_list_when_no_ingredients_detected():
    assert find_interactions([], ALL_RULES) == []


def test_returns_empty_list_when_only_one_side_of_every_rule_present():
    # Aspirin alone matches the "a" side of two rules and "b" side of one,
    # but no rule has BOTH sides satisfied.
    assert find_interactions([ASPIRIN.id], ALL_RULES) == []


def test_finds_single_matching_pair():
    result = find_interactions([ASPIRIN.id, IBUPROFEN.id], ALL_RULES)
    assert result == [
        Finding(
            ingredient_a=ASPIRIN,
            ingredient_b=IBUPROFEN,
            severity=Severity.MODERATE,
            severity_ungraded=False,
            mechanism=ASPIRIN_IBUPROFEN.mechanism,
            source=SOURCE,
            source_text=ASPIRIN_IBUPROFEN.source_text,
        )
    ]


def test_finds_multiple_pairs_when_three_interacting_ingredients_present():
    # Warfarin + Aspirin + Ibuprofen together should surface all three
    # pairwise rules, not just one.
    result = find_interactions([WARFARIN.id, ASPIRIN.id, IBUPROFEN.id], ALL_RULES)
    assert {(f.ingredient_a.name, f.ingredient_b.name) for f in result} == {
        ("Aspirin", "Ibuprofen"),
        ("Warfarin", "Aspirin"),
        ("Warfarin", "Ibuprofen"),
    }


def test_unrelated_ingredient_pair_does_not_trigger_unrelated_rule():
    result = find_interactions([ASPIRIN.id, IBUPROFEN.id], ALL_RULES)
    assert all(f.ingredient_a.name != "Calcium" and f.ingredient_b.name != "Calcium" for f in result)


def test_every_finding_carries_a_source_citation():
    # The hard requirement from docs/api-contract.md: every interaction
    # warning must be traceable to a source.
    result = find_interactions([WARFARIN.id, ASPIRIN.id], ALL_RULES)
    assert len(result) == 1
    finding = result[0]
    assert finding.source.name == "DrugBank"
    assert finding.source_text


def test_ingredient_present_only_on_the_b_side_of_a_rule_still_matches():
    # Regression guard: matching must check both (a in present and b in
    # present), not assume detected ingredients only ever appear as `a`.
    result = find_interactions([WARFARIN.id, ASPIRIN.id], [WARFARIN_ASPIRIN])
    assert len(result) == 1


def test_dedupe_ingredients_keeps_first_occurrence_and_drops_repeats():
    result = dedupe_ingredients([ASPIRIN, IBUPROFEN, ASPIRIN, WARFARIN, IBUPROFEN])
    assert result == [ASPIRIN, IBUPROFEN, WARFARIN]


def test_dedupe_ingredients_handles_empty_input():
    assert dedupe_ingredients([]) == []


def test_ungraded_pair_is_still_returned_by_an_interaction_query():
    # DDInter's "Unknown"-severity pairs (~21% of its raw rows) must not be
    # invisible to the engine just because they carry no severity grade.
    ST_JOHNS_WORT = IngredientRef(id=6, name="St. John's Wort")
    SERTRALINE = IngredientRef(id=7, name="Sertraline")
    ungraded = ungraded_rule(ST_JOHNS_WORT, SERTRALINE)

    result = find_interactions([ST_JOHNS_WORT.id, SERTRALINE.id], [ungraded])

    assert len(result) == 1


def test_ungraded_finding_is_distinguishable_from_a_graded_one():
    ST_JOHNS_WORT = IngredientRef(id=6, name="St. John's Wort")
    SERTRALINE = IngredientRef(id=7, name="Sertraline")
    rules = [ungraded_rule(ST_JOHNS_WORT, SERTRALINE), WARFARIN_ASPIRIN]

    result = find_interactions(
        [ST_JOHNS_WORT.id, SERTRALINE.id, WARFARIN.id, ASPIRIN.id], rules
    )

    by_pair = {(f.ingredient_a.name, f.ingredient_b.name): f for f in result}
    ungraded_finding = by_pair[("St. John's Wort", "Sertraline")]
    graded_finding = by_pair[("Warfarin", "Aspirin")]

    assert ungraded_finding.severity is None
    assert ungraded_finding.severity_ungraded is True
    assert graded_finding.severity == Severity.HIGH
    assert graded_finding.severity_ungraded is False
    # The two must never compare equal to each other by severity alone —
    # a consumer that only checks `severity` and ignores
    # `severity_ungraded` should not be able to confuse the two states.
    assert ungraded_finding.severity != graded_finding.severity


# --- check_pair / check_all_pairs -------------------------------------

# A source that has data on Aspirin, Ibuprofen, and Warfarin (mentioned
# them at all — not necessarily paired with each other) but has never
# heard of Calcium or Iron.
COVERED_IDS = {ASPIRIN.id, IBUPROFEN.id, WARFARIN.id}


def test_check_pair_returns_found_when_a_rule_matches():
    result = check_pair(ASPIRIN, IBUPROFEN, ALL_RULES, COVERED_IDS)
    assert result.state == PairState.FOUND
    assert result.finding is not None
    assert result.finding.severity == Severity.MODERATE


def test_check_pair_returns_found_for_an_ungraded_rule_too():
    result = check_pair(WARFARIN, IBUPROFEN, [ungraded_rule(WARFARIN, IBUPROFEN)], COVERED_IDS)
    assert result.state == PairState.FOUND
    assert result.finding.severity_ungraded is True


def test_check_pair_returns_checked_none_found_when_both_covered_but_no_rule():
    # Warfarin and Ibuprofen are both covered, but this rule set has no
    # Warfarin-Ibuprofen rule between them (only Aspirin-Ibuprofen,
    # Warfarin-Aspirin, and Calcium-Iron) — a genuine "checked, nothing
    # found" case, not a coverage gap.
    rules_without_warfarin_ibuprofen = [ASPIRIN_IBUPROFEN, WARFARIN_ASPIRIN, CALCIUM_IRON]
    result = check_pair(WARFARIN, IBUPROFEN, rules_without_warfarin_ibuprofen, COVERED_IDS)
    assert result.state == PairState.CHECKED_NONE_FOUND
    assert result.finding is None


def test_check_pair_returns_not_checked_source_gap_when_one_side_uncovered():
    # Calcium is not in COVERED_IDS — the source never mentioned it, so a
    # miss here must NOT read the same as "checked, nothing found".
    result = check_pair(ASPIRIN, CALCIUM, ALL_RULES, COVERED_IDS)
    assert result.state == PairState.NOT_CHECKED_SOURCE_GAP
    assert result.finding is None


def test_check_pair_returns_not_checked_source_gap_when_both_sides_uncovered():
    result = check_pair(CALCIUM, IRON, [], COVERED_IDS)
    assert result.state == PairState.NOT_CHECKED_SOURCE_GAP


def test_check_pair_found_wins_even_if_a_side_looks_uncovered():
    # Defensive: an actual rule match must win regardless of coverage
    # bookkeeping — a real Interaction row is stronger evidence than the
    # mention-tracking table ever needs to be.
    result = check_pair(ASPIRIN, CALCIUM, [rule(ASPIRIN, CALCIUM, Severity.LOW)], set())
    assert result.state == PairState.FOUND


def test_check_pair_never_returns_checked_none_found_and_not_checked_as_the_same_value():
    assert PairState.CHECKED_NONE_FOUND != PairState.NOT_CHECKED_SOURCE_GAP


def test_check_all_pairs_covers_every_combination_and_distinguishes_states():
    ingredients = [ASPIRIN, IBUPROFEN, CALCIUM]
    results = check_all_pairs(ingredients, ALL_RULES, COVERED_IDS)
    states = {frozenset({r.ingredient_a.id, r.ingredient_b.id}): r.state for r in results}

    assert states[frozenset({ASPIRIN.id, IBUPROFEN.id})] == PairState.FOUND
    # Aspirin+Calcium: Calcium uncovered -> source gap, not "none found".
    assert states[frozenset({ASPIRIN.id, CALCIUM.id})] == PairState.NOT_CHECKED_SOURCE_GAP
    assert states[frozenset({IBUPROFEN.id, CALCIUM.id})] == PairState.NOT_CHECKED_SOURCE_GAP


def test_check_all_pairs_dedupes_repeated_ingredients():
    results = check_all_pairs([ASPIRIN, ASPIRIN, IBUPROFEN], ALL_RULES, COVERED_IDS)
    assert len(results) == 1
