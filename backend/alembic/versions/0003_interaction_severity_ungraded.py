"""interaction severity ungraded

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08

DDInter marks ~47K interaction pairs "Unknown" severity rather than
Minor/Moderate/Major. Previously the loader silently dropped those rows;
now they load with severity=NULL and severity_ungraded=True instead of
being discarded — a real, sourced interaction is more useful to a safety
tool than no flag at all, as long as it's clearly distinguishable from a
graded one (see docs/api-contract.md for how the API surfaces this).
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interaction",
        sa.Column("severity_ungraded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column(
        "interaction", "severity", existing_type=sa.Enum(name="severity"), nullable=True
    )
    op.create_check_constraint(
        "ck_interaction_severity_ungraded",
        "interaction",
        "(severity IS NULL) = severity_ungraded",
    )
    # server_default was only needed to backfill existing rows to False;
    # the ORM sets it explicitly on every insert going forward.
    op.alter_column("interaction", "severity_ungraded", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_interaction_severity_ungraded", "interaction", type_="check")
    op.execute("DELETE FROM interaction WHERE severity IS NULL")
    op.alter_column(
        "interaction", "severity", existing_type=sa.Enum(name="severity"), nullable=False
    )
    op.drop_column("interaction", "severity_ungraded")
