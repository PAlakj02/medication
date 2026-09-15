"""The interaction rules engine.

ARCHITECTURAL RULE (do not violate): an interaction finding is produced ONLY
by matching database rows (app.models.interaction.Interaction) against the
set of detected ingredients. There is no path, anywhere in this module, that
calls an LLM or any model inference. Findings are deterministic and fully
reproducible from the `interaction` table.

This module must never import anything from app.explain (the LLM layer). The
LLM's only job, done elsewhere, is to turn a Finding + its source_text into
human-readable prose — it does not get a vote on whether a Finding exists.

Kept as pure functions over plain dataclasses (app.findings.models) — no
SQLAlchemy Session, no FastAPI request — so this is unit-testable with
in-memory fixtures only. See tests/findings/test_engine.py.
"""

from collections.abc import Iterable
from itertools import combinations

from app.findings.models import Finding, IngredientRef, InteractionRule, PairCheckResult, PairState


def find_interactions(
    ingredient_ids: Iterable[int],
    rules: Iterable[InteractionRule],
) -> list[Finding]:
    """Return every rule where both sides are present in `ingredient_ids`.

    Mirrors the frontend mock's findInteractions() (pill-check/src/lib/med-data.ts)
    exactly: interactions are computed over the *set* of recognized
    ingredients, not tied to any particular input token or ordering.
    """
    present = set(ingredient_ids)
    findings: list[Finding] = []
    for rule in rules:
        if rule.ingredient_a.id in present and rule.ingredient_b.id in present:
            findings.append(
                Finding(
                    ingredient_a=rule.ingredient_a,
                    ingredient_b=rule.ingredient_b,
                    severity=rule.severity,
                    severity_ungraded=rule.severity_ungraded,
                    mechanism=rule.mechanism,
                    source=rule.source,
                    source_text=rule.source_text,
                )
            )
    return findings


def check_pair(
    ingredient_a: IngredientRef,
    ingredient_b: IngredientRef,
    rules: Iterable[InteractionRule],
    covered_ingredient_ids: set[int],
) -> PairCheckResult:
    """The 3-state query for one specific pair — distinct from
    find_interactions(), which only ever reports hits and silently omits
    everything else. Never collapse the no-hit cases:

      - FOUND: a rule matches this exact pair (graded or ungraded — both
        are real findings, see InteractionRule's severity_ungraded).
      - CHECKED_NONE_FOUND: no rule matches, but the source's data
        mentioned BOTH ingredients somewhere (covered_ingredient_ids) — it
        had the chance to report this combination and didn't.
      - NOT_CHECKED_SOURCE_GAP: no rule matches, and at least one
        ingredient was never mentioned by the source at all
        (covered_ingredient_ids is built from
        app.models.ingredient_source_mention — see
        app.findings.repository.load_covered_ingredient_ids). A "no
        interaction" result here means "we don't know", not "it's safe".
    """
    for rule in rules:
        matches = {rule.ingredient_a.id, rule.ingredient_b.id} == {ingredient_a.id, ingredient_b.id}
        if matches:
            finding = Finding(
                ingredient_a=rule.ingredient_a,
                ingredient_b=rule.ingredient_b,
                severity=rule.severity,
                severity_ungraded=rule.severity_ungraded,
                mechanism=rule.mechanism,
                source=rule.source,
                source_text=rule.source_text,
            )
            return PairCheckResult(
                ingredient_a=ingredient_a, ingredient_b=ingredient_b, state=PairState.FOUND, finding=finding
            )

    both_covered = ingredient_a.id in covered_ingredient_ids and ingredient_b.id in covered_ingredient_ids
    state = PairState.CHECKED_NONE_FOUND if both_covered else PairState.NOT_CHECKED_SOURCE_GAP
    return PairCheckResult(ingredient_a=ingredient_a, ingredient_b=ingredient_b, state=state, finding=None)


def check_all_pairs(
    ingredients: Iterable[IngredientRef],
    rules: Iterable[InteractionRule],
    covered_ingredient_ids: set[int],
) -> list[PairCheckResult]:
    """check_pair() for every combination among `ingredients` — O(n²) rule
    scans, fine for the small detected-ingredient lists this is meant for
    (a pasted medication list), not a bulk operation."""
    rules = list(rules)
    unique = dedupe_ingredients(ingredients)
    return [
        check_pair(a, b, rules, covered_ingredient_ids) for a, b in combinations(unique, 2)
    ]


def dedupe_ingredients(ingredients: Iterable[IngredientRef]) -> list[IngredientRef]:
    """Stable de-dup by id — mirrors the frontend's dedup-by-recognized-name
    behavior in detect() (src/lib/med-data.ts:272-277). Kept here (rather
    than left to callers) since interaction lookup and any future
    ingredient-level aggregation both need the same de-dup semantics.
    """
    seen: set[int] = set()
    out: list[IngredientRef] = []
    for ing in ingredients:
        if ing.id in seen:
            continue
        seen.add(ing.id)
        out.append(ing)
    return out
