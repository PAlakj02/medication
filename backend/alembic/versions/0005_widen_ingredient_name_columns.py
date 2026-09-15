"""widen ingredient name columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-08

RxNorm's MIN (multiple-ingredient) concepts include multi-antigen
combination vaccine names up to ~2600 chars (p99.9 of all RXNCONSO STR
values is 469; 255 was too tight). ingest/ rejects anything still over
MAX_INGREDIENT_NAME_LENGTH (500) rather than truncating — see
app.ingest.alias_prepass.
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ingredient", "name", type_=sa.String(500), existing_type=sa.String(255))
    op.alter_column(
        "ingredient_alias", "alias_name", type_=sa.String(500), existing_type=sa.String(255)
    )


def downgrade() -> None:
    op.alter_column(
        "ingredient_alias", "alias_name", type_=sa.String(255), existing_type=sa.String(500)
    )
    op.alter_column("ingredient", "name", type_=sa.String(255), existing_type=sa.String(500))
