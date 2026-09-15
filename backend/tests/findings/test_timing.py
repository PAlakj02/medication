from app.findings.models import IngredientRef, SourceRef, TimingRuleRecord
from app.findings.timing import find_timing_findings

SOURCE = SourceRef(id=1, name="FDA label", url=None, reference="label-section-4.2")

CALCIUM = IngredientRef(id=1, name="Calcium")
IRON = IngredientRef(id=2, name="Iron")

CALCIUM_RULE = TimingRuleRecord(
    ingredient=CALCIUM,
    rule_type="separate_from",
    offset_minutes=120,
    note="Separate from iron doses by at least 2 hours.",
    source=SOURCE,
)
IRON_RULE = TimingRuleRecord(
    ingredient=IRON,
    rule_type="take_on_empty_stomach",
    offset_minutes=None,
    note="Best absorbed on an empty stomach.",
    source=SOURCE,
)


def test_returns_empty_when_no_ingredients_present():
    assert find_timing_findings([], [CALCIUM_RULE, IRON_RULE]) == []


def test_returns_only_rules_for_present_ingredients():
    result = find_timing_findings([CALCIUM.id], [CALCIUM_RULE, IRON_RULE])
    assert len(result) == 1
    assert result[0].ingredient.name == "Calcium"


def test_returns_multiple_rules_when_multiple_ingredients_present():
    result = find_timing_findings([CALCIUM.id, IRON.id], [CALCIUM_RULE, IRON_RULE])
    assert {f.ingredient.name for f in result} == {"Calcium", "Iron"}


def test_unrelated_ingredient_does_not_trigger_rule():
    result = find_timing_findings([999], [CALCIUM_RULE, IRON_RULE])
    assert result == []
