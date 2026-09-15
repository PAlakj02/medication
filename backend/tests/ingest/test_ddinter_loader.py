"""Integration test for DDInterLoader.load() — real Postgres (db_session),
since the bug this guards against only shows up after actual ingredient
resolution, not in the pure-function tests in test_ddinter_parsing.py.

Regression guard for a real bug found 2026-09-09: two DIFFERENT raw DDInter
drug-name strings that normalize to the SAME canonical ingredient (e.g.
"Warfarin Sodium" and "Warfarin", both stripping to "warfarin" via
normalize_salt_form) used to silently keep whichever severity happened to
be inserted first via ON CONFLICT DO NOTHING — checked against real data,
this affected ~887 pairs. Fixed by resolving every pair to an ingredient-id
pair BEFORE inserting and keeping only the highest-ranked severity per pair
(app.ingest.ddinter_parsing.severity_rank).
"""

from sqlalchemy import select

from app.ingest.ddinter import DDInterLoader
from app.models.ingredient import Ingredient
from app.models.interaction import Interaction


def _write_ddinter_csv(path, rows: list[tuple[str, str, str]]) -> None:
    path.write_text(
        "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"
        + "\n".join(f"DDInter1,{a},DDInter2,{b},{level}" for a, b, level in rows)
        + "\n"
    )


def test_post_resolution_collision_keeps_highest_severity_not_first_inserted(db_session, tmp_path):
    # "Warfarin Sodium" and "Warfarin" both normalize to "warfarin" via
    # salt-form stripping -- two different raw strings, same real drug.
    # "Warfarin" listed first so IT becomes the literal canonical row (the
    # first raw name processed for a never-before-seen ingredient is the
    # one that gets created) — "Warfarin Sodium" then resolves to that same
    # row via the normalized tier instead of creating its own.
    _write_ddinter_csv(
        tmp_path / "ddinter_downloads_code_A.csv",
        [
            ("Warfarin", "Aspirin", "Moderate"),
            ("Warfarin Sodium", "Aspirin", "Major"),
        ],
    )

    loader = DDInterLoader(data_dir=tmp_path)
    loader.load(db_session)

    warfarin = db_session.execute(
        select(Ingredient).where(Ingredient.name == "Warfarin")
    ).scalar_one()
    aspirin = db_session.execute(select(Ingredient).where(Ingredient.name == "Aspirin")).scalar_one()

    rows = db_session.execute(
        select(Interaction).where(
            Interaction.ingredient_a_id.in_([warfarin.id, aspirin.id]),
            Interaction.ingredient_b_id.in_([warfarin.id, aspirin.id]),
        )
    ).scalars().all()

    assert len(rows) == 1, "the two colliding raw names should produce exactly one interaction row"
    assert rows[0].severity.value == "high", (
        "must keep the higher-ranked severity (Major/high) from 'Warfarin', not whichever "
        "row (possibly the lower Moderate from 'Warfarin Sodium') happened to insert first"
    )


def test_post_resolution_collision_prefers_graded_over_ungraded(db_session, tmp_path):
    _write_ddinter_csv(
        tmp_path / "ddinter_downloads_code_A.csv",
        [
            ("Warfarin", "Ibuprofen", "Unknown"),
            ("Warfarin Sodium", "Ibuprofen", "Minor"),
        ],
    )

    loader = DDInterLoader(data_dir=tmp_path)
    loader.load(db_session)

    warfarin = db_session.execute(
        select(Ingredient).where(Ingredient.name == "Warfarin")
    ).scalar_one()
    ibuprofen = db_session.execute(
        select(Ingredient).where(Ingredient.name == "Ibuprofen")
    ).scalar_one()

    rows = db_session.execute(
        select(Interaction).where(
            Interaction.ingredient_a_id.in_([warfarin.id, ibuprofen.id]),
            Interaction.ingredient_b_id.in_([warfarin.id, ibuprofen.id]),
        )
    ).scalars().all()

    assert len(rows) == 1
    assert rows[0].severity_ungraded is False
    assert rows[0].severity.value == "low"


def test_no_collision_when_names_resolve_to_different_ingredients(db_session, tmp_path):
    _write_ddinter_csv(
        tmp_path / "ddinter_downloads_code_A.csv",
        [
            ("Warfarin", "Aspirin", "Major"),
            ("Ibuprofen", "Aspirin", "Moderate"),
        ],
    )

    loader = DDInterLoader(data_dir=tmp_path)
    loader.load(db_session)

    aspirin = db_session.execute(select(Ingredient).where(Ingredient.name == "Aspirin")).scalar_one()
    rows = db_session.execute(
        select(Interaction).where(
            (Interaction.ingredient_a_id == aspirin.id) | (Interaction.ingredient_b_id == aspirin.id)
        )
    ).scalars().all()

    assert len(rows) == 2
