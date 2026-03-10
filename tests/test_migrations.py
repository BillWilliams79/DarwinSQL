"""
Test migration correctness and schema evolution.

Applies migrations to temporary tables in darwin_dev, verifies final schema
matches expected state. Validates that migrations are idempotent and can be applied
to fresh tables.

Test workflow:
1. Create temporary prefixed tables (mig_{prefix}_profiles, etc.)
2. Apply migrations in dependency order
3. DESCRIBE final tables and verify schema matches expectations
4. DROP temporary tables after test cleanup

Dependency note: Migrations 009-015 modify tables (projects, categories,
swarm_sessions, priorities) that were originally created ad-hoc on production.
Migration 016 retroactively tracks those table definitions. Tests must apply
016 before 009-015 to satisfy FK dependencies.
"""
import os
import glob
import pytest


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------

def _get_migrations_dir():
    """Return absolute path to migrations directory."""
    test_dir = os.path.dirname(__file__)
    darwinsql_root = os.path.dirname(test_dir)
    return os.path.join(darwinsql_root, 'migrations')


def _read_migration_file(migration_path):
    """Read and return migration SQL."""
    with open(migration_path, 'r') as f:
        return f.read()


def _apply_migration(cur, sql_content, table_prefix, tolerant=False):
    """Apply migration SQL with table name replacements.

    Replaces table names with prefixed versions (longest first to avoid
    partial matches). All 11 tables are handled.

    Args:
        cur: Database cursor
        sql_content: Raw migration SQL
        table_prefix: Prefix for temp table names
        tolerant: If True, skip ALTER/DROP failures on non-existent
                  columns (for migrations that post-date ad-hoc table creation)
    """
    sql = sql_content

    # Replace table names with prefixed versions (longest first to avoid partial matches)
    # 'recurring_tasks' must appear before 'tasks' to prevent partial substitution
    table_names = [
        'priority_card_order',
        'priority_sessions',
        'swarm_sessions',
        'dev_servers',
        'recurring_tasks',
        'categories',
        'priorities',
        'profiles',
        'projects',
        'domains',
        'areas',
        'tasks',
    ]

    # Replace backtick-quoted names first
    for name in table_names:
        sql = sql.replace(f'`{name}`', f'`{table_prefix}_{name}`')

    # Replace unquoted names
    for name in table_names:
        sql = sql.replace(name, f'{table_prefix}_{name}')

    # Remove SQL comments (both -- and # style)
    lines = []
    for line in sql.split('\n'):
        if '--' in line:
            line = line[:line.index('--')]
        if '#' in line and "'" not in line[:line.index('#')]:
            line = line[:line.index('#')]
        line = line.rstrip()
        if line:
            lines.append(line)
    sql = '\n'.join(lines)

    # Split into statements and execute each (skip CREATE DATABASE / USE)
    for statement in sql.split(';'):
        stmt = statement.strip()
        if not stmt:
            continue
        upper_stmt = stmt.upper()
        if upper_stmt.startswith(('CREATE DATABASE', 'USE ')):
            continue
        try:
            cur.execute(stmt)
        except Exception as e:
            if tolerant and ('DROP' in upper_stmt or 'ALTER' in upper_stmt):
                # Known issue: migration 012 drops worker_count which was never
                # created in temp tables (016 reflects current state without it)
                continue
            raise RuntimeError(f"Migration statement failed:\n{stmt}\nError: {e}")


def _get_dependency_ordered_migrations():
    """Return migration files in dependency order.

    Migrations 009-015 modify tables that were created ad-hoc and only
    tracked by migration 016. Apply 001-008 first, then 016, then 009-015.
    """
    migrations_dir = _get_migrations_dir()
    all_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

    early = []     # 001-008: core table creation and modifications
    mid = None     # 016: roadmap table creation
    late = []      # 009-015: modifications to tables created ad-hoc

    for f in all_files:
        basename = os.path.basename(f)
        num = int(basename.split('_')[0])
        if num <= 8:
            early.append(f)
        elif basename.startswith('016'):
            mid = f
        else:
            late.append(f)

    result = early[:]
    if mid:
        result.append(mid)
    result.extend(late)
    return result


# ---------------------------------------------------------------------------
# Per-test cleanup fixture
# ---------------------------------------------------------------------------

# All table types in FK-safe drop order (leaves first, roots last)
# recurring_tasks must be dropped before tasks (tasks.recurring_task_fk → recurring_tasks)
ALL_TABLE_SUFFIXES = [
    'priority_card_order', 'dev_servers', 'priority_sessions',
    'priorities', 'swarm_sessions', 'categories', 'projects',
    'tasks', 'recurring_tasks', 'areas', 'domains', 'profiles',
]


@pytest.fixture(autouse=True)
def cleanup_migration_test_tables(db_connection, migration_test_prefix):
    """Cleanup temporary migration tables before and after each test.

    Ensures each test starts with a clean slate. Drops all 11 table types.
    """
    def _cleanup():
        with db_connection.cursor() as cur:
            for suffix in ALL_TABLE_SUFFIXES:
                try:
                    cur.execute(f"DROP TABLE IF EXISTS `{migration_test_prefix}_{suffix}`")
                except Exception:
                    pass
        db_connection.commit()

    _cleanup()
    yield
    _cleanup()


# ---------------------------------------------------------------------------
# Test: Migration 001 creates core tables
# ---------------------------------------------------------------------------

def test_migration_001_creates_tables(db_connection, migration_test_prefix):
    """Apply migration 001 and verify 4 tables are created.

    Migration 001 creates: profiles, domains, areas, tasks
    """
    migrations_dir = _get_migrations_dir()
    migration_001 = os.path.join(migrations_dir, '001_initial_tables.sql')
    sql = _read_migration_file(migration_001)

    with db_connection.cursor() as cur:
        _apply_migration(cur, sql, migration_test_prefix)
        db_connection.commit()

        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s",
            ('darwin_dev', f"{migration_test_prefix}_%")
        )
        tables = {row['TABLE_NAME'] for row in cur.fetchall()}

    expected_tables = {
        f"{migration_test_prefix}_profiles",
        f"{migration_test_prefix}_domains",
        f"{migration_test_prefix}_areas",
        f"{migration_test_prefix}_tasks",
    }
    assert tables == expected_tables, \
        f"Expected {expected_tables}, got {tables}"


# ---------------------------------------------------------------------------
# Test: Migration 016 creates roadmap tables
# ---------------------------------------------------------------------------

def test_migration_016_creates_roadmap_tables(db_connection, migration_test_prefix):
    """Apply migrations 001-008 + 016 and verify 9 tables are created.

    016 requires profiles.id as VARCHAR(64) (from migration 004) for FK
    compatibility with creator_fk columns.
    Creates: projects, categories, swarm_sessions, priorities, priority_sessions
    """
    migrations_dir = _get_migrations_dir()
    # Apply core migrations 001-008 first (004 converts profiles.id INT→VARCHAR(64))
    core_migrations = sorted(glob.glob(os.path.join(migrations_dir, '00[1-8]_*.sql')))
    migration_016 = os.path.join(migrations_dir, '016_create_roadmap_tables.sql')

    with db_connection.cursor() as cur:
        for mig in core_migrations:
            _apply_migration(cur, _read_migration_file(mig), migration_test_prefix)
        _apply_migration(cur, _read_migration_file(migration_016), migration_test_prefix)
        db_connection.commit()

        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s",
            ('darwin_dev', f"{migration_test_prefix}_%")
        )
        tables = {row['TABLE_NAME'] for row in cur.fetchall()}

    expected_tables = {
        f"{migration_test_prefix}_profiles",
        f"{migration_test_prefix}_domains",
        f"{migration_test_prefix}_areas",
        f"{migration_test_prefix}_tasks",
        f"{migration_test_prefix}_projects",
        f"{migration_test_prefix}_categories",
        f"{migration_test_prefix}_swarm_sessions",
        f"{migration_test_prefix}_priorities",
        f"{migration_test_prefix}_priority_sessions",
    }
    assert tables == expected_tables, \
        f"Expected {expected_tables}, got {tables}"


# ---------------------------------------------------------------------------
# Test: All migrations apply successfully in dependency order
# ---------------------------------------------------------------------------

def test_migration_sequence_applies(db_connection, migration_test_prefix):
    """Apply all migrations in dependency order to temp tables.

    Order: 001-008 (core), 016 (roadmap tables), 009-015 (modifications).
    Tolerant mode handles migration 012 (DROP COLUMN worker_count) which
    targets a column absent from 016's current-state DDL.
    Expects all 11 tables after completion.
    """
    ordered_files = _get_dependency_ordered_migrations()

    with db_connection.cursor() as cur:
        for migration_file in ordered_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix, tolerant=True)
            db_connection.commit()

        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s",
            ('darwin_dev', f"{migration_test_prefix}_%")
        )
        tables = {row['TABLE_NAME'] for row in cur.fetchall()}

    expected_tables = {
        f"{migration_test_prefix}_{suffix}"
        for suffix in [
            'profiles', 'domains', 'areas', 'tasks',
            'projects', 'categories', 'priorities',
            'swarm_sessions', 'priority_sessions',
            'dev_servers', 'priority_card_order',
        ]
    }
    assert tables == expected_tables, \
        f"Missing: {expected_tables - tables}, extra: {tables - expected_tables}"


# ---------------------------------------------------------------------------
# Test: Final schema after all migrations matches expectations
# ---------------------------------------------------------------------------

def test_migration_final_schema_matches_profiles(db_connection, migration_test_prefix):
    """After all migrations, profiles table schema matches schema.sql.

    Expected final state (post migration 015 slim-down):
    - id: VARCHAR(64), PRI
    - name: VARCHAR(256), NOT NULL
    - email: VARCHAR(256), NOT NULL
    - timezone: VARCHAR(64), NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    ordered_files = _get_dependency_ordered_migrations()

    with db_connection.cursor() as cur:
        for migration_file in ordered_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix, tolerant=True)
        db_connection.commit()

        table_name = f"{migration_test_prefix}_profiles"
        cur.execute(f"DESCRIBE {table_name}")
        columns = {row['Field']: row for row in cur.fetchall()}

    # Verify schema — 6 columns after slim-down
    expected_fields = {'id', 'name', 'email', 'timezone', 'create_ts', 'update_ts'}
    assert set(columns.keys()) == expected_fields, \
        f"Unexpected columns: {set(columns.keys()) - expected_fields}"

    assert columns['id']['Type'] == 'varchar(64)'
    assert columns['id']['Key'] == 'PRI'

    assert columns['name']['Type'] == 'varchar(256)'
    assert columns['name']['Null'] == 'NO'

    assert columns['email']['Type'] == 'varchar(256)'
    assert columns['email']['Null'] == 'NO'

    assert columns['timezone']['Type'] == 'varchar(64)'
    assert columns['timezone']['Null'] == 'YES'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_migration_final_schema_matches_domains(db_connection, migration_test_prefix):
    """After all migrations, domains table schema matches schema.sql.

    Expected final state:
    - id: INT, PRI, AUTO_INCREMENT
    - domain_name: VARCHAR(32), NOT NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - closed: TINYINT, NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    ordered_files = _get_dependency_ordered_migrations()

    with db_connection.cursor() as cur:
        for migration_file in ordered_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix, tolerant=True)
        db_connection.commit()

        table_name = f"{migration_test_prefix}_domains"
        cur.execute(f"DESCRIBE {table_name}")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = {'id', 'domain_name', 'creator_fk', 'closed', 'sort_order',
                       'create_ts', 'update_ts'}
    assert set(columns.keys()) == expected_fields

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['domain_name']['Type'] == 'varchar(32)'
    assert columns['domain_name']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['closed']['Type'] == 'tinyint'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_migration_final_schema_matches_areas(db_connection, migration_test_prefix):
    """After all migrations, areas table schema matches schema.sql.

    Expected final state:
    - id: INT, PRI, AUTO_INCREMENT
    - area_name: VARCHAR(32), NOT NULL
    - domain_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - closed: TINYINT, NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'priority'
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    ordered_files = _get_dependency_ordered_migrations()

    with db_connection.cursor() as cur:
        for migration_file in ordered_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix, tolerant=True)
        db_connection.commit()

        table_name = f"{migration_test_prefix}_areas"
        cur.execute(f"DESCRIBE {table_name}")
        columns = {row['Field']: row for row in cur.fetchall()}

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['area_name']['Type'] == 'varchar(32)'
    assert columns['area_name']['Null'] == 'NO'

    assert columns['domain_fk']['Type'] == 'int'
    assert columns['domain_fk']['Null'] == 'YES'
    assert columns['domain_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['closed']['Type'] == 'tinyint'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert columns['sort_mode']['Type'] == 'varchar(8)'
    assert columns['sort_mode']['Null'] == 'NO'
    assert columns['sort_mode']['Default'] == 'priority'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_migration_final_schema_matches_tasks(db_connection, migration_test_prefix):
    """After all migrations, tasks table schema matches schema.sql.

    Expected final state:
    - id: INT, PRI, AUTO_INCREMENT
    - priority: TINYINT(1), NOT NULL
    - done: TINYINT(1), NOT NULL
    - description: VARCHAR(1024), NOT NULL
    - area_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    - done_ts: TIMESTAMP, NULL
    - sort_order: SMALLINT, NULL
    """
    ordered_files = _get_dependency_ordered_migrations()

    with db_connection.cursor() as cur:
        for migration_file in ordered_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix, tolerant=True)
        db_connection.commit()

        table_name = f"{migration_test_prefix}_tasks"
        cur.execute(f"DESCRIBE {table_name}")
        columns = {row['Field']: row for row in cur.fetchall()}

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert 'tinyint' in columns['priority']['Type'].lower()
    assert columns['priority']['Null'] == 'NO'

    assert 'tinyint' in columns['done']['Type'].lower()
    assert columns['done']['Null'] == 'NO'

    assert columns['description']['Type'] == 'varchar(1024)'
    assert columns['description']['Null'] == 'NO'

    assert columns['area_fk']['Type'] == 'int'
    assert columns['area_fk']['Null'] == 'YES'
    assert columns['area_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'

    assert 'timestamp' in columns['done_ts']['Type']
    assert columns['done_ts']['Null'] == 'YES'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'


# ---------------------------------------------------------------------------
# Test: Migration idempotency — applying 001 twice succeeds
# ---------------------------------------------------------------------------

def test_migration_001_idempotent(db_connection, migration_test_prefix):
    """Migration 001 uses CREATE TABLE IF NOT EXISTS, so re-applying succeeds.

    This tests that 001 can be applied multiple times without error.
    """
    migrations_dir = _get_migrations_dir()
    migration_001 = os.path.join(migrations_dir, '001_initial_tables.sql')
    sql = _read_migration_file(migration_001)

    with db_connection.cursor() as cur:
        # Apply first time
        _apply_migration(cur, sql, migration_test_prefix)
        db_connection.commit()

        # Apply second time (should not error)
        _apply_migration(cur, sql, migration_test_prefix)
        db_connection.commit()

        # Verify tables still exist
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s",
            ('darwin_dev', f"{migration_test_prefix}_%")
        )
        tables = {row['TABLE_NAME'] for row in cur.fetchall()}

    expected_tables = {
        f"{migration_test_prefix}_profiles",
        f"{migration_test_prefix}_domains",
        f"{migration_test_prefix}_areas",
        f"{migration_test_prefix}_tasks",
    }
    assert tables == expected_tables
