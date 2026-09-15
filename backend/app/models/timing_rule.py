from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import TimingRuleType, pg_enum
from app.models.mixins import TimestampMixin


class TimingRule(TimestampMixin, Base):
    """A single-ingredient dosing-timing constraint, e.g. "separate calcium
    and iron doses by >=120 minutes". Distinct from Interaction (which is
    always an ingredient *pair*) — this is a property of one ingredient.
    """

    __tablename__ = "timing_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_type: Mapped[TimingRuleType] = mapped_column(
        pg_enum(TimingRuleType, "timing_rule_type"), nullable=False
    )
    offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )

    ingredient: Mapped["Ingredient"] = relationship()
    source: Mapped["Source"] = relationship(back_populates="timing_rules")
