"""Add source/updated_at to startup_transactions

Revision ID: b7c1d9e2f3a4
Revises: a1b2c3d4e5f6
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c1d9e2f3a4'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('startup_transactions', sa.Column('source', sa.String(), nullable=True, server_default='manual'))
    op.add_column('startup_transactions', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('startup_transactions', 'updated_at')
    op.drop_column('startup_transactions', 'source')