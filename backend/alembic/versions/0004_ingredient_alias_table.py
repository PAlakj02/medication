"""ingredient alias table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08

Backs the alias resolution layer (app.ingest.ingredient_resolver): SY
synonyms from RxNorm and hand-curated aliases (data/aliases.csv) both
resolve to an EXISTING ingredient row, never create a new one.
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    alias_tier = sa.Enum("sy", "curated", name="alias_tier")

    op.create_table(
        "ingredient_alias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredient.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_name", sa.String(255), nullable=False),
        sa.Column("tier", alias_tier, nullable=False),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("alias_name", "tier", name="uq_ingredient_alias_name_tier"),
    )
    op.create_index("ix_ingredient_alias_ingredient_id", "ingredient_alias", ["ingredient_id"])
    op.create_index("ix_ingredient_alias_alias_name", "ingredient_alias", ["alias_name"])


def downgrade() -> None:
    op.drop_table("ingredient_alias")
    op.execute("DROP TYPE IF EXISTS alias_tier")
