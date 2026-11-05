"""Add mobile number to users

Revision ID: 9dcbc0c149f6
Revises: 20261104_01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic revision identifiers
revision: str = "9dcbc0c149f6"
down_revision: Union[str, Sequence[str], None] = "20261104_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add mobile_number column to users table."""

    op.add_column(
        "users",
        sa.Column(
            "mobile_number",
            sa.String(length=15),
            nullable=True
        )
    )


def downgrade() -> None:
    """Remove mobile_number column from users table."""

    op.drop_column("users", "mobile_number")