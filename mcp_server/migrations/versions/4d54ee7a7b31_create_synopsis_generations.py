"""create synopsis generations

Revision ID: 4d54ee7a7b31
Revises:
Create Date: 2026-07-21 12:49:19.773039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d54ee7a7b31'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "synopsis_generations",

        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "idea",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "genre",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "style",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "language",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "requested_length",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "selected_writer",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "draft",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "final_text",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "critique_passed",
            sa.Boolean(),
            nullable=True,
        ),

        sa.Column(
            "critique_score",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "revision_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),

        sa.PrimaryKeyConstraint(
            "id",
        ),
    )


def downgrade() -> None:
    op.drop_table("synopsis_generations")
