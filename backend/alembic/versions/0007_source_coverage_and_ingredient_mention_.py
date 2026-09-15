"""source coverage and ingredient mention tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-08

Backs the 3-state interaction query (app.findings.engine.check_pair):
source_coverage records which ATC top-level classes a source's data
actually covers; ingredient_source_mention records which ingredients that
source's raw data mentioned at all. An ingredient absent from
ingredient_source_mention for a source means that source never evaluated
it — a "no interaction found" involving it is NOT_CHECKED_SOURCE_GAP, not
CHECKED_NONE_FOUND.
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_coverage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("source.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("atc_class_code", sa.String(1), nullable=False),
        sa.Column("atc_class_label", sa.String(100), nullable=False),
        sa.Column("covered", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "atc_class_code", name="uq_source_coverage_class"),
    )
    op.create_index("ix_source_coverage_source_id", "source_coverage", ["source_id"])

    op.create_table(
        "ingredient_source_mention",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredient.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("source.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("atc_class_code", sa.String(1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ingredient_id", "source_id", name="uq_ingredient_source_mention"),
    )
    op.create_index("ix_ingredient_source_mention_ingredient_id", "ingredient_source_mention", ["ingredient_id"])
    op.create_index("ix_ingredient_source_mention_source_id", "ingredient_source_mention", ["source_id"])


def downgrade() -> None:
    op.drop_table("ingredient_source_mention")
    op.drop_table("source_coverage")
