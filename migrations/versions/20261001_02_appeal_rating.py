"""Store user feedback for closed appeals.

Revision ID: 20261001_02
Revises: 20260928_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20261001_02"
down_revision = "20260928_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appeals", sa.Column("rating", sa.SmallInteger(), nullable=True))
    op.add_column("appeals", sa.Column("rated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("appeals_rating_check", "appeals", "rating IN (-1, 1)")


def downgrade() -> None:
    op.drop_constraint("appeals_rating_check", "appeals", type_="check")
    op.drop_column("appeals", "rated_at")
    op.drop_column("appeals", "rating")
