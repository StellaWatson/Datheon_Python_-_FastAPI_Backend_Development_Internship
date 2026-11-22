"""add book ownership

Revision ID: 47f94f826848
Revises: 
Create Date: 2026-11-10 10:49:54.860232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47f94f826848'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("books") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True)
        )

    op.execute(
        "UPDATE books SET user_id = 1"
    )

    with op.batch_alter_table("books") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False
        )
        batch_op.create_foreign_key(
            "fk_books_user_id_users",
            "users",
            ["user_id"],
            ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("books") as batch_op:
        batch_op.drop_constraint(
            "fk_books_user_id_users",
            type_="foreignkey"
        )
        batch_op.drop_column("user_id")
