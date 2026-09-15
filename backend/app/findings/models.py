"""Plain data shapes for the findings engine.

Deliberately NOT SQLAlchemy models and NOT Pydantic API schemas: the engine
in engine.py/timing.py must stay a pure function of plain data so it can be
unit tested with zero DB and zero HTTP layer involved. app/findings/repository.py
is the only place that translates ORM rows into these shapes; app/api/routers
translates these shapes into the Pydantic response models.
"""

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# Total order for "worst severity wins" — mirrors the frontend's precedence
# logic (high > moderate > low) exactly; see docs/api-contract.md.
_SEVERITY_RANK = {Severity.LOW: 0, Severity.MODERATE: 1, Severity.HIGH: 2}


def severity_rank(severity: Severity) -> int:
    return _SEVERITY_RANK[severity]


@dataclass(frozen=True)
class IngredientRef:
    id: int
    name: str


@dataclass(frozen=True)
class SourceRef:
    id: int
    name: str
    url: str | None
    reference: str


@dataclass(frozen=True)
class InteractionRule:
    """One row of app.models.interaction.Interaction, pre-loaded.

    severity is None iff severity_ungraded is True — the source (e.g.
    DDInter's "Unknown" level) recorded this pair without a grade. It is
    still a real, sourced interaction, not a missing/invalid row.
    """

    ingredient_a: IngredientRef
    ingredient_b: IngredientRef
    severity: Severity | None
    severity_ungraded: bool
    mechanism: str
    source: SourceRef
    source_text: str


@dataclass(frozen=True)
class Finding:
    """One interaction finding, ready for the API layer to serialize."""

    ingredient_a: IngredientRef
    ingredient_b: IngredientRef
    severity: Severity | None
    severity_ungraded: bool
    mechanism: str
    source: SourceRef
    source_text: str


@dataclass(frozen=True)
class TimingRuleRecord:
    """One row of app.models.timing_rule.TimingRule, pre-loaded."""

    ingredient: IngredientRef
    rule_type: str
    offset_minutes: int | None
    note: str | None
    source: SourceRef


@dataclass(frozen=True)
class TimingFinding:
    ingredient: IngredientRef
    rule_type: str
    offset_minutes: int | None
    note: str | None
    source: SourceRef


class PairState(str, Enum):
    """The three states a queried ingredient pair can be in — see
    app.findings.engine.check_pair. Must never collapse FOUND-less states
    into each other: a pair the source never evaluated (NOT_CHECKED_
    SOURCE_GAP) is not the same claim as "we checked and it's fine"
    (CHECKED_NONE_FOUND), and conflating them is exactly the failure mode
    this type exists to prevent.
    """

    FOUND = "found"
    CHECKED_NONE_FOUND = "checked_none_found"
    NOT_CHECKED_SOURCE_GAP = "not_checked_source_gap"


@dataclass(frozen=True)
class PairCheckResult:
    ingredient_a: IngredientRef
    ingredient_b: IngredientRef
    state: PairState
    # Populated iff state == FOUND; None otherwise — never a placeholder
    # Finding for the other two states.
    finding: Finding | None
