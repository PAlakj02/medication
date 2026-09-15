from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class IngredientSourceMention(TimestampMixin, Base):
    """Records that a source's raw data mentioned this ingredient AT ALL —
    populated at load time (see app.ingest.ddinter). This is the ground
    truth behind the 3-state interaction query
    (app.findings.engine.check_pair): an ingredient with NO mention row for
    a given source means that source never evaluated it for anything, so a
    "no interaction found" result for a pair involving it is
    NOT_CHECKED_SOURCE_GAP, not CHECKED_NONE_FOUND — those two must never
    collapse into each other.

    One row per (ingredient, source) — not one per raw CSV row, since the
    same ingredient appears in many interaction pairs and this table only
    needs to answer "was it ever mentioned," not "how many times."

    atc_class_code is nullable and, when set, reflects only a
    Drug_A-position mention. DDInter's per-category file split appears to
    be organized by the FIRST drug's category — inspection showed e.g. an
    antineoplastic paired with an antiretroviral landing in the
    antineoplastic ("L") file, not the antiretroviral's — but this is NOT
    verified against DDInter's own documentation. Drug_B-position mentions
    are recorded with atc_class_code=NULL rather than guessing they share
    the pair's class.
    """

    __tablename__ = "ingredient_source_mention"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "source_id", name="uq_ingredient_source_mention"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atc_class_code: Mapped[str | None] = mapped_column(String(1), nullable=True)

    ingredient: Mapped["Ingredient"] = relationship()
    source: Mapped["Source"] = relationship()
