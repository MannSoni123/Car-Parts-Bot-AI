from alembic import op
import sqlalchemy as sa

revision = "bf4fc1360cee"
down_revision = "b579e067b4df"

branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "intent_prompts",
        sa.Column(
            "intent_type",
            sa.String(length=20),
            nullable=False,
            server_default="text"
        )
    )


def downgrade():
    op.drop_column("intent_prompts", "intent_type")
