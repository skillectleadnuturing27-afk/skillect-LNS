"""Add nurture content identities and image metadata.

Revision ID: 0002_nurture_content_identity
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_nurture_content_identity"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _has_unique_columns(table_name, columns):
    inspector = sa.inspect(op.get_bind())
    for index in inspector.get_indexes(table_name):
        if index.get("unique") and index.get("column_names") == columns:
            return True
    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("column_names") == columns:
            return True
    return False


def _ensure_index(table_name, index_name, columns):
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    }
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=False)


def _raise_on_duplicates(table_name, columns):
    # Fail before creating unique indexes rather than discarding legacy rows.
    duplicate = op.get_bind().execute(
        sa.text(
            f"""
            SELECT 1
            FROM {table_name}
            GROUP BY {columns}
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            f"Cannot create unique constraints: {table_name} contains "
            f"duplicate values for ({columns}). Resolve duplicates "
            "explicitly, then rerun the migration; no rows were deleted."
        )


def upgrade() -> None:
    tables = _tables()
    if "nurture_content_identities" in tables:
        _raise_on_duplicates(
            "nurture_content_identities",
            "lead_id, identity",
        )
    if "nurture_image_metadata" in tables:
        _raise_on_duplicates("nurture_image_metadata", "nurture_id")

    if "nurture_content_identities" not in tables:
        op.create_table(
            "nurture_content_identities",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("nurture_id", sa.Integer(), nullable=False),
            sa.Column("identity", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["nurture_id"],
                ["nurture_messages.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_nurture_content_identities_id", ["id"]),
        ("ix_nurture_content_identities_lead_id", ["lead_id"]),
        ("ix_nurture_content_identities_nurture_id", ["nurture_id"]),
    ):
        _ensure_index("nurture_content_identities", index_name, columns)

    if not _has_unique_columns(
        "nurture_content_identities",
        ["lead_id", "identity"],
    ):
        op.create_index(
            "uq_nurture_content_identity_lead_identity",
            "nurture_content_identities",
            ["lead_id", "identity"],
            unique=True,
        )

    if "nurture_image_metadata" not in _tables():
        op.create_table(
            "nurture_image_metadata",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("nurture_id", sa.Integer(), nullable=False),
            sa.Column("image_id", sa.String(length=255), nullable=True),
            sa.Column("canonical_url", sa.Text(), nullable=True),
            sa.Column("topic", sa.String(length=100), nullable=False),
            sa.Column("source", sa.Text(), nullable=False),
            sa.Column("approved", sa.Boolean(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(
                ["nurture_id"],
                ["nurture_messages.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    _ensure_index(
        "nurture_image_metadata",
        "ix_nurture_image_metadata_id",
        ["id"],
    )
    if not _has_unique_columns(
        "nurture_image_metadata",
        ["nurture_id"],
    ):
        op.create_index(
            "uq_nurture_image_metadata_nurture_id",
            "nurture_image_metadata",
            ["nurture_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(
        "uq_nurture_image_metadata_nurture_id",
        table_name="nurture_image_metadata",
        if_exists=True,
    )
    op.drop_index(
        "ix_nurture_image_metadata_id",
        table_name="nurture_image_metadata",
        if_exists=True,
    )
    op.drop_table("nurture_image_metadata")
    op.drop_index(
        "uq_nurture_content_identity_lead_identity",
        table_name="nurture_content_identities",
        if_exists=True,
    )
    op.drop_index(
        "ix_nurture_content_identities_nurture_id",
        table_name="nurture_content_identities",
        if_exists=True,
    )
    op.drop_index(
        "ix_nurture_content_identities_lead_id",
        table_name="nurture_content_identities",
        if_exists=True,
    )
    op.drop_index(
        "ix_nurture_content_identities_id",
        table_name="nurture_content_identities",
        if_exists=True,
    )
    op.drop_table("nurture_content_identities")
