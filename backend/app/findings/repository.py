"""The DB boundary for findings/. This is the ONLY module in findings/ that
may import SQLAlchemy models or take a Session — engine.py and timing.py stay
pure. Converts ORM rows into the plain dataclasses in app.findings.models.
"""

from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.findings.models import Severity as FindingSeverity
from app.findings.models import IngredientRef, InteractionRule, SourceRef, TimingRuleRecord
from app.models.ingredient_source_mention import IngredientSourceMention
from app.models.interaction import Interaction
from app.models.source import Source
from app.models.timing_rule import TimingRule


def _source_ref(source) -> SourceRef:  # noqa: ANN001 — app.models.source.Source
    return SourceRef(id=source.id, name=source.name, url=source.url, reference=source.name)


def load_interaction_rules(db: Session, ingredient_ids: Iterable[int]) -> list[InteractionRule]:
    """Load every interaction rule touching at least one of `ingredient_ids`.

    Loads a superset (either side matches) rather than requiring both sides
    up front — find_interactions() in engine.py does the precise "both sides
    present" filter. This keeps the SQL simple and the actual matching logic
    in one pure, testable place.
    """
    ids = list(ingredient_ids)
    if not ids:
        return []

    stmt = select(Interaction).where(
        or_(
            Interaction.ingredient_a_id.in_(ids),
            Interaction.ingredient_b_id.in_(ids),
        )
    )
    rows = db.execute(stmt).scalars().all()

    return [
        InteractionRule(
            ingredient_a=IngredientRef(id=row.ingredient_a.id, name=row.ingredient_a.name),
            ingredient_b=IngredientRef(id=row.ingredient_b.id, name=row.ingredient_b.name),
            # Explicit conversion between app.models.enums.Severity (the DB/ORM
            # enum) and app.findings.models.Severity (the pure-layer enum) —
            # findings/ intentionally has zero import dependency on app.models,
            # so it defines its own equivalent enum rather than importing the
            # ORM one. None passes through as None (ungraded pair).
            severity=FindingSeverity(row.severity.value) if row.severity is not None else None,
            severity_ungraded=row.severity_ungraded,
            mechanism=row.mechanism,
            source=_source_ref(row.source),
            source_text=row.source_text,
        )
        for row in rows
    ]


def load_covered_ingredient_ids(db: Session, source_name: str) -> set[int]:
    """The ground truth for app.findings.engine.check_pair's
    NOT_CHECKED_SOURCE_GAP state: every ingredient_id the named source's
    raw data ever mentioned (app.models.ingredient_source_mention,
    populated at load time — see app.ingest.ddinter). Returns an empty set
    if the source doesn't exist or has no mentions recorded, which
    correctly makes check_pair treat every pair as a source gap rather
    than raising.
    """
    stmt = (
        select(IngredientSourceMention.ingredient_id)
        .join(Source, Source.id == IngredientSourceMention.source_id)
        .where(Source.name == source_name)
    )
    return set(db.execute(stmt).scalars().all())


def load_timing_rules(db: Session, ingredient_ids: Iterable[int]) -> list[TimingRuleRecord]:
    ids = list(ingredient_ids)
    if not ids:
        return []

    stmt = select(TimingRule).where(TimingRule.ingredient_id.in_(ids))
    rows = db.execute(stmt).scalars().all()

    return [
        TimingRuleRecord(
            ingredient=IngredientRef(id=row.ingredient.id, name=row.ingredient.name),
            rule_type=row.rule_type.value,
            offset_minutes=row.offset_minutes,
            note=row.note,
            source=_source_ref(row.source),
        )
        for row in rows
    ]
