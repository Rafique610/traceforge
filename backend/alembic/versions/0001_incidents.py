"""incidents, evidence_items, audit_events

Hand-written (no Postgres was available to autogenerate against); matches
traceforge/incidents/models.py. Target: PostgreSQL 16. NOT yet applied on Postgres.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATES = (
    "CREATED",
    "SNAPSHOT_LOCKED",
    "EVIDENCE_COLLECTED",
    "CONTEXT_RETRIEVED",
    "DIAGNOSED",
    "INCONCLUSIVE",
    "PATCH_PROPOSED",
    "VALIDATING",
    "VERIFIED",
    "UNVERIFIED",
    "REVIEW_PENDING",
    "REVIEWED",
    "CLOSED",
)


def _state(name: str) -> sa.Enum:
    return sa.Enum(*STATES, name=name, native_enum=False, length=32, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.String(128)),
        sa.Column("service", sa.String(128)),
        sa.Column("symptom", sa.Text()),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("state", _state("ck_incidents_state"), nullable=False),
        sa.Column("cause_class", sa.String(64)),
        sa.Column("base_sha", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_state", "incidents", ["state"])
    op.create_table(
        "evidence_items",
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("service", sa.String(128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("path", sa.String(512)),
        sa.Column("line", sa.Integer()),
        sa.Column("ts", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_state", _state("ck_audit_events_from_state")),
        sa.Column("to_state", _state("ck_audit_events_to_state")),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_incident_id", "audit_events", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_incident_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("evidence_items")
    op.drop_index("ix_incidents_state", table_name="incidents")
    op.drop_table("incidents")
