"""
Add user deactivation fields
===========================

This Alembic migration introduces three new columns to the ``users`` table
to support account deactivation. The boolean ``is_deactivated`` column
represents whether a previously approved account has been suspended. The
``deactivated_at`` timestamp records when the action occurred, and
``deactivated_by`` stores the identifier of the administrator that
initiated the deactivation.

Revision ID: 002_user_deactivation
Revises: 001_initial
Create Date: 2025-01-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_user_deactivation'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_deactivated', sa.Boolean(), server_default=sa.false()))
    op.add_column('users', sa.Column('deactivated_at', sa.TIMESTAMP()))
    op.add_column('users', sa.Column('deactivated_by', sa.Integer()))


def downgrade() -> None:
    op.drop_column('users', 'deactivated_by')
    op.drop_column('users', 'deactivated_at')
    op.drop_column('users', 'is_deactivated')