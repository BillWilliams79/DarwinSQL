"""Build Visualizer event times — builds.built_at, branches.branched_at,
customer_releases.released_at (req #3515, migration 20260913064647).

`test_data_types.py` pins each column's DESCRIBE contract. This file pins the
two things DESCRIBE cannot show:

1. **The three DDL surfaces agree.** The column lives in the migration (what
   darwin_dev got), `schema.sql` (the documented schema, and what darwin-mcp's
   unit-tier fake parses) and `scripts/recreate_darwin_dev.sql` (what a
   darwin_dev rebuild produces). A column missing from the rebuild script
   vanishes silently the next time darwin_dev is recreated — every test of it
   keeps passing against the old database until then.
2. **The type choice behaves as the migration argues.** DATETIME, not TIMESTAMP:
   the stored wall clock must not move with the session `time_zone`, and an
   INSERT that omits the column must leave NULL ("not recorded"), not stamp the
   insert time over the event time.
"""

import os
import re
import uuid

import pytest

DARWINSQL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = ('migrations/'
             '20260913064647_add_build_viz_event_datetimes_built_at_branched_at_released.sql')

EVENT_COLUMNS = {
    'builds': 'built_at',
    'branches': 'branched_at',
    'customer_releases': 'released_at',
}


def _read(relpath):
    with open(os.path.join(DARWINSQL_ROOT, relpath), encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(sql):
    return re.sub(r'--[^\n]*', '', sql)


def _create_table_body(sql, table):
    m = re.search(rf'CREATE TABLE (?:IF NOT EXISTS )?`?{table}`?\s*\((.*?)\n\);',
                  sql, re.S | re.I)
    assert m, f'CREATE TABLE {table} not found'
    return m.group(1)


def _column_decl(body, column):
    m = re.search(rf'^\s*{column}\s+(.+?),?\s*$', body, re.M | re.I)
    return m.group(1).strip().rstrip(',') if m else None


@pytest.mark.parametrize('relpath', ['schema.sql', 'scripts/recreate_darwin_dev.sql'])
@pytest.mark.parametrize('table, column', sorted(EVENT_COLUMNS.items()))
def test_event_column_declared_datetime_null_without_default(relpath, table, column):
    body = _create_table_body(_strip_comments(_read(relpath)), table)
    decl = _column_decl(body, column)
    assert decl is not None, f'{relpath}: {table}.{column} not declared'
    assert re.fullmatch(r'DATETIME\s+NULL', decl, re.I), (
        f'{relpath}: {table}.{column} must be `DATETIME NULL` with no DEFAULT, '
        f'got `{decl}`')


def test_migration_adds_exactly_the_three_event_columns():
    sql = _strip_comments(_read(MIGRATION))
    adds = re.findall(r'ALTER TABLE\s+(\w+)\s+ADD COLUMN\s+(\w+)\s+([^;]+);', sql, re.I)
    assert {(t, c) for t, c, _ in adds} == set(EVENT_COLUMNS.items())
    for table, column, rest in adds:
        assert re.match(r'DATETIME\s+NULL\b', rest.strip(), re.I), (table, column, rest)
        assert 'DEFAULT' not in rest.upper(), (table, column, rest)


def test_migration_is_barred_from_production():
    """The build-viz tables exist only in darwin_dev (dropped from production by
    migration 057). `test_sql_targets.py` enforces the declaration's GRAMMAR on
    every file; this pins that THIS migration declares darwin_dev alone."""
    header = _read(MIGRATION)
    targets = re.findall(r'^--\s*darwin:targets\s*=\s*(.+)$', header, re.M)
    assert [t.strip() for t in targets] == ['darwin_dev']
    assert not re.search(r'^\s*USE\s', _strip_comments(header), re.M | re.I)


# --- live behaviour against darwin_dev --------------------------------------

@pytest.fixture
def bv_chain(db_connection, test_creator_fk):
    """project -> trunk branch -> one build -> one customer release, owned by the
    session's schema-test creator, with every event column left OMITTED."""
    tag = uuid.uuid4().hex[:8]
    ids = {}
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO build_projects (title, creator_fk) VALUES (%s, %s)",
                    (f'evt-{tag}', test_creator_fk))
        ids['project'] = cur.lastrowid
        cur.execute("INSERT INTO branches (project_fk, branch_type, external_id, creator_fk) "
                    "VALUES (%s, 'main', 'main', %s)", (ids['project'], test_creator_fk))
        ids['branch'] = cur.lastrowid
        cur.execute("INSERT INTO builds (branch_fk, position, build_number, creator_fk) "
                    "VALUES (%s, 0, 1, %s)", (ids['branch'], test_creator_fk))
        ids['build'] = cur.lastrowid
        cur.execute("INSERT INTO customers (customer_name, creator_fk) VALUES (%s, %s)",
                    (f'evt-cust-{tag}', test_creator_fk))
        ids['customer'] = cur.lastrowid
        cur.execute("INSERT INTO customer_releases (customer_fk, build_fk, creator_fk) "
                    "VALUES (%s, %s, %s)", (ids['customer'], ids['build'], test_creator_fk))
        ids['release'] = cur.lastrowid
    db_connection.commit()

    yield ids

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM customer_releases WHERE id = %s", (ids['release'],))
        cur.execute("DELETE FROM builds WHERE id = %s", (ids['build'],))
        cur.execute("DELETE FROM branches WHERE id = %s", (ids['branch'],))
        cur.execute("DELETE FROM build_projects WHERE id = %s", (ids['project'],))
        cur.execute("DELETE FROM customers WHERE id = %s", (ids['customer'],))
    db_connection.commit()


_ROW_ID = {'builds': 'build', 'branches': 'branch', 'customer_releases': 'release'}


def test_omitted_event_time_is_null_not_the_insert_time(db_connection, bv_chain):
    with db_connection.cursor() as cur:
        for table, column in EVENT_COLUMNS.items():
            cur.execute(f"SELECT {column} AS v, create_ts FROM {table} WHERE id = %s",
                        (bv_chain[_ROW_ID[table]],))
            row = cur.fetchone()
            assert row['create_ts'] is not None          # the audit column did stamp
            assert row['v'] is None, f'{table}.{column} was stamped on INSERT'


def test_event_time_does_not_shift_with_session_time_zone(db_connection, bv_chain):
    """Write 14:00 under UTC, read under Pacific: a DATETIME reads back 14:00.
    A TIMESTAMP would read 07:00 — and the UI, which treats the value as UTC,
    would then show 12:00 AM instead of 7:00 AM."""
    with db_connection.cursor() as cur:
        # The connection is SESSION-scoped and shared with every other test, so
        # its zone is captured and restored rather than assumed.
        cur.execute("SELECT @@session.time_zone AS tz")
        original_tz = cur.fetchone()['tz']
        cur.execute("SET SESSION time_zone = '+00:00'")
        for table, column in EVENT_COLUMNS.items():
            cur.execute(f"UPDATE {table} SET {column} = '2026-09-14 14:00:00' WHERE id = %s",
                        (bv_chain[_ROW_ID[table]],))
        db_connection.commit()
        cur.execute("SET SESSION time_zone = '-07:00'")
        try:
            for table, column in EVENT_COLUMNS.items():
                cur.execute(
                    f"SELECT DATE_FORMAT({column}, '%%Y-%%m-%%d %%H:%%i:%%s') AS v "
                    f"FROM {table} WHERE id = %s", (bv_chain[_ROW_ID[table]],))
                assert cur.fetchone()['v'] == '2026-09-14 14:00:00', f'{table}.{column}'
        finally:
            cur.execute("SET SESSION time_zone = %s", (original_tz,))
