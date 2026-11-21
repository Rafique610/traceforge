"""patches, validation_runs, reviews (all insert-only)

Hand-written; matches traceforge/repair/models.py and traceforge/reviews/models.py.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

Json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _incident_fk() -> sa.Column:
    return sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "patches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _incident_fk(),
        sa.Column("diff", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("paths", Json, nullable=False),
        sa.Column("signature_changed", sa.Boolean(), nullable=False),
        sa.Column("impact", Json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("incident_id", name="uq_patches_incident_id"),
    )
    op.create_index("ix_patches_incident_id", "patches", ["incident_id"])
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _incident_fk(),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("suite", sa.String(16), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("tests", Json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "suite in ('reproducer','visible','hidden')", name="ck_validation_suite"
        ),
    )
    op.create_index("ix_validation_runs_incident_id", "validation_runs", ["incident_id"])
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _incident_fk(),
        sa.Column("patch_sha256", sa.String(64)),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reviewer", sa.String(80), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision in ('approve','reject')", name="ck_reviews_decision"),
        sa.UniqueConstraint("incident_id", name="uq_reviews_incident_id"),
    )
    op.create_index("ix_reviews_incident_id", "reviews", ["incident_id"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("validation_runs")
    op.drop_table("patches")
