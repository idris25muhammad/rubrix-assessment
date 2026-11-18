"""roles admin kps, class lecturer_id, assessment links, drop shared_with

Revision ID: 2a2821c3037e
Revises: d675cc5c1d87
Create Date: 2026-11-18 12:51:46.501004

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2a2821c3037e'
down_revision = 'd675cc5c1d87'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET role = 'kps' WHERE role = 'tim_kurikulum'")

    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lecturer_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('academic_year', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('soal_ats_teori', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_ats_praktikum', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_aas_teori', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_aas_praktikum', sa.String(length=500), nullable=True))
        batch_op.create_foreign_key('fk_classes_lecturer_id', 'users', ['lecturer_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('shared_with')


def downgrade():
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shared_with', sa.Text(), nullable=True))

    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_classes_lecturer_id', type_='foreignkey')
        batch_op.drop_column('soal_aas_praktikum')
        batch_op.drop_column('soal_aas_teori')
        batch_op.drop_column('soal_ats_praktikum')
        batch_op.drop_column('soal_ats_teori')
        batch_op.drop_column('academic_year')
        batch_op.drop_column('lecturer_id')

    op.execute("UPDATE users SET role = 'tim_kurikulum' WHERE role = 'kps'")
