"""interaction unique pair + nullable product.otc_status

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

Driven by real ingest sources (DDInter, RxNorm, the Indian medicine
dataset): the interaction unique constraint lets bulk loaders use
ON CONFLICT DO NOTHING for idempotent re-runs, and none of those sources
reliably carries OTC-vs-prescription status, so otc_status can no longer be
forced NOT NULL without guessing it.
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_interaction_pair", "interaction", ["ingredient_a_id", "ingredient_b_id"]
    )
    op.alter_column("product", "otc_status", existing_type=sa.Enum(name="otc_status"), nullable=True)
    op.create_unique_constraint(
        "uq_product_name_manufacturer", "product", ["name", "manufacturer"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_product_name_manufacturer", "product", type_="unique")
    op.alter_column("product", "otc_status", existing_type=sa.Enum(name="otc_status"), nullable=False)
    op.drop_constraint("uq_interaction_pair", "interaction", type_="unique")
