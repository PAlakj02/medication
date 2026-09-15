"""Integration tests for IngredientResolver — real Postgres (via db_session),
since the resolution tiers depend on actual DB rows (Ingredient,
IngredientAlias) and the enums/constraints around them, not just pure logic.
"""

from datetime import datetime, timezone

from app.ingest.common import get_or_create_source
from app.ingest.ingredient_resolver import IngredientResolver
from app.models.enums import AliasTier
from app.models.ingredient import Ingredient
from app.models.ingredient_alias import IngredientAlias


def _source(db):
    return get_or_create_source(
        db, name="Test Source", url=None, license=None, retrieved_at=datetime.now(timezone.utc)
    )


def test_exact_tier_matches_case_insensitively(db_session):
    db_session.add(Ingredient(name="Aspirin"))
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("aspirin")
    assert tier == "exact"
    assert ingredient.name == "Aspirin"


def test_sy_tier_resolves_rxnorm_synonym_to_canonical_ingredient(db_session):
    source = _source(db_session)
    aspirin = Ingredient(name="Aspirin")
    db_session.add(aspirin)
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=aspirin.id,
            alias_name="Acetylsalicylic acid",
            tier=AliasTier.SY,
            source_id=source.id,
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Acetylsalicylic acid")
    assert tier == "sy"
    assert ingredient.id == aspirin.id


def test_normalized_tier_strips_salt_form_suffix(db_session):
    db_session.add(Ingredient(name="Diphenhydramine"))
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Diphenhydramine Hydrochloride")
    assert tier == "normalized"
    assert ingredient.name == "Diphenhydramine"


def test_curated_tier_resolves_hand_curated_alias(db_session):
    source = _source(db_session)
    tylenol_ingredient = Ingredient(name="Acetaminophen")
    db_session.add(tylenol_ingredient)
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=tylenol_ingredient.id,
            alias_name="Tylenol Active",
            tier=AliasTier.CURATED,
            source_id=source.id,
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Tylenol Active")
    assert tier == "curated"
    assert ingredient.id == tylenol_ingredient.id


def test_resolution_order_exact_beats_everything(db_session):
    source = _source(db_session)
    real_match = Ingredient(name="Aspirin")
    decoy = Ingredient(name="Decoy")
    db_session.add_all([real_match, decoy])
    db_session.flush()
    # An SY alias that (if checked) would resolve "Aspirin" to the wrong
    # ingredient — exact match must win before SY is even consulted.
    db_session.add(
        IngredientAlias(
            ingredient_id=decoy.id, alias_name="Aspirin", tier=AliasTier.SY, source_id=source.id
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Aspirin")
    assert tier == "exact"
    assert ingredient.id == real_match.id


def test_resolution_order_sy_beats_normalized(db_session):
    source = _source(db_session)
    sy_target = Ingredient(name="SY Target")
    normalized_target = Ingredient(name="Diphenhydramine")
    db_session.add_all([sy_target, normalized_target])
    db_session.flush()
    # "Diphenhydramine Hydrochloride" would also resolve via the normalized
    # tier (stripping "Hydrochloride") to normalized_target — SY must win.
    db_session.add(
        IngredientAlias(
            ingredient_id=sy_target.id,
            alias_name="Diphenhydramine Hydrochloride",
            tier=AliasTier.SY,
            source_id=source.id,
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Diphenhydramine Hydrochloride")
    assert tier == "sy"
    assert ingredient.id == sy_target.id


def test_resolution_order_normalized_beats_curated(db_session):
    source = _source(db_session)
    normalized_target = Ingredient(name="Diphenhydramine")
    curated_target = Ingredient(name="Curated Target")
    db_session.add_all([normalized_target, curated_target])
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=curated_target.id,
            alias_name="Diphenhydramine Hydrochloride",
            tier=AliasTier.CURATED,
            source_id=source.id,
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Diphenhydramine Hydrochloride")
    assert tier == "normalized"
    assert ingredient.id == normalized_target.id


def test_inn_usan_tier_resolves_documented_divergence(db_session):
    source = _source(db_session)
    acetaminophen = Ingredient(name="acetaminophen")
    db_session.add(acetaminophen)
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=acetaminophen.id,
            alias_name="Paracetamol",
            tier=AliasTier.INN_USAN,
            source_id=source.id,
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Paracetamol")
    assert tier == "inn_usan"
    assert ingredient.id == acetaminophen.id


def test_resolution_order_normalized_beats_inn_usan(db_session):
    source = _source(db_session)
    normalized_target = Ingredient(name="Diphenhydramine")
    inn_usan_target = Ingredient(name="INN/USAN Target")
    db_session.add_all([normalized_target, inn_usan_target])
    db_session.flush()
    db_session.add(
        IngredientAlias(
            ingredient_id=inn_usan_target.id,
            alias_name="Diphenhydramine Hydrochloride",
            tier=AliasTier.INN_USAN,
            source_id=source.id,
        )
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Diphenhydramine Hydrochloride")
    assert tier == "normalized"
    assert ingredient.id == normalized_target.id


def test_resolution_order_inn_usan_beats_curated(db_session):
    source = _source(db_session)
    inn_usan_target = Ingredient(name="INN Target")
    curated_target = Ingredient(name="Curated Target")
    db_session.add_all([inn_usan_target, curated_target])
    db_session.flush()
    db_session.add_all(
        [
            IngredientAlias(
                ingredient_id=inn_usan_target.id,
                alias_name="Shared Alias Name",
                tier=AliasTier.INN_USAN,
                source_id=source.id,
            ),
            IngredientAlias(
                ingredient_id=curated_target.id,
                alias_name="Shared Alias Name",
                tier=AliasTier.CURATED,
                source_id=source.id,
            ),
        ]
    )
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Shared Alias Name")
    assert tier == "inn_usan"
    assert ingredient.id == inn_usan_target.id


def test_unresolved_name_returns_none_and_get_or_create_makes_a_new_row(db_session):
    resolver = IngredientResolver(db_session)
    resolver.warm()

    ingredient, tier = resolver.resolve("Some Brand New Ingredient")
    assert ingredient is None
    assert tier == "unresolved"

    created = resolver.get_or_create("Some Brand New Ingredient")
    assert created.name == "Some Brand New Ingredient"
    assert resolver.tier_counts["created"] == 1
    assert resolver.created_count == 1

    # A second call for the same (now-known) name resolves exact, not create.
    again = resolver.get_or_create("some brand new ingredient")
    assert again.id == created.id
    assert resolver.tier_counts["exact"] == 1
    assert resolver.tier_counts["created"] == 1


def test_register_alias_takes_effect_without_rewarming(db_session):
    ingredient = Ingredient(name="Aspirin")
    db_session.add(ingredient)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    assert resolver.resolve("ASA")[1] == "unresolved"
    resolver.register_alias("ASA", ingredient, AliasTier.SY)
    result, tier = resolver.resolve("ASA")
    assert tier == "sy"
    assert result.id == ingredient.id


def test_get_or_create_canonical_backfills_missing_rxcui(db_session):
    ingredient = Ingredient(name="Aspirin", rxcui=None)
    db_session.add(ingredient)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    result = resolver.get_or_create_canonical("Aspirin", rxcui="1191")
    assert result.id == ingredient.id
    assert result.rxcui == "1191"


def test_get_or_create_canonical_does_not_overwrite_existing_rxcui(db_session):
    ingredient = Ingredient(name="Aspirin", rxcui="1191")
    db_session.add(ingredient)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    result = resolver.get_or_create_canonical("Aspirin", rxcui="9999")
    assert result.rxcui == "1191"


# --- deprecate() --------------------------------------------------------


def test_deprecate_sets_flag_and_removes_from_exact_matching(db_session):
    orphan = Ingredient(name="Acetylsalicylic Acid", rxcui=None)
    db_session.add(orphan)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()
    assert resolver.resolve("Acetylsalicylic Acid")[1] == "exact"

    resolver.deprecate(orphan)

    assert orphan.deprecated is True
    ingredient, tier = resolver.resolve("Acetylsalicylic Acid")
    assert tier == "unresolved"
    assert ingredient is None


def test_deprecate_removes_from_normalized_matching_too(db_session):
    orphan = Ingredient(name="Diphenhydramine Hydrochloride", rxcui=None)
    db_session.add(orphan)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()
    # Its own exact name still wins over normalizing itself, but a
    # DIFFERENT raw name that normalizes to it should also stop working
    # after deprecation.
    resolver.deprecate(orphan)

    ingredient, tier = resolver.resolve("Diphenhydramine")
    assert tier != "normalized"


def test_deprecated_ingredient_loaded_via_warm_is_excluded_from_exact(db_session):
    ingredient = Ingredient(name="Old Orphan Name", rxcui=None, deprecated=True)
    db_session.add(ingredient)
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()

    assert resolver.resolve("Old Orphan Name") == (None, "unresolved")
    # Still trackable by id even though invisible to resolve().
    assert resolver.get_by_id(ingredient.id) is ingredient


def test_deprecated_ingredient_does_not_shadow_alias_after_deprecation(db_session):
    source = _source(db_session)
    orphan = Ingredient(name="Paracetamol", rxcui=None)
    canonical = Ingredient(name="acetaminophen", rxcui="161")
    db_session.add_all([orphan, canonical])
    db_session.flush()

    resolver = IngredientResolver(db_session)
    resolver.warm()
    # Before deprecation: exact match on the orphan shadows everything.
    assert resolver.resolve("Paracetamol")[1] == "exact"

    resolver.deprecate(orphan)
    resolver.register_alias("Paracetamol", canonical, AliasTier.INN_USAN)

    ingredient, tier = resolver.resolve("Paracetamol")
    assert tier == "inn_usan"
    assert ingredient.id == canonical.id
