from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class Source(TimestampMixin, Base):
    """A citable origin for a clinical fact — e.g. RxNav, DailyMed, CDSCO,
    Jan Aushadhi. Every Interaction and TimingRule points back to one of
    these, so every clinical finding the API returns can carry a citation.
    """

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    interactions: Mapped[list["Interaction"]] = relationship(back_populates="source")
    timing_rules: Mapped[list["TimingRule"]] = relationship(back_populates="source")
