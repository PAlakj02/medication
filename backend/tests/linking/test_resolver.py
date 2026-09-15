"""Integration tests for app.linking.resolver.resolve — real Postgres
(db_session), since gazetteer matching depends on actual Ingredient/
IngredientAlias rows, not just pure logic.
"""

from app.ingest.common import get_or_create_source
from app.linking.resolver import resolve
from app.models.enums import AliasTier
from app.models.ingredient import Ingredient
from app.models.ingredient_alias import IngredientAlias
from datetime import datetime, timezone


def test_resolves_bare_drug_name_via_exact_match(db_session):
    db_session.add(Ingredient(name="Aspirin"))
    db_session.flush()

    result = resolve("Aspirin", db_session)

    assert result.matched is not None
    assert result.matched.ingredient_name == "Aspirin"
    assert result.matched.confidence == 1.0
    assert result.input_text == "Aspirin"


def test_resolves_drug_name_with_dose_and_frequency_stripped_first(db_session):
    db_session.add(Ingredient(name="Paracetamol"))
    db_session.flush()

    result = resolve("Paracetamol 500mg BD", db_session)

    assert result.matched is not None
    assert result.matched.ingredient_name == "Paracetamol"


def test_resolves_via_normalized_salt_form_tier(db_session):
    db_session.add(Ingredient(name="Diphenhydramine"))
    db_session.flush()

    result = resolve("Diphenhydramine Hydrochloride 25mg HS", db_session)

    assert result.matched is not None
    assert result.matched.ingredient_name == "Diphenhydramine"


def test_resolves_via_curated_alias_tier(db_session):
    source = get_or_create_source(
        db_session, name="Test Source", url=None, license=None, retrieved_at=datetime.now(timezone.utc)
    )
    acetaminophen = Ingredient(name="Acetaminophen")
    db_session.add(acetaminophen)
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=acetaminophen.id,
            alias_name="Paracetamol",
            tier=AliasTier.CURATED,
            source_id=source.id,
        )
    )
    db_session.flush()

    result = resolve("Paracetamol 500mg TDS", db_session)

    assert result.matched is not None
    assert result.matched.ingredient_name == "Acetaminophen"


def test_abstains_rather_than_guess_on_unknown_drug_name(db_session):
    result = resolve("SomeCompletelyUnknownDrugXYZ 10mg OD", db_session)

    assert result.matched is None
    assert result.candidates == []


def test_abstains_and_does_not_raise_on_dosage_only_text_with_no_drug_name(db_session):
    result = resolve("500mg BD", db_session)

    assert result.matched is None


def test_does_not_create_a_new_ingredient_for_unresolved_text(db_session):
    from sqlalchemy import func, select

    before = db_session.execute(select(func.count()).select_from(Ingredient)).scalar_one()
    resolve("SomeCompletelyUnknownDrugXYZ", db_session)
    after = db_session.execute(select(func.count()).select_from(Ingredient)).scalar_one()

    assert after == before, "resolve() must never mint a new ingredient from user-typed text"
