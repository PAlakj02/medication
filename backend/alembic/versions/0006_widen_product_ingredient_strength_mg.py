"""widen product_ingredient strength_mg

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-08

A handful of RxNorm SBD gene-therapy products carry strengths in the
billions (vector-genome counts per mL) — Numeric(10,3) overflows on them.
Widened to Numeric(14,4); genuinely astronomical outliers (10^9+) are
rejected at ingest time instead of stored — see
app.ingest.rxnorm_bulk.MAX_STRENGTH.
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "product_ingredient",
        "strength_mg",
        type_=sa.Numeric(14, 4),
        existing_type=sa.Numeric(10, 3),
    )


def downgrade() -> None:
    op.alter_column(
        "product_ingredient",
        "strength_mg",
        type_=sa.Numeric(10, 3),
        existing_type=sa.Numeric(14, 4),
    )
