from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import Severity, pg_enum
from app.models.mixins import TimestampMixin


class Interaction(TimestampMixin, Base):
    """A single ingredient-pair interaction rule. This table (read by
    findings/repository.py, never written by the LLM) is the *only* source
    of interaction findings — see app/findings/engine.py docstring for the
    architectural rule this enforces.
    """

    __tablename__ = "interaction"
    __table_args__ = (
        CheckConstraint("ingredient_a_id <> ingredient_b_id", name="ck_interaction_distinct_pair"),
        # Loaders (app.ingest) are responsible for canonicalizing pair order
        # (ingredient_a_id < ingredient_b_id) before insert, so this actually
        # enforces "one row per unordered pair" and lets bulk loads use
        # ON CONFLICT DO NOTHING for idempotent re-runs.
        UniqueConstraint("ingredient_a_id", "ingredient_b_id", name="uq_interaction_pair"),
        # severity NULL iff severity_ungraded is true — enforced here rather
        # than trusted to callers, since a NULL severity with
        # severity_ungraded=False would silently look like a data-loss bug
        # rather than an intentional "source didn't grade this" state.
        CheckConstraint(
            "(severity IS NULL) = severity_ungraded", name="ck_interaction_severity_ungraded"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_a_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_b_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL means the source recorded this pair without a severity grade
    # (e.g. DDInter's "Unknown" level) — see severity_ungraded below. NULL
    # does NOT mean "no interaction" or "not yet loaded"; the row still
    # represents a real, sourced interaction, just an ungraded one.
    severity: Mapped[Severity | None] = mapped_column(pg_enum(Severity, "severity"), nullable=True)
    severity_ungraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Clinical mechanism, e.g. "NSAIDs displace warfarin from protein binding
    # and irritate the GI lining." Fed to explain/ as grounding text along
    # with source_text; never generated or altered by the LLM layer.
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )
    # Verbatim excerpt from the source justifying this rule — the "RAG"
    # context explain/ is allowed to use. Required: every interaction must be
    # traceable to an actual passage, not just a source name.
    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    ingredient_a: Mapped["Ingredient"] = relationship(foreign_keys=[ingredient_a_id])
    ingredient_b: Mapped["Ingredient"] = relationship(foreign_keys=[ingredient_b_id])
    source: Mapped["Source"] = relationship(back_populates="interactions")
