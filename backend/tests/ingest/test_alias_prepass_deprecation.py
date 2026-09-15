"""Tests for the deprecate-on-conflict behavior in
app.ingest.alias_prepass._maybe_deprecate_orphan — the mechanism that
handles "Paracetamol-type" cases: an inn_usan/curated alias attaching to a
canonical ingredient while an orphan with the alias's exact name already
exists.
"""

from datetime import datetime, timezone

from app.ingest.alias_prepass import _maybe_deprecate_orphan
from app.ingest.common import get_or_create_source
from app.ingest.ingredient_resolver import IngredientResolver
from app.ingest.repository import find_deprecated_ingredients
from app.models.enums import AliasTier
from app.models.ingredient import Ingredient
from app.models.ingredient_alias import IngredientAlias


def _source(db):
    return get_or_create_source(
        db, name="Test Source", url=None, license=None, retrieved_at=datetime.now(timezone.utc)
    )


def test_deprecates_true_orphan_sharing_the_alias_name(db_session):
    orphan = Ingredient(name="Paracetamol", rxcui=None)
    canonical = Ingredient(name="acetaminophen", rxcui="161")
    db_session.add_all([orphan, canonical])
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    deprecated = _maybe_deprecate_orphan(resolver, "Paracetamol", canonical)

    assert deprecated is True
    assert orphan.deprecated is True


def test_does_not_deprecate_when_alias_name_has_no_existing_ingredient(db_session):
    canonical = Ingredient(name="acetaminophen", rxcui="161")
    db_session.add(canonical)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    deprecated = _maybe_deprecate_orphan(resolver, "Paracetamol", canonical)
    assert deprecated is False


def test_does_not_deprecate_when_existing_is_itself_a_real_canonical(db_session):
    # "doxycycline hyclate" vs "doxycycline" -- both independently real
    # RxNorm ingredients, not an orphan/canonical pair.
    doxycycline = Ingredient(name="doxycycline", rxcui="3640")
    doxycycline_hyclate = Ingredient(name="doxycycline hyclate", rxcui="23663")
    db_session.add_all([doxycycline, doxycycline_hyclate])
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    deprecated = _maybe_deprecate_orphan(resolver, "doxycycline hyclate", doxycycline)

    assert deprecated is False
    assert doxycycline_hyclate.deprecated is False


def test_does_not_deprecate_for_a_sy_match(db_session):
    source = _source(db_session)
    sy_target = Ingredient(name="SY Target", rxcui="1")
    other_orphan = Ingredient(name="Some Orphan", rxcui=None)
    db_session.add_all([sy_target, other_orphan])
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=sy_target.id, alias_name="Aliased Name", tier=AliasTier.SY, source_id=source.id
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    # "Aliased Name" resolves via sy (not exact) -- must not deprecate
    # sy_target even though it's a different ingredient than other_orphan.
    deprecated = _maybe_deprecate_orphan(resolver, "Aliased Name", other_orphan)
    assert deprecated is False
    assert sy_target.deprecated is False


def test_does_not_deprecate_for_a_normalized_spelling_match(db_session):
    normalized_target = Ingredient(name="Diphenhydramine", rxcui="1")
    other_canonical = Ingredient(name="Some Other Canonical", rxcui="2")
    db_session.add_all([normalized_target, other_canonical])
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    # "Diphenhydramine Hydrochloride" resolves via normalized (salt-form
    # stripping), not exact -- must not deprecate.
    deprecated = _maybe_deprecate_orphan(
        resolver, "Diphenhydramine Hydrochloride", other_canonical
    )
    assert deprecated is False
    assert normalized_target.deprecated is False


def test_does_not_deprecate_when_alias_already_points_at_the_same_target(db_session):
    canonical = Ingredient(name="acetaminophen", rxcui="161")
    db_session.add(canonical)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    # alias_name IS the canonical's own name -- nothing to deprecate.
    deprecated = _maybe_deprecate_orphan(resolver, "acetaminophen", canonical)
    assert deprecated is False


def test_find_deprecated_ingredients_returns_only_deprecated_rows(db_session):
    deprecated_one = Ingredient(name="Deprecated One", rxcui=None, deprecated=True)
    normal_one = Ingredient(name="Normal One", rxcui="1", deprecated=False)
    db_session.add_all([deprecated_one, normal_one])
    db_session.flush()

    result = find_deprecated_ingredients(db_session)

    result_ids = {i.id for i in result}
    assert deprecated_one.id in result_ids
    assert normal_one.id not in result_ids


def test_find_deprecated_ingredients_filters_by_source(db_session):
    from app.models.ingredient_source_mention import IngredientSourceMention

    source_a = get_or_create_source(
        db_session, name="Source A", url=None, license=None, retrieved_at=datetime.now(timezone.utc)
    )
    source_b = get_or_create_source(
        db_session, name="Source B", url=None, license=None, retrieved_at=datetime.now(timezone.utc)
    )
    dep_in_a = Ingredient(name="Deprecated In A", rxcui=None, deprecated=True)
    dep_in_b = Ingredient(name="Deprecated In B", rxcui=None, deprecated=True)
    db_session.add_all([dep_in_a, dep_in_b])
    db_session.flush()
    db_session.add_all(
        [
            IngredientSourceMention(ingredient_id=dep_in_a.id, source_id=source_a.id, atc_class_code=None),
            IngredientSourceMention(ingredient_id=dep_in_b.id, source_id=source_b.id, atc_class_code=None),
        ]
    )
    db_session.flush()

    result = find_deprecated_ingredients(db_session, source="Source A")

    result_ids = {i.id for i in result}
    assert dep_in_a.id in result_ids
    assert dep_in_b.id not in result_ids
