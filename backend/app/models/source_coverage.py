from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class SourceCoverage(TimestampMixin, Base):
    """Which top-level ATC anatomical classes a source's data actually
    covers — populated at load time (see app.ingest.ddinter), not
    hand-maintained. For DDInter specifically this is derived from which
    per-category download files exist on disk, since neither DDInter's
    bulk export nor the RxNorm data on hand carries verified per-drug ATC
    codes (same limitation noted in scripts/coverage_report.py).
    """

    __tablename__ = "source_coverage"
    __table_args__ = (UniqueConstraint("source_id", "atc_class_code", name="uq_source_coverage_class"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atc_class_code: Mapped[str] = mapped_column(String(1), nullable=False)
    atc_class_label: Mapped[str] = mapped_column(String(100), nullable=False)
    covered: Mapped[bool] = mapped_column(Boolean, nullable=False)

    source: Mapped["Source"] = relationship()
