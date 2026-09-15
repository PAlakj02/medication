from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AliasTier, pg_enum
from app.models.mixins import TimestampMixin


class IngredientAlias(TimestampMixin, Base):
    """An alternate name that resolves to a canonical Ingredient — NOT a
    second ingredient row. Populated by app.ingest.alias_prepass, consumed
    by app.ingest.ingredient_resolver.IngredientResolver. Every row here
    represents "this text means the same real ingredient as ingredient_id",
    never a fuzzy guess (see IngredientResolver's docstring for why fuzzy
    matching is deliberately excluded from ingest-time resolution).
    """

    __tablename__ = "ingredient_alias"
    __table_args__ = (
        # Guards idempotent re-runs (ON CONFLICT DO NOTHING), not global
        # uniqueness of alias_name — the SAME alias text CAN legitimately
        # appear once per tier if, e.g., an SY row and a later curated row
        # both mention it (tier resolution order is what decides which
        # wins at lookup time, not a DB-level uniqueness rule).
        UniqueConstraint("alias_name", "tier", name="uq_ingredient_alias_name_tier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # See Ingredient.name for why 500 (not 255) — same RxNorm-STR-length
    # reasoning applies to SY synonym text.
    alias_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    tier: Mapped[AliasTier] = mapped_column(pg_enum(AliasTier, "alias_tier"), nullable=False)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )

    ingredient: Mapped["Ingredient"] = relationship()
    source: Mapped["Source"] = relationship()
