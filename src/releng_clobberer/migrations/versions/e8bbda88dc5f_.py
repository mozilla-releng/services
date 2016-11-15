"""empty message

Revision ID: e8bbda88dc5f
Revises: None
Create Date: 2016-11-03 17:03:27.231041

"""

# revision identifiers, used by Alembic.
revision = 'e8bbda88dc5f'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('releng_clobberer_builds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('branch', sa.String(length=50), nullable=True),
    sa.Column('builddir', sa.String(length=100), nullable=True),
    sa.Column('buildername', sa.String(length=100), nullable=True),
    sa.Column('last_build_time', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clobberer_builds_branch'), 'releng_clobberer_builds', ['branch'], unique=False)
    op.create_index(op.f('ix_clobberer_builds_builddir'), 'releng_clobberer_builds', ['builddir'], unique=False)
    op.create_table('releng_clobberer_times',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('branch', sa.String(length=50), nullable=True),
    sa.Column('slave', sa.String(length=30), nullable=True),
    sa.Column('builddir', sa.String(length=100), nullable=True),
    sa.Column('lastclobber', sa.Integer(), nullable=False),
    sa.Column('who', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clobberer_times_branch'), 'releng_clobberer_times', ['branch'], unique=False)
    op.create_index(op.f('ix_clobberer_times_builddir'), 'releng_clobberer_times', ['builddir'], unique=False)
    op.create_index(op.f('ix_clobberer_times_lastclobber'), 'releng_clobberer_times', ['lastclobber'], unique=False)
    op.create_index(op.f('ix_clobberer_times_slave'), 'releng_clobberer_times', ['slave'], unique=False)
    op.create_index('ix_get_clobberer_times', 'releng_clobberer_times', ['slave', 'builddir', 'branch'], unique=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_get_clobberer_times', table_name='releng_clobberer_times')
    op.drop_index(op.f('ix_clobberer_times_slave'), table_name='releng_clobberer_times')
    op.drop_index(op.f('ix_clobberer_times_lastclobber'), table_name='releng_clobberer_times')
    op.drop_index(op.f('ix_clobberer_times_builddir'), table_name='releng_clobberer_times')
    op.drop_index(op.f('ix_clobberer_times_branch'), table_name='releng_clobberer_times')
    op.drop_table('clobberer_times')
    op.drop_index(op.f('ix_clobberer_builds_builddir'), table_name='releng_clobberer_builds')
    op.drop_index(op.f('ix_clobberer_builds_branch'), table_name='releng_clobberer_builds')
    op.drop_table('releng_clobberer_builds')
    ### end Alembic commands ###
