"""move assessment links from classes to courses

Revision ID: 1f0aee90793e
Revises: 4f8c2314030e
Create Date: 2026-11-19 11:51:23.926814

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1f0aee90793e'
down_revision = '4f8c2314030e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('soal_ats_teori', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_ats_praktikum', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_aas_teori', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_aas_praktikum', sa.String(length=500), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT course_id, soal_ats_teori, soal_ats_praktikum, soal_aas_teori, soal_aas_praktikum "
            "FROM classes "
            "WHERE soal_ats_teori IS NOT NULL OR soal_ats_praktikum IS NOT NULL "
            "OR soal_aas_teori IS NOT NULL OR soal_aas_praktikum IS NOT NULL"
        )
    ).fetchall()
    merged = {}
    for row in rows:
        cid = row[0]
        cur = merged.setdefault(cid, [None, None, None, None])
        for idx in range(4):
            val = (row[idx + 1] or "").strip() if row[idx + 1] else ""
            if val and not cur[idx]:
                cur[idx] = val
    for cid, vals in merged.items():
        conn.execute(
            sa.text(
                "UPDATE courses SET soal_ats_teori = :v0, soal_ats_praktikum = :v1, "
                "soal_aas_teori = :v2, soal_aas_praktikum = :v3 WHERE id = :cid"
            ),
            {"v0": vals[0], "v1": vals[1], "v2": vals[2], "v3": vals[3], "cid": cid},
        )

    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.drop_column('soal_ats_praktikum')
        batch_op.drop_column('soal_aas_praktikum')
        batch_op.drop_column('soal_ats_teori')
        batch_op.drop_column('soal_aas_teori')


def downgrade():
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('soal_aas_teori', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_ats_teori', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_aas_praktikum', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('soal_ats_praktikum', sa.String(length=500), nullable=True))

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('soal_aas_praktikum')
        batch_op.drop_column('soal_aas_teori')
        batch_op.drop_column('soal_ats_praktikum')
        batch_op.drop_column('soal_ats_teori')
