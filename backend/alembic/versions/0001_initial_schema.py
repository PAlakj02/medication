"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-05

Creates the six tables from the requested schema (source, ingredient,
product, product_ingredient, interaction, timing_rule), enables pg_trgm and
pgvector, and adds the fuzzy-matching indexes linking/ will need: trigram
GIN indexes on ingredient.name / product.name, and an HNSW index on
ingredient.name_embedding.
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Keep in sync with app.config.Settings.embedding_dim.
EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    severity = sa.Enum("high", "moderate", "low", name="severity")
    market = sa.Enum("US", "IN", name="market")
    otc_status = sa.Enum("OTC", "RX", name="otc_status")
    timing_rule_type = sa.Enum(
        "separate_from",
        "take_with_food",
        "take_on_empty_stomach",
        "avoid_alcohol",
        "monitor",
        "other",
        name="timing_rule_type",
    )

    op.create_table(
        "source",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("license", sa.String(255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ingredient",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("atc_code", sa.String(16), nullable=True),
        sa.Column("rxcui", sa.String(16), nullable=True),
        sa.Column("name_embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # A single unique index, matching the model's
    # mapped_column(..., unique=True, index=True) exactly — not a separate
    # named UniqueConstraint plus a non-unique index (that mismatch is
    # exactly what `alembic check` caught).
    op.create_index("ix_ingredient_name", "ingredient", ["name"], unique=True)
    op.execute("CREATE INDEX ix_ingredient_name_trgm ON ingredient USING gin (name gin_trgm_ops)")
    # HNSW requires pgvector >= 0.5.0 server-side. Targeting an older
    # pgvector? Swap for `USING ivfflat (name_embedding vector_cosine_ops)
    # WITH (lists = 100)` and build it after backfilling data, not before.
    op.execute(
        "CREATE INDEX ix_ingredient_name_embedding_hnsw ON ingredient "
        "USING hnsw (name_embedding vector_cosine_ops)"
    )

    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("market", market, nullable=False),
        sa.Column("otc_status", otc_status, nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_name", "product", ["name"])
    op.execute("CREATE INDEX ix_product_name_trgm ON product USING gin (name gin_trgm_ops)")

    op.create_table(
        "product_ingredient",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("product.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredient.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strength_mg", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "ingredient_id", name="uq_product_ingredient"),
    )

    op.create_table(
        "interaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ingredient_a_id",
            sa.Integer(),
            sa.ForeignKey("ingredient.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_b_id",
            sa.Integer(),
            sa.ForeignKey("ingredient.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", severity, nullable=False),
        sa.Column("mechanism", sa.Text(), nullable=False),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ingredient_a_id <> ingredient_b_id", name="ck_interaction_distinct_pair"
        ),
    )
    op.create_index("ix_interaction_ingredient_a_id", "interaction", ["ingredient_a_id"])
    op.create_index("ix_interaction_ingredient_b_id", "interaction", ["ingredient_b_id"])

    op.create_table(
        "timing_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredient.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_type", timing_rule_type, nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_timing_rule_ingredient_id", "timing_rule", ["ingredient_id"])


def downgrade() -> None:
    op.drop_table("timing_rule")
    op.drop_table("interaction")
    op.drop_table("product_ingredient")
    op.execute("DROP INDEX IF EXISTS ix_product_name_trgm")
    op.drop_table("product")
    op.execute("DROP INDEX IF EXISTS ix_ingredient_name_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_ingredient_name_trgm")
    op.drop_table("ingredient")
    op.drop_table("source")

    bind = op.get_bind()
    sa.Enum(name="timing_rule_type").drop(bind, checkfirst=True)
    sa.Enum(name="otc_status").drop(bind, checkfirst=True)
    sa.Enum(name="market").drop(bind, checkfirst=True)
    sa.Enum(name="severity").drop(bind, checkfirst=True)
