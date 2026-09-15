"""Timing-rule engine — same architectural rule as engine.py: deterministic,
DB-rows-only, no LLM. Separate from interaction findings because a timing
rule is a property of a single ingredient, not a pair.

Not yet wired into POST /api/analyze (docs/api-contract.md's AnalyzeResponse
has no timing field today) — the `timing_rule` table and this module exist
per the requested schema/module layout, ahead of the API contract catching
up. Flagged to the frontend/product side as an open item; see the message
accompanying this scaffold.
"""

from collections.abc import Iterable

from app.findings.models import TimingFinding, TimingRuleRecord


def find_timing_findings(
    ingredient_ids: Iterable[int],
    rules: Iterable[TimingRuleRecord],
) -> list[TimingFinding]:
    """Return every timing rule whose ingredient is in `ingredient_ids`."""
    present = set(ingredient_ids)
    findings: list[TimingFinding] = []
    for rule in rules:
        if rule.ingredient.id in present:
            findings.append(
                TimingFinding(
                    ingredient=rule.ingredient,
                    rule_type=rule.rule_type,
                    offset_minutes=rule.offset_minutes,
                    note=rule.note,
                    source=rule.source,
                )
            )
    return findings
