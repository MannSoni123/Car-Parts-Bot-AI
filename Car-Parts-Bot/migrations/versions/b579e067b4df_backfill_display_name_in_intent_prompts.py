from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b579e067b4df'
down_revision = '5a7b71a11b59'
branch_labels = None
depends_on = None


def upgrade():
    # 1️⃣ Backfill display_name where NULL
    op.execute("""
        UPDATE intent_prompts
        SET display_name = intent_key
        WHERE display_name IS NULL
    """)

    # 2️⃣ Enforce NOT NULL (MySQL requires existing_type)
    op.alter_column(
        'intent_prompts',
        'display_name',
        existing_type=sa.String(length=255),
        nullable=False
    )


def downgrade():
    # Optional: allow NULL again
    op.alter_column(
        'intent_prompts',
        'display_name',
        existing_type=sa.String(length=255),
        nullable=True
    )
