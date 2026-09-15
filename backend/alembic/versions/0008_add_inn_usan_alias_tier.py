"""add inn_usan alias tier

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-08

New alias resolution tier backed by the hand-verified data/inn_usan_map.csv
(documented INN/USAN naming divergences, e.g. paracetamol/acetaminophen).
Sits between "normalized" and "curated" in app.ingest.ingredient_resolver's
resolution order — see AliasTier's docstring.

Postgres enum values can't be dropped, only added — ADD VALUE also can't
run in the same transaction as anything that uses the new value, which is
fine here since this migration only adds it. The downgrade rebuilds the
type from scratch (the only way to truly remove a value) and refuses if any
row still uses 'inn_usan', rather than silently deleting data.
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE alias_tier ADD VALUE IF NOT EXISTS 'inn_usan'")


def downgrade() -> None:
    conn = op.get_bind()
    (in_use,) = conn.exec_driver_sql(
        "SELECT count(*) FROM ingredient_alias WHERE tier = 'inn_usan'"
    ).fetchone()
    if in_use:
        raise RuntimeError(
            f"{in_use} ingredient_alias row(s) still use tier='inn_usan' — "
            "delete them before downgrading past this migration."
        )
    op.execute("ALTER TYPE alias_tier RENAME TO alias_tier_old")
    op.execute("CREATE TYPE alias_tier AS ENUM ('sy', 'curated')")
    op.execute(
        "ALTER TABLE ingredient_alias ALTER COLUMN tier TYPE alias_tier "
        "USING tier::text::alias_tier"
    )
    op.execute("DROP TYPE alias_tier_old")
