"""DB query helpers for ingest-side data-quality concerns (deprecated
ingredients, etc.) — distinct from app.findings.repository, which is
specifically the DB boundary for interaction-finding queries.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient
from app.models.ingredient_source_mention import IngredientSourceMention
from app.models.source import Source


def find_deprecated_ingredients(db: Session, source: str | None = None) -> list[Ingredient]:
    """All ingredients marked deprecated — see
    app.ingest.ingredient_resolver.IngredientResolver.deprecate(), set when
    an inn_usan/curated alias attaches to a canonical ingredient while an
    orphan with the alias's exact name already existed.

    If `source` is given (a Source.name, e.g. "DDInter"), restricted to
    deprecated ingredients that source's raw data actually mentioned (via
    ingredient_source_mention) — "which deprecated ingredients does this
    source's data still reference", useful for prioritizing which
    deprecations matter most to a given source's coverage.
    """
    stmt = select(Ingredient).where(Ingredient.deprecated.is_(True))
    if source is not None:
        stmt = (
            stmt.join(IngredientSourceMention, IngredientSourceMention.ingredient_id == Ingredient.id)
            .join(Source, Source.id == IngredientSourceMention.source_id)
            .where(Source.name == source)
        )
    return list(db.execute(stmt).scalars().all())
