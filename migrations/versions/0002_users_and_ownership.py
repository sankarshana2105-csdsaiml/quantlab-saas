"""Add users and resource ownership."""
from datetime import datetime, timezone
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LEGACY_USER_ID = UUID("00000000-0000-0000-0000-000000000000")
LEGACY_STORAGE_ID = "00000000000000000000000000000000"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    now = datetime.now(timezone.utc)
    users = sa.table(
        "users", sa.column("id", sa.Uuid()), sa.column("email", sa.String()),
        sa.column("password_hash", sa.String()), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(users, [{
        "id": LEGACY_USER_ID, "email": "legacy-storage@quantlab.invalid",
        "password_hash": "!", "created_at": now, "updated_at": now,
    }])
    for table in ("datasets", "backtests"):
        op.add_column(table, sa.Column("owner_id", sa.Uuid(), nullable=False, server_default=LEGACY_STORAGE_ID))
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_owner_id_users", "users", ["owner_id"], ["id"])
            batch.alter_column("owner_id", server_default=None)
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])


def downgrade() -> None:
    for table in ("backtests", "datasets"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_owner_id")
            batch.drop_constraint(f"fk_{table}_owner_id_users", type_="foreignkey")
            batch.drop_column("owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
