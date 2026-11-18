"""convert pi_code to PI-xx.y format

Revision ID: 010e3b33099a
Revises: 2a2821c3037e
Create Date: 2026-11-18 13:30:09.000000

"""
import json
import re

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010e3b33099a'
down_revision = '2a2821c3037e'
branch_labels = None
depends_on = None


def _to_pi_dash(code):
    m = re.match(r'^(\d+)([a-z])$', str(code or '').strip(), re.I)
    if not m:
        return code
    so_num = int(m.group(1))
    pi_idx = ord(m.group(2).lower()) - ord('a') + 1
    return f'PI-{so_num:02d}.{pi_idx}'


def _to_legacy(code):
    m = re.match(r'^PI-(\d+)\.(\d+)$', str(code or '').strip(), re.I)
    if not m:
        return code
    so_num = int(m.group(1))
    pi_idx = int(m.group(2))
    if 1 <= pi_idx <= 26:
        return f'{so_num}{chr(ord("a") + pi_idx - 1)}'
    return code


def _convert_all(converter):
    conn = op.get_bind()

    # 1. performance_indicators
    pis = conn.execute(sa.text('SELECT id, pi_code FROM performance_indicators')).fetchall()
    for row_id, code in pis:
        new_code = converter(code)
        if new_code != code:
            conn.execute(
                sa.text('UPDATE performance_indicators SET pi_code = :new WHERE id = :id'),
                {'new': new_code, 'id': row_id},
            )

    # 2. components.cpl_pis
    comps = conn.execute(sa.text('SELECT id, cpl_pis FROM components')).fetchall()
    for row_id, raw in comps:
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(items, list):
            continue
        changed = False
        for item in items:
            if isinstance(item, dict) and item.get('pi'):
                new_pi = converter(item['pi'])
                if new_pi != item['pi']:
                    item['pi'] = new_pi
                    changed = True
        if changed:
            conn.execute(
                sa.text('UPDATE components SET cpl_pis = :raw WHERE id = :id'),
                {'raw': json.dumps(items, ensure_ascii=False), 'id': row_id},
            )

    # 3. courses.raw_json
    courses = conn.execute(sa.text('SELECT id, raw_json FROM courses')).fetchall()
    for row_id, raw in courses:
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        changed = False
        for cat in data.get('categories') or []:
            for comp in cat.get('components') or []:
                for item in comp.get('cpl_pis') or []:
                    if isinstance(item, dict) and item.get('pi'):
                        new_pi = converter(item['pi'])
                        if new_pi != item['pi']:
                            item['pi'] = new_pi
                            changed = True
        if changed:
            conn.execute(
                sa.text('UPDATE courses SET raw_json = :raw WHERE id = :id'),
                {'raw': json.dumps(data, ensure_ascii=False), 'id': row_id},
            )


def upgrade():
    _convert_all(_to_pi_dash)


def downgrade():
    _convert_all(_to_legacy)
