"""Create the complete PostgreSQL schema.

Revision ID: 20260928_01
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260928_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("username", sa.Text()),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text()),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("language IN ('ru', 'en')", name="users_language_check"),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_index("users_last_seen_at", "users", [sa.text("last_seen_at DESC"), sa.text("telegram_id DESC")])

    op.create_table(
        "bot_chats",
        sa.Column("chat_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("chat_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("username", sa.Text()),
        sa.Column("bot_status", sa.String(length=20), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("chat_id"),
    )
    op.create_index("bot_chats_status_seen", "bot_chats", ["bot_status", sa.text("last_seen_at DESC")])

    op.create_table(
        "fsm_states",
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("thread_id", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("business_connection_id", sa.Text(), server_default="", nullable=False),
        sa.Column("destiny", sa.Text(), server_default="default", nullable=False),
        sa.Column("state", sa.Text()),
        sa.Column("data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("bot_id", "chat_id", "user_id", "thread_id", "business_connection_id", "destiny"),
    )

    op.create_table(
        "data_imports",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "appeals",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("workflow_status", sa.String(length=20), server_default="new", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("category", sa.String(length=20), server_default="other", nullable=False),
        sa.CheckConstraint(
            "workflow_status IN ('new', 'in_progress', 'waiting_user', 'closed')",
            name="appeals_workflow_status_check",
        ),
        sa.CheckConstraint(
            "category IN ('technical', 'account', 'question', 'suggestion', 'other')",
            name="appeals_category_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("appeals_user_id_id", "appeals", ["user_id", sa.text("id DESC")])
    op.create_index("appeals_workflow_updated", "appeals", ["workflow_status", sa.text("updated_at DESC")])
    op.create_index("appeals_category_updated", "appeals", ["category", sa.text("updated_at DESC")])

    op.create_table(
        "appeal_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("appeal_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_role", sa.String(length=10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("content_type", sa.String(length=10), server_default="text", nullable=False),
        sa.Column("file_id", sa.Text()),
        sa.Column("file_name", sa.Text()),
        sa.CheckConstraint("sender_role IN ('user', 'admin')", name="appeal_messages_sender_role_check"),
        sa.CheckConstraint(
            "content_type IN ('text', 'photo', 'document')", name="appeal_messages_content_type_check"
        ),
        sa.ForeignKeyConstraint(["appeal_id"], ["appeals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("appeal_messages_appeal_id_id", "appeal_messages", ["appeal_id", "id"])


def downgrade() -> None:
    op.drop_table("appeal_messages")
    op.drop_table("appeals")
    op.drop_table("data_imports")
    op.drop_table("fsm_states")
    op.drop_table("bot_chats")
    op.drop_table("users")
