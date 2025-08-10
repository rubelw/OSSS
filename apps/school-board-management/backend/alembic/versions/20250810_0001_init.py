from alembic import op
import sqlalchemy as sa

revision = '20250810_0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    role_enum = sa.Enum('ADMIN','CLERK','MEMBER','PUBLIC', name='role')
    meeting_status = sa.Enum('DRAFT','PUBLISHED','ARCHIVED', name='meetingstatus')
    motion_status = sa.Enum('PROPOSED','PASSED','FAILED','TABLED', name='motionstatus')
    vote_choice = sa.Enum('AYE','NAY','ABSTAIN','ABSENT', name='votechoice')
    policy_status = sa.Enum('DRAFT','ADOPTED','RETIRED', name='policystatus')

    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', role_enum, nullable=False, server_default='PUBLIC'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('email')
    )

    op.create_table('meetings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('location', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('status', meeting_status, nullable=False, server_default='DRAFT'),
        sa.Column('livestream_url', sa.String(length=1024)),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
    )
    op.create_index('ix_meetings_start_at', 'meetings', ['start_at'])

    op.create_table('agenda_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('meeting_id', sa.Integer(), sa.ForeignKey('meetings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('agenda_items.id')),
        sa.Column('order_no', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False, server_default=''),
        sa.Column('consent', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('executive_session', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index('ix_agenda_items_meeting', 'agenda_items', ['meeting_id'])

    op.create_table('motions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('meeting_id', sa.Integer(), sa.ForeignKey('meetings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agenda_item_id', sa.Integer(), sa.ForeignKey('agenda_items.id')),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('mover_user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('seconder_user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('status', motion_status, nullable=False, server_default='PROPOSED'),
    )
    op.create_index('ix_motions_meeting', 'motions', ['meeting_id'])

    op.create_table('votes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('motion_id', sa.Integer(), sa.ForeignKey('motions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('voter_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('choice', vote_choice, nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_votes_motion', 'votes', ['motion_id'])
    op.create_index('ix_votes_voter', 'votes', ['voter_user_id'])

    op.create_table('policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', policy_status, nullable=False, server_default='DRAFT'),
        sa.Column('category', sa.String(length=100)),
        sa.Column('current_version_id', sa.Integer(), unique=True),
        sa.UniqueConstraint('code', name='uq_policy_code')
    )

    # Optional but useful for lookups:
    op.create_index('ix_policies_current_version_id', 'policies', ['current_version_id'])

    op.create_table('policy_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('redline_from_id', sa.Integer(), sa.ForeignKey('policy_versions.id')),
        sa.Column('adopted_on', sa.Date()),
        sa.Column('effective_on', sa.Date()),
    )
    op.create_index('ix_policy_versions_policy', 'policy_versions', ['policy_id'])

    # 🔑 Add FK now that both tables exist (avoid cyclic creation issues)
    op.create_foreign_key(
        'fk_policies_current_version',
        'policies', 'policy_versions',
        ['current_version_id'], ['id'],
        ondelete='SET NULL'  # when a version is deleted, clear the pointer
    )

    op.create_table('attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('s3_key', sa.String(length=1024), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('mime', sa.String(length=100), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('checksum', sa.String(length=128), nullable=False),
        sa.Column('public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

def downgrade():
    op.drop_table('attachments')

    # drop FK + index before dropping the tables they reference
    op.drop_constraint('fk_policies_current_version', 'policies', type_='foreignkey')
    op.drop_index('ix_policies_current_version_id', table_name='policies')

    op.drop_index('ix_policy_versions_policy', table_name='policy_versions')
    op.drop_table('policy_versions')
    op.drop_table('policies')
    op.drop_index('ix_votes_voter', table_name='votes')
    op.drop_index('ix_votes_motion', table_name='votes')
    op.drop_table('votes')
    op.drop_index('ix_motions_meeting', table_name='motions')
    op.drop_table('motions')
    op.drop_index('ix_agenda_items_meeting', table_name='agenda_items')
    op.drop_table('agenda_items')
    op.drop_index('ix_meetings_start_at', table_name='meetings')
    op.drop_table('meetings')
    op.drop_table('users')
    for name in ['policystatus','votechoice','motionstatus','meetingstatus','role']:
        op.execute(f'DROP TYPE IF EXISTS {name} CASCADE')
