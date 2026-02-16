"""
Test migration correctness and schema evolution.

Applies migrations 001-008 to temporary tables in darwin2, verifies final schema
matches expected state. Validates that migrations are idempotent and can be applied
to fresh tables.

Test workflow:
1. Create temporary prefixed tables (mig_{prefix}_profiles, etc.)
2. Apply migrations in order
3. DESCRIBE final tables and verify schema matches expectations
4. DROP temporary tables after test cleanup
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


def _apply_migration(cur, sql_content, table_prefix):
    """Apply migration SQL with table name replacements.

    Replaces unqualified table names with prefixed versions:
    - profiles → {prefix}_profiles
    - domains → {prefix}_domains
    - areas → {prefix}_areas
    - tasks → {prefix}_tasks

    Skips CREATE DATABASE, USE, and comment-only statements.
    """
    # Strip lines referencing darwin2-specific table names (e.g. areas2, tasks2)
    # These are environment-specific duplicates; the test only creates non-suffixed tables.
    filtered_lines = []
    for line in sql_content.split('\n'):
        stripped = line.strip().lower()
        if any(t in stripped for t in ['profiles2', 'domains2', 'areas2', 'tasks2']):
            continue
        filtered_lines.append(line)
    sql = '\n'.join(filtered_lines)

    # Replace table names with prefixed versions (order: longest first to avoid partial matches)
    sql = sql.replace('`profiles`', f'`{table_prefix}_profiles`')
    sql = sql.replace('`domains`', f'`{table_prefix}_domains`')
    sql = sql.replace('`areas`', f'`{table_prefix}_areas`')
    sql = sql.replace('`tasks`', f'`{table_prefix}_tasks`')
    # Also replace unquoted names
    sql = sql.replace('profiles', f'{table_prefix}_profiles')
    sql = sql.replace('domains', f'{table_prefix}_domains')
    sql = sql.replace('areas', f'{table_prefix}_areas')
    sql = sql.replace('tasks', f'{table_prefix}_tasks')

    # Remove SQL comments first (both -- and # style)
    lines = []
    for line in sql.split('\n'):
        # Remove -- comments
        if '--' in line:
            line = line[:line.index('--')]
        # Remove # comments
        if '#' in line and not "'" in line[:line.index('#')]:  # Avoid removing # inside strings
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
        # Skip control statements
        upper_stmt = stmt.upper()
        if upper_stmt.startswith(('CREATE DATABASE', 'USE ')):
            continue
        try:
            cur.execute(stmt)
        except Exception as e:
            # Re-raise with context
            raise RuntimeError(f"Migration statement failed:\n{stmt}\nError: {e}")


# ---------------------------------------------------------------------------
# Per-test cleanup fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_migration_test_tables(db_connection, migration_test_prefix):
    """Cleanup temporary migration tables before and after each test.

    Ensures each test starts with a clean slate.
    """
    # Cleanup before test
    with db_connection.cursor() as cur:
        for suffix in ['tasks', 'areas', 'domains', 'profiles']:
            try:
                cur.execute(f"DROP TABLE IF EXISTS `{migration_test_prefix}_{suffix}`")
            except Exception:
                pass
    db_connection.commit()

    yield

    # Cleanup after test
    with db_connection.cursor() as cur:
        for suffix in ['tasks', 'areas', 'domains', 'profiles']:
            try:
                cur.execute(f"DROP TABLE IF EXISTS `{migration_test_prefix}_{suffix}`")
            except Exception:
                pass
    db_connection.commit()


# ---------------------------------------------------------------------------
# Test: Migration creates tables
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

        # Verify tables exist by querying information_schema
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s",
            ('darwin2', f"{migration_test_prefix}_%")
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
# Test: All migrations apply successfully in order
# ---------------------------------------------------------------------------

def test_migration_sequence_applies(db_connection, migration_test_prefix):
    """Apply all migrations 001-008 in sequence to temp tables.

    Verifies that migrations can be applied in order without errors.
    """
    migrations_dir = _get_migrations_dir()
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

    with db_connection.cursor() as cur:
        for migration_file in migration_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix)
            db_connection.commit()

        # After all migrations, verify 4 tables exist
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s",
            ('darwin2', f"{migration_test_prefix}_%")
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
# Test: Final schema after all migrations matches expectations
# ---------------------------------------------------------------------------

def test_migration_final_schema_matches_profiles(db_connection, migration_test_prefix):
    """After all migrations, profiles table schema matches schema.sql.

    Expected final state:
    - id: VARCHAR(64), PRI
    - name: VARCHAR(256), NOT NULL
    - email: VARCHAR(256), NOT NULL
    - subject: VARCHAR(64), NOT NULL
    - userName: VARCHAR(256), NOT NULL
    - region: VARCHAR(128), NOT NULL
    - userPoolId: VARCHAR(128), NOT NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    migrations_dir = _get_migrations_dir()
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

    with db_connection.cursor() as cur:
        for migration_file in migration_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix)
        db_connection.commit()

        # DESCRIBE final table
        table_name = f"{migration_test_prefix}_profiles"
        cur.execute(f"DESCRIBE {table_name}")
        columns = {row['Field']: row for row in cur.fetchall()}

    # Verify schema
    assert columns['id']['Type'] == 'varchar(64)'
    assert columns['id']['Key'] == 'PRI'

    assert columns['name']['Type'] == 'varchar(256)'
    assert columns['name']['Null'] == 'NO'

    assert columns['email']['Type'] == 'varchar(256)'
    assert columns['email']['Null'] == 'NO'

    assert columns['subject']['Type'] == 'varchar(64)'
    assert columns['subject']['Null'] == 'NO'

    assert columns['userName']['Type'] == 'varchar(256)'
    assert columns['userName']['Null'] == 'NO'

    assert columns['region']['Type'] == 'varchar(128)'
    assert columns['region']['Null'] == 'NO'

    assert columns['userPoolId']['Type'] == 'varchar(128)'
    assert columns['userPoolId']['Null'] == 'NO'

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
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    migrations_dir = _get_migrations_dir()
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

    with db_connection.cursor() as cur:
        for migration_file in migration_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix)
        db_connection.commit()

        table_name = f"{migration_test_prefix}_domains"
        cur.execute(f"DESCRIBE {table_name}")
        columns = {row['Field']: row for row in cur.fetchall()}

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
    migrations_dir = _get_migrations_dir()
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

    with db_connection.cursor() as cur:
        for migration_file in migration_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix)
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
    migrations_dir = _get_migrations_dir()
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

    with db_connection.cursor() as cur:
        for migration_file in migration_files:
            sql = _read_migration_file(migration_file)
            _apply_migration(cur, sql, migration_test_prefix)
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
            ('darwin2', f"{migration_test_prefix}_%")
        )
        tables = {row['TABLE_NAME'] for row in cur.fetchall()}

    expected_tables = {
        f"{migration_test_prefix}_profiles",
        f"{migration_test_prefix}_domains",
        f"{migration_test_prefix}_areas",
        f"{migration_test_prefix}_tasks",
    }
    assert tables == expected_tables
