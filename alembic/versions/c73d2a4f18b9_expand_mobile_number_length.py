"""Expand mobile number length to 20 characters.

Revision ID: c73d2a4f18b9
Revises: 9dcbc0c149f6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c73d2a4f18b9"
down_revision: Union[str, Sequence[str], None] = "9dcbc0c149f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "mobile_number",
            existing_type=sa.String(length=15),
            type_=sa.String(length=20),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "mobile_number",
            existing_type=sa.String(length=20),
            type_=sa.String(length=15),
            existing_nullable=True,
        )
