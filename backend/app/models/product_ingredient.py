from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class ProductIngredient(TimestampMixin, Base):
    """Join table: which ingredients (at what strength) a product contains."""

    __tablename__ = "product_ingredient"
    __table_args__ = (UniqueConstraint("product_id", "ingredient_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False
    )
    # Numeric(14, 4), not (10, 3): a handful of RxNorm SBD gene-therapy
    # products carry strengths in the billions (e.g. vector-genome counts
    # per mL), which aren't a realistic "mg" dose but do need to fit if
    # encountered — genuinely astronomical outliers (10^9+, e.g. 4x10^13
    # "vector genomes") are rejected at ingest time instead, not stored;
    # see app.ingest.rxnorm_bulk.MAX_STRENGTH.
    strength_mg: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="ingredient_links")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="product_links")
