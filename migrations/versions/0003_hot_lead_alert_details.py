"""Store qualification details and actionable HOT alert states.

Revision ID: 0003_hot_lead_alert_details
Revises: 0002_nurture_content_identity
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_hot_lead_alert_details"
down_revision = "0002_nurture_content_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lead_alerts",
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "lead_alerts",
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "lead_alerts",
        sa.Column(
            "qualification_summary",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )

    op.execute(
        sa.text(
            "UPDATE lead_alerts SET reason = message WHERE reason IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE lead_alerts SET status = 'active' "
            "WHERE status = 'pending'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE lead_alerts SET status = 'resolved' "
            "WHERE status = 'handled'"
        )
    )
    with op.batch_alter_table("lead_alerts") as batch_op:
        batch_op.alter_column(
            "reason",
            existing_type=sa.Text(),
            nullable=False,
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE lead_alerts SET status = 'pending' "
            "WHERE status = 'active'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE lead_alerts SET status = 'handled' "
            "WHERE status = 'resolved'"
        )
    )
    op.drop_column("lead_alerts", "qualification_summary")
    op.drop_column("lead_alerts", "score")
    op.drop_column("lead_alerts", "reason")
