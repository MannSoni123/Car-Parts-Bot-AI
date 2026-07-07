"""add parts_alias_text

Revision ID: fa29aa32d2a7
Revises: 2c6ef0f6405d
Create Date: 2026-01-27 17:18:23.379928

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'fa29aa32d2a7'
down_revision = '2c6ef0f6405d'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        'intent_prompts',
        sa.Column('parts_alias_text', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column('intent_prompts', 'parts_alias_text')
