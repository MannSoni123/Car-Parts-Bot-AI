"""add intent_type and reference file support

Revision ID: 2c6ef0f6405d
Revises: bf4fc1360cee
Create Date: 2026-01-08 15:03:26.608284

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '2c6ef0f6405d'
down_revision = 'bf4fc1360cee'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "intent_prompts",
        sa.Column("reference_file", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "intent_prompts",
        sa.Column("reference_text", sa.Text(), nullable=True),
    )

def downgrade():
    op.drop_column("intent_prompts", "reference_text")
    op.drop_column("intent_prompts", "reference_file")
