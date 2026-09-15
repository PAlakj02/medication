from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base
from app.models.mixins import TimestampMixin

_EMBEDDING_DIM = get_settings().embedding_dim


class Ingredient(TimestampMixin, Base):
    """Canonical salt / active ingredient, e.g. "Ibuprofen" or "Ascorbic acid".

    This is the join key for interactions and timing rules — both are
    expressed ingredient-to-ingredient, never product-to-product, so a
    generic and its ten branded equivalents all inherit the same findings.
    """

    __tablename__ = "ingredient"
    __table_args__ = (
        # Declared here (not just created via raw SQL in the migration) so
        # `alembic check` / autogenerate sees them as intentional instead of
        # flagging them as drift to remove.
        Index(
            "ix_ingredient_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_ingredient_name_embedding_hnsw",
            "name_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"name_embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 500, not 255: RxNorm's MIN (multiple-ingredient) concepts include
    # multi-antigen combination vaccine names up to ~2600 chars — p99.9 of
    # all RXNCONSO STR values is 469. Ingest/ loaders reject (not truncate)
    # anything still over MAX_INGREDIENT_NAME_LENGTH after this — see
    # app.ingest.alias_prepass — both to stay under Postgres's btree index
    # entry size limit and because those extreme outliers are multi-antigen
    # vaccine descriptions no consumer medication-interaction check needs.
    name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    atc_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rxcui: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # For linking/: semantic nearest-neighbor fallback when pg_trgm trigram
    # similarity misses (e.g. brand/alias names that share no substring with
    # the canonical name, like "Tylenol" vs "Acetaminophen"). Populated by
    # ingest/ once a name is inserted; nullable until then.
    name_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(_EMBEDDING_DIM), nullable=True
    )

    # Set by app.ingest.ingredient_resolver.IngredientResolver.deprecate()
    # when an inn_usan/curated alias attaches to a canonical ingredient
    # while an orphan ingredient with the alias's exact name already
    # existed (see that module and app.ingest.alias_prepass). The orphan
    # row is kept, not deleted or merged — existing Interaction/
    # ProductIngredient rows referencing it stay intact (history
    # preserved) — but it stops participating in exact/normalized
    # resolution, so future lookups reach the alias instead.
    deprecated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product_links: Mapped[list["ProductIngredient"]] = relationship(back_populates="ingredient")
