"""create states table

Revision ID: 0001_create_states
Revises: 
Create Date: 2025-08-21 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_create_states'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'states',
        sa.Column('code', sa.String(length=2), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
    )
    # Optional seed data
    op.bulk_insert(
        sa.table('states',
                 sa.column('code', sa.String),
                 sa.column('name', sa.String)),
        [
            {'code': 'AL', 'name': 'Alabama'},
            {'code': 'AK', 'name': 'Alaska'},
            {'code': 'AZ', 'name': 'Arizona'},
            {'code': 'AR', 'name': 'Arkansas'},
            {'code': 'CA', 'name': 'California'},
        ]
    )

def downgrade() -> None:
    op.drop_table('states')
