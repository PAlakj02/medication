"""Integration test for load_covered_ingredient_ids — real Postgres, since
it depends on the actual ingredient_source_mention table and join.
"""

from datetime import datetime, timezone

from app.findings.repository import load_covered_ingredient_ids
from app.ingest.common import get_or_create_source
from app.models.ingredient import Ingredient
from app.models.ingredient_source_mention import IngredientSourceMention


def test_load_covered_ingredient_ids_returns_only_mentioned_ingredients(db_session):
    source = get_or_create_source(
        db_session, name="TestSource", url=None, license=None, retrieved_at=datetime.now(timezone.utc)
    )
    mentioned = Ingredient(name="Mentioned Drug")
    not_mentioned = Ingredient(name="Never Mentioned Drug")
    db_session.add_all([mentioned, not_mentioned])
    db_session.flush()
    db_session.add(
        IngredientSourceMention(ingredient_id=mentioned.id, source_id=source.id, atc_class_code="A")
    )
    db_session.flush()

    covered = load_covered_ingredient_ids(db_session, "TestSource")

    assert mentioned.id in covered
    assert not_mentioned.id not in covered


def test_load_covered_ingredient_ids_returns_empty_set_for_unknown_source(db_session):
    assert load_covered_ingredient_ids(db_session, "Nonexistent Source XYZ") == set()
