from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Identity, Index, MetaData, SmallInteger, String, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("telegram_id", BigInteger, primary_key=True, autoincrement=False),
    Column("username", Text),
    Column("first_name", Text, nullable=False),
    Column("last_name", Text),
    Column("language", String(2), nullable=False),
    Column("registered_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("language IN ('ru', 'en')", name="users_language_check"),
)
Index("users_last_seen_at", users.c.last_seen_at.desc(), users.c.telegram_id.desc())

appeals = Table(
    "appeals",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("user_id", BigInteger, ForeignKey("users.telegram_id", ondelete="RESTRICT"), nullable=False),
    Column("text", Text, nullable=False),
    Column("status", Boolean, nullable=False, server_default="false"),
    Column("answer", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("answered_at", DateTime(timezone=True)),
    Column("workflow_status", String(20), nullable=False, server_default="new"),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("closed_at", DateTime(timezone=True)),
    Column("rating", SmallInteger),
    Column("rated_at", DateTime(timezone=True)),
    Column("category", String(20), nullable=False, server_default="other"),
    CheckConstraint("workflow_status IN ('new', 'in_progress', 'waiting_user', 'closed')", name="appeals_workflow_status_check"),
    CheckConstraint("category IN ('technical', 'account', 'question', 'suggestion', 'other')", name="appeals_category_check"),
    CheckConstraint("rating IN (-1, 1)", name="appeals_rating_check"),
)
Index("appeals_user_id_id", appeals.c.user_id, appeals.c.id.desc())
Index("appeals_workflow_updated", appeals.c.workflow_status, appeals.c.updated_at.desc())
Index("appeals_category_updated", appeals.c.category, appeals.c.updated_at.desc())

appeal_messages = Table(
    "appeal_messages",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("appeal_id", BigInteger, ForeignKey("appeals.id", ondelete="CASCADE"), nullable=False),
    Column("sender_id", BigInteger, nullable=False),
    Column("sender_role", String(10), nullable=False),
    Column("text", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("content_type", String(10), nullable=False, server_default="text"),
    Column("file_id", Text),
    Column("file_name", Text),
    CheckConstraint("sender_role IN ('user', 'admin')", name="appeal_messages_sender_role_check"),
    CheckConstraint("content_type IN ('text', 'photo', 'document')", name="appeal_messages_content_type_check"),
)
Index("appeal_messages_appeal_id_id", appeal_messages.c.appeal_id, appeal_messages.c.id)

bot_chats = Table(
    "bot_chats",
    metadata,
    Column("chat_id", BigInteger, primary_key=True, autoincrement=False),
    Column("chat_type", String(20), nullable=False),
    Column("title", Text),
    Column("username", Text),
    Column("bot_status", String(20), nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
Index("bot_chats_status_seen", bot_chats.c.bot_status, bot_chats.c.last_seen_at.desc())

fsm_states = Table(
    "fsm_states",
    metadata,
    Column("bot_id", BigInteger, primary_key=True),
    Column("chat_id", BigInteger, primary_key=True),
    Column("user_id", BigInteger, primary_key=True),
    Column("thread_id", BigInteger, primary_key=True, server_default="0"),
    Column("business_connection_id", Text, primary_key=True, server_default=""),
    Column("destiny", Text, primary_key=True, server_default="default"),
    Column("state", Text),
    Column("data", JSONB, nullable=False, server_default="{}"),
)

data_imports = Table(
    "data_imports",
    metadata,
    Column("name", Text, primary_key=True),
    Column("imported_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
