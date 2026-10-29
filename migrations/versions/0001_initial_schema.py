"""Create the existing application schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lead_score", sa.Integer(), nullable=False),
        sa.Column("lead_temperature", sa.String(length=20), nullable=False),
        sa.Column("interest", sa.String(length=100), nullable=True),
        sa.Column("budget", sa.Integer(), nullable=True),
        sa.Column("timeline", sa.String(length=100), nullable=True),
        sa.Column("requirement", sa.String(length=150), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=False),
        sa.Column("ai_temperature", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_id", "leads", ["id"], unique=False)
    op.create_index("ix_leads_email", "leads", ["email"], unique=True)

    op.create_table(
        "lead_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_activities_id", "lead_activities", ["id"])
    op.create_index(
        "ix_lead_activities_lead_id",
        "lead_activities",
        ["lead_id"],
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_id", "conversations", ["id"])
    op.create_index("ix_conversations_lead_id", "conversations", ["lead_id"])

    op.create_table(
        "nurture_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=True),
        sa.Column("topic", sa.String(length=100), nullable=True),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_nurture_messages_id", "nurture_messages", ["id"])
    op.create_index("ix_nurture_messages_lead_id", "nurture_messages", ["lead_id"])

    op.create_table(
        "lead_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_alerts_id", "lead_alerts", ["id"])
    op.create_index("ix_lead_alerts_lead_id", "lead_alerts", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_alerts_lead_id", table_name="lead_alerts")
    op.drop_index("ix_lead_alerts_id", table_name="lead_alerts")
    op.drop_table("lead_alerts")
    op.drop_index("ix_nurture_messages_lead_id", table_name="nurture_messages")
    op.drop_index("ix_nurture_messages_id", table_name="nurture_messages")
    op.drop_table("nurture_messages")
    op.drop_index("ix_conversations_lead_id", table_name="conversations")
    op.drop_index("ix_conversations_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_lead_activities_lead_id", table_name="lead_activities")
    op.drop_index("ix_lead_activities_id", table_name="lead_activities")
    op.drop_table("lead_activities")
    op.drop_index("ix_leads_email", table_name="leads")
    op.drop_index("ix_leads_id", table_name="leads")
    op.drop_table("leads")
