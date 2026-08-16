"""Add startup journey tables

Revision ID: a1b2c3d4e5f6
Revises: 924c02a1e5cb
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '924c02a1e5cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('startup_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('founder_name', sa.String(), nullable=True),
        sa.Column('founder_email', sa.String(), nullable=True),
        sa.Column('founder_mobile', sa.String(), nullable=True),
        sa.Column('preferred_language', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('business_model', sa.String(), nullable=True),
        sa.Column('founded_year', sa.Integer(), nullable=True),
        sa.Column('stage', sa.String(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('headcount', sa.Integer(), nullable=True),
        sa.Column('is_pre_revenue', sa.Boolean(), nullable=True),
        sa.Column('monthly_revenue', sa.Float(), nullable=True),
        sa.Column('revenue_streams', sa.JSON(), nullable=True),
        sa.Column('revenue_growth_pct_input', sa.Float(), nullable=True),
        sa.Column('paying_customers', sa.Integer(), nullable=True),
        sa.Column('fixed_costs', sa.Float(), nullable=True),
        sa.Column('variable_costs', sa.Float(), nullable=True),
        sa.Column('current_cash', sa.Float(), nullable=True),
        sa.Column('monthly_burn_input', sa.Float(), nullable=True),
        sa.Column('business_loans_debt', sa.Float(), nullable=True),
        sa.Column('total_funding', sa.Float(), nullable=True),
        sa.Column('last_round', sa.String(), nullable=True),
        sa.Column('currently_fundraising', sa.Boolean(), nullable=True),
        sa.Column('fundraising_target', sa.Float(), nullable=True),
        sa.Column('planned_hires', sa.Integer(), nullable=True),
        sa.Column('cost_per_hire', sa.Float(), nullable=True),
        sa.Column('goals', sa.JSON(), nullable=True),
        sa.Column('current_decision', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id')
    )
    op.create_index(op.f('ix_startup_profiles_id'), 'startup_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_startup_profiles_profile_id'), 'startup_profiles', ['profile_id'], unique=True)

    op.create_table('startup_metric_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('snapshot_date', sa.Date(), nullable=True),
        sa.Column('cash', sa.Float(), nullable=True),
        sa.Column('gross_burn', sa.Float(), nullable=True),
        sa.Column('net_burn', sa.Float(), nullable=True),
        sa.Column('revenue', sa.Float(), nullable=True),
        sa.Column('runway_months', sa.Float(), nullable=True),
        sa.Column('financial_health_score', sa.Float(), nullable=True),
        sa.Column('raw', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id', 'snapshot_date', name='uq_startup_snapshot_profile_date')
    )
    op.create_index(op.f('ix_startup_metric_snapshots_id'), 'startup_metric_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_startup_metric_snapshots_profile_id'), 'startup_metric_snapshots', ['profile_id'], unique=False)
    op.create_index(op.f('ix_startup_metric_snapshots_snapshot_date'), 'startup_metric_snapshots', ['snapshot_date'], unique=False)

    op.create_table('startup_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('txn_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_startup_transactions_id'), 'startup_transactions', ['id'], unique=False)
    op.create_index(op.f('ix_startup_transactions_profile_id'), 'startup_transactions', ['profile_id'], unique=False)

    op.create_table('startup_decision_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('decision_type', sa.String(), nullable=True),
        sa.Column('scenario_text', sa.String(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('tag', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_startup_decision_log_id'), 'startup_decision_log', ['id'], unique=False)
    op.create_index(op.f('ix_startup_decision_log_profile_id'), 'startup_decision_log', ['profile_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_startup_decision_log_profile_id'), table_name='startup_decision_log')
    op.drop_index(op.f('ix_startup_decision_log_id'), table_name='startup_decision_log')
    op.drop_table('startup_decision_log')

    op.drop_index(op.f('ix_startup_transactions_profile_id'), table_name='startup_transactions')
    op.drop_index(op.f('ix_startup_transactions_id'), table_name='startup_transactions')
    op.drop_table('startup_transactions')

    op.drop_index(op.f('ix_startup_metric_snapshots_snapshot_date'), table_name='startup_metric_snapshots')
    op.drop_index(op.f('ix_startup_metric_snapshots_profile_id'), table_name='startup_metric_snapshots')
    op.drop_index(op.f('ix_startup_metric_snapshots_id'), table_name='startup_metric_snapshots')
    op.drop_table('startup_metric_snapshots')

    op.drop_index(op.f('ix_startup_profiles_profile_id'), table_name='startup_profiles')
    op.drop_index(op.f('ix_startup_profiles_id'), table_name='startup_profiles')
    op.drop_table('startup_profiles')
