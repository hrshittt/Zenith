"""Add startup_weekly_reports table

Revision ID: c8d2e4f6a7b9
Revises: b7c1d9e2f3a4
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d2e4f6a7b9'
down_revision: Union[str, Sequence[str], None] = 'b7c1d9e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('startup_weekly_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('week_start', sa.Date(), nullable=True),
        sa.Column('week_end', sa.Date(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('category_spend', sa.JSON(), nullable=True),
        sa.Column('flags', sa.JSON(), nullable=True),
        sa.Column('suggestions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id', 'week_start', name='uq_weekly_report_profile_week')
    )
    op.create_index(op.f('ix_startup_weekly_reports_id'), 'startup_weekly_reports', ['id'], unique=False)
    op.create_index(op.f('ix_startup_weekly_reports_profile_id'), 'startup_weekly_reports', ['profile_id'], unique=False)
    op.create_index(op.f('ix_startup_weekly_reports_week_start'), 'startup_weekly_reports', ['week_start'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_startup_weekly_reports_week_start'), table_name='startup_weekly_reports')
    op.drop_index(op.f('ix_startup_weekly_reports_profile_id'), table_name='startup_weekly_reports')
    op.drop_index(op.f('ix_startup_weekly_reports_id'), table_name='startup_weekly_reports')
    op.drop_table('startup_weekly_reports')