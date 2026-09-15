"""deprecated column on ingredient and product

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-08

ingredient.deprecated backs the alias-resolver fix for "Paracetamol-type"
cases: when an inn_usan/curated alias attaches to a canonical ingredient
while an orphan with the alias's exact name already exists, the orphan is
marked deprecated (not deleted/merged) rather than left to silently shadow
the alias forever. product.deprecated is schema parity for now — nothing
sets it yet, no product-level alias mechanism exists.
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingredient", sa.Column("deprecated", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column("ingredient", "deprecated", server_default=None)

    op.add_column(
        "product", sa.Column("deprecated", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column("product", "deprecated", server_default=None)


def downgrade() -> None:
    op.drop_column("product", "deprecated")
    op.drop_column("ingredient", "deprecated")
