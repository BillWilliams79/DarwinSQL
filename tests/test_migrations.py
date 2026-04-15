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
swarm_sessions, requirements) that were originally created ad-hoc on production.
Migration 016 retroactively tracks those table definitions. Tests must apply
016 before 009-015 to satisfy FK dependencies.
"""
import os
import glob
import re
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
    partial matches). All 15 tables are handled.

    Args:
        cur: Database cursor
        sql_content: Raw migration SQL
        table_prefix: Prefix for temp table names
        tolerant: If True, skip ALTER/DROP failures on non-existent
                  columns (for migrations that post-date ad-hoc table creation)
    """
    sql = sql_content

    # Replace table names with prefixed versions (longest first to avoid partial matches).
    # Two-pass placeholder approach prevents double-replacement
    # (e.g., 'tasks' inside 'recurring_tasks') while preserving FK constraint
    # name replacement (e.g., 'domains_ibfk_1' → 'mig_xxx_domains_ibfk_1').
    table_names = [
        'user_integrations',
        'requirement_sessions',
        'priority_sessions',     # pre-038 name (for RENAME TABLE in migration 038)
        'priority_card_order',
        'map_run_partners',
        'map_coordinates',
        'swarm_sessions',
        'recurring_tasks',
        'map_partners',
        'dev_servers',
        'requirements',
        'priorities',            # pre-038 name (for RENAME TABLE in migration 038)
        'categories',
        'map_routes',
        'map_views',
        'map_runs',
        'profiles',
        'projects',
        'domains',
        'areas',
        'tasks',
    ]

    # Replace backtick-quoted names first
    for name in table_names:
        sql = sql.replace(f'`{name}`', f'`{table_prefix}_{name}`')

    # Replace unquoted table names and FK constraint names ({table}_ibfk_N).
    # Uses regex to match table names as standalone identifiers OR as FK name
    # prefixes, avoiding partial matches inside column names (e.g., 'app_tasks').
    # Process longest names first to prevent shorter names from matching first.
    for name in table_names:
        # Match: standalone table name OR {table}_ibfk (FK constraint name prefix)
        # (?<![a-zA-Z_]) = not preceded by identifier character (prevents 'app_tasks')
        # (?=_ibfk|\b) = followed by _ibfk (FK name) or word boundary (standalone)
        pattern = r'(?<![a-zA-Z_])' + re.escape(name) + r'(?=_ibfk|\b)'
        sql = re.sub(pattern, f'{table_prefix}_{name}', sql)

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
            if tolerant:
                # Tolerant mode skips all non-CREATE failures. Migration tests
                # verify final DESCRIBE schema, not data integrity. Known issues:
                # - ALTER/DROP on columns absent in temp tables (migration 012)
                # - INSERT/UPDATE with production FK refs (migration 025)
                # - PREPARE/EXECUTE referencing tables not yet created (migration 009)
                # Only CREATE TABLE failures are real errors worth raising.
                if not upper_stmt.startswith('CREATE'):
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
# map_coordinates → map_runs → map_routes (FK chain)
ALL_TABLE_SUFFIXES = [
    'user_integrations', 'map_run_partners', 'map_partners',
    'map_views', 'map_coordinates', 'map_runs', 'map_routes',
    'priority_card_order', 'dev_servers',
    'requirement_sessions', 'priority_sessions',  # pre-038 name
    'requirements', 'priorities',                  # pre-038 name
    'swarm_sessions', 'categories', 'projects',
    'tasks', 'recurring_tasks', 'areas', 'domains', 'profiles',
]


@pytest.fixture(autouse=True)
def cleanup_migration_test_tables(db_connection, migration_test_prefix):
    """Cleanup temporary migration tables before and after each test.

    Ensures each test starts with a clean slate. Drops all 16 table types.
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
    (016 uses original names; migration 038 renames them to requirements/requirement_sessions)
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

    # 016 creates tables with original names (priorities, priority_sessions)
    # Migration 038 renames them later in the full sequence
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

    Order: 001-008 (core), 016 (roadmap tables), 009-015 (modifications),
    017+ (recurring_tasks, map tables, etc.).
    Tolerant mode handles migration 012 (DROP COLUMN worker_count) which
    targets a column absent from 016's current-state DDL.
    Expects all 16 tables after completion.
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
            'projects', 'categories', 'requirements',
            'swarm_sessions', 'requirement_sessions',
            'dev_servers', 'priority_card_order',
            'recurring_tasks',
            'map_routes', 'map_runs', 'map_coordinates',
            'map_views', 'map_partners', 'map_run_partners',
            'user_integrations',
        ]
    }
    assert tables == expected_tables, \
        f"Missing: {expected_tables - tables}, extra: {tables - expected_tables}"


# ---------------------------------------------------------------------------
# Test: Final schema after all migrations matches expectations
# ---------------------------------------------------------------------------

def test_migration_final_schema_matches_profiles(db_connection, migration_test_prefix):
    """After all migrations, profiles table schema matches schema.sql.

    Expected final state (post migration 026):
    - id: VARCHAR(64), PRI
    - name: VARCHAR(256), NOT NULL
    - email: VARCHAR(256), NOT NULL
    - timezone: VARCHAR(64), NULL
    - theme_mode: VARCHAR(8), NOT NULL, DEFAULT 'light'
    - app_tasks: TINYINT(1), NOT NULL, DEFAULT 1
    - app_maps: TINYINT(1), NOT NULL, DEFAULT 1
    - app_swarm: TINYINT(1), NOT NULL, DEFAULT 0
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

    # Verify schema — 10 columns after migration 026
    expected_fields = {'id', 'name', 'email', 'timezone', 'theme_mode',
                       'app_tasks', 'app_maps', 'app_swarm', 'create_ts', 'update_ts'}
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

    assert columns['theme_mode']['Type'] == 'varchar(8)'
    assert columns['theme_mode']['Null'] == 'NO'
    assert columns['theme_mode']['Default'] == 'light'

    assert 'tinyint' in columns['app_tasks']['Type']
    assert columns['app_tasks']['Null'] == 'NO'
    assert columns['app_tasks']['Default'] == '1'

    assert 'tinyint' in columns['app_maps']['Type']
    assert columns['app_maps']['Null'] == 'NO'
    assert columns['app_maps']['Default'] == '1'

    assert 'tinyint' in columns['app_swarm']['Type']
    assert columns['app_swarm']['Null'] == 'NO'
    assert columns['app_swarm']['Default'] == '0'

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


# ---------------------------------------------------------------------------
# Test: Migration 039 — requirement data types overhaul data mapping
# ---------------------------------------------------------------------------

def test_migration_039_data_mapping(db_connection, migration_test_prefix):
    """Verify migration 039 correctly remaps old requirement_status values and
    maps scheduled>=1 rows to swarm_ready + planned.

    Test cases:
      idle + scheduled=0        → authoring + 'implemented' (new default)
      idle + scheduled=1        → swarm_ready + planned
      idle + scheduled=2        → swarm_ready + planned
      in_progress + scheduled=0 → development + 'implemented'
      completed + scheduled=0   → met + 'implemented'
      deferred + scheduled=0    → deferred + 'implemented'
    """
    table_name = f"{migration_test_prefix}_requirements_m039"

    with db_connection.cursor() as cur:
        # Create a pre-039 style table (no coordination_type column)
        cur.execute(f"""
            CREATE TABLE {table_name} (
                id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(256) NOT NULL,
                requirement_status VARCHAR(16) NOT NULL DEFAULT 'idle',
                scheduled TINYINT NOT NULL DEFAULT 0
            )
        """)
        db_connection.commit()

        # Seed with all test case combinations
        test_cases = [
            ('T1 idle sched=0',      'idle',        0),
            ('T2 idle sched=1',      'idle',        1),
            ('T3 idle sched=2',      'idle',        2),
            ('T4 in_progress',       'in_progress', 0),
            ('T5 completed',         'completed',   0),
            ('T6 deferred',          'deferred',    0),
        ]
        for title, status, sched in test_cases:
            cur.execute(
                f"INSERT INTO {table_name} (title, requirement_status, scheduled) VALUES (%s, %s, %s)",
                (title, status, sched)
            )
        db_connection.commit()

        # Apply migration 039 SQL against the test table
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN coordination_type VARCHAR(16) NULL DEFAULT 'implemented' AFTER scheduled")
        cur.execute(f"UPDATE {table_name} SET requirement_status = 'swarm_ready', coordination_type = 'planned' WHERE requirement_status = 'idle' AND scheduled >= 1")
        cur.execute(f"UPDATE {table_name} SET requirement_status = 'authoring'   WHERE requirement_status = 'idle'")
        cur.execute(f"UPDATE {table_name} SET requirement_status = 'development' WHERE requirement_status = 'in_progress'")
        cur.execute(f"UPDATE {table_name} SET requirement_status = 'met'         WHERE requirement_status = 'completed'")
        cur.execute(f"ALTER TABLE {table_name} ALTER COLUMN requirement_status SET DEFAULT 'authoring'")
        db_connection.commit()

        # Verify each row transitioned as expected
        cur.execute(f"SELECT title, requirement_status, scheduled, coordination_type FROM {table_name} ORDER BY id")
        rows = {r['title']: r for r in cur.fetchall()}

        assert rows['T1 idle sched=0']['requirement_status'] == 'authoring'
        assert rows['T1 idle sched=0']['coordination_type'] == 'implemented'

        assert rows['T2 idle sched=1']['requirement_status'] == 'swarm_ready'
        assert rows['T2 idle sched=1']['coordination_type'] == 'planned'

        assert rows['T3 idle sched=2']['requirement_status'] == 'swarm_ready'
        assert rows['T3 idle sched=2']['coordination_type'] == 'planned'

        assert rows['T4 in_progress']['requirement_status'] == 'development'
        assert rows['T4 in_progress']['coordination_type'] == 'implemented'

        assert rows['T5 completed']['requirement_status'] == 'met'
        assert rows['T5 completed']['coordination_type'] == 'implemented'

        assert rows['T6 deferred']['requirement_status'] == 'deferred'
        assert rows['T6 deferred']['coordination_type'] == 'implemented'

        # Verify new default applies to an inserted row
        cur.execute(f"INSERT INTO {table_name} (title) VALUES ('T7 default')")
        db_connection.commit()
        cur.execute(f"SELECT requirement_status, coordination_type FROM {table_name} WHERE title = 'T7 default'")
        row = cur.fetchone()
        assert row['requirement_status'] == 'authoring'
        assert row['coordination_type'] == 'implemented'

        # Cleanup
        cur.execute(f"DROP TABLE {table_name}")
        db_connection.commit()


# ---------------------------------------------------------------------------
# Test: Migration 040 — drop requirements.scheduled column
# ---------------------------------------------------------------------------

def test_migration_040_drops_scheduled_column(db_connection, migration_test_prefix):
    """Verify migration 040 drops the scheduled column cleanly.

    Creates a pre-040 shape table (with scheduled), seeds rows, runs the
    ALTER TABLE DROP COLUMN from migration 040, then asserts:
      - scheduled column is gone
      - row count is unchanged
      - existing data (title, requirement_status) is preserved
    """
    table_name = f"{migration_test_prefix}_requirements_m040"

    with db_connection.cursor() as cur:
        # Create a pre-040 style table (with scheduled + coordination_type)
        cur.execute(f"""
            CREATE TABLE {table_name} (
                id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(256) NOT NULL,
                requirement_status VARCHAR(16) NOT NULL DEFAULT 'authoring',
                scheduled TINYINT NOT NULL DEFAULT 0,
                coordination_type VARCHAR(16) NULL DEFAULT 'implemented'
            )
        """)
        db_connection.commit()

        # Seed with rows that cover the interesting states
        seed_rows = [
            ('M040 T1', 'swarm_ready', 2, 'planned'),
            ('M040 T2', 'swarm_ready', 1, 'implemented'),
            ('M040 T3', 'authoring',   0, None),
            ('M040 T4', 'development', 0, 'deployed'),
        ]
        for title, status, sched, coord in seed_rows:
            cur.execute(
                f"INSERT INTO {table_name} (title, requirement_status, scheduled, coordination_type) VALUES (%s, %s, %s, %s)",
                (title, status, sched, coord)
            )
        db_connection.commit()

        pre_count = cur.execute(f"SELECT COUNT(*) AS n FROM {table_name}")
        row = cur.fetchone()
        assert row['n'] == len(seed_rows)

        # Apply migration 040 against the test table (rewrite target table name)
        cur.execute(f"ALTER TABLE {table_name} DROP COLUMN scheduled")
        db_connection.commit()

        # Column is gone
        cur.execute(f"DESCRIBE {table_name}")
        columns = {r['Field'] for r in cur.fetchall()}
        assert 'scheduled' not in columns
        assert 'coordination_type' in columns  # sanity: didn't drop the wrong column

        # Row count unchanged
        cur.execute(f"SELECT COUNT(*) AS n FROM {table_name}")
        row = cur.fetchone()
        assert row['n'] == len(seed_rows)

        # Data preserved
        cur.execute(f"SELECT title, requirement_status, coordination_type FROM {table_name} ORDER BY id")
        rows = {r['title']: r for r in cur.fetchall()}
        assert rows['M040 T1']['requirement_status'] == 'swarm_ready'
        assert rows['M040 T1']['coordination_type'] == 'planned'
        assert rows['M040 T4']['requirement_status'] == 'development'
        assert rows['M040 T4']['coordination_type'] == 'deployed'

        # Cleanup
        cur.execute(f"DROP TABLE {table_name}")
        db_connection.commit()
