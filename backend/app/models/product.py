from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import Market, OtcStatus, pg_enum
from app.models.mixins import TimestampMixin


class Product(TimestampMixin, Base):
    """A branded/marketed product, e.g. "Advil" or "Crocin". One product can
    contain multiple ingredients (combination products) via ProductIngredient.
    """

    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("name", "manufacturer", name="uq_product_name_manufacturer"),
        Index(
            "ix_product_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    market: Mapped[Market] = mapped_column(pg_enum(Market, "market"), nullable=False)
    # Nullable: none of the bulk sources ingest/ actually loads from (RxNorm,
    # the Indian medicine dataset) reliably carry OTC-vs-prescription status,
    # so forcing a value here would mean guessing it — see
    # app/ingest/indian_medicine.py and app/ingest/rxnorm_bulk.py.
    otc_status: Mapped[OtcStatus | None] = mapped_column(
        pg_enum(OtcStatus, "otc_status"), nullable=True
    )
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Added for schema parity with Ingredient.deprecated — no product-level
    # alias/dedup mechanism exists yet (ProductCache does plain get-or-
    # create, no tiered resolution), so nothing currently sets this to
    # True. Reserved for when/if one is built.
    deprecated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ingredient_links: Mapped[list["ProductIngredient"]] = relationship(back_populates="product")
