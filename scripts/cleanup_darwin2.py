#!/usr/bin/env python3
"""
Cleanup orphaned test data from darwin2 test database.

This script identifies and removes test data left behind by failed or
interrupted test runs. It operates ONLY on the darwin2 test database
and ONLY on tables with the '2' suffix.

GUARDRAILS (5 layers):
1. Hardcoded database: connects to 'darwin2' only (literal string, not env var)
2. Runtime verification: SELECT DATABASE() check before any DELETE
3. Table suffix validation: only operates on tables ending in '2'
4. Dry-run default: --execute flag required for actual deletes
5. No DROP/TRUNCATE: only DELETE FROM ... WHERE with specific patterns

Usage:
    # Dry run (default) — shows what WOULD be deleted
    python3 cleanup_darwin2.py

    # Actually delete orphaned data
    python3 cleanup_darwin2.py --execute

    # Chain after test runs
    cd Lambda-Rest && . exports.sh && pytest tests/ -v && \\
        python3 ../DarwinSQL/scripts/cleanup_darwin2.py --execute

Environment variables required (from exports.sh):
    endpoint     — RDS MySQL hostname
    username     — Database username
    db_password  — Database password
"""
import argparse
import os
import sys

import pymysql

# ============================================================================
# GUARDRAIL 1: Hardcoded database name — never from env var
# ============================================================================
TARGET_DATABASE = 'darwin2'

# ============================================================================
# GUARDRAIL 3: Only tables with '2' suffix
# ============================================================================
VALID_TABLES = ('profiles2', 'domains2', 'areas2', 'tasks2')

# Test data identification patterns
# These match the creator_fk/id patterns used by each test suite
CLEANUP_PATTERNS = [
    # Lambda-Cognito tests: conftest.py generates 'cognito-test-{hex}'
    ('cognito-test-%', 'Lambda-Cognito test data'),
    # Lambda-Rest tests: conftest.py generates 'pytest-{timestamp}-{hex}'
    ('pytest-%', 'Lambda-Rest test data'),
]


def get_connection():
    """Connect to darwin2 with hardcoded database name."""
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=TARGET_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def verify_database(conn):
    """GUARDRAIL 2: Runtime verification that we're on darwin2."""
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS db")
        result = cur.fetchone()
    actual_db = result['db']
    if actual_db != TARGET_DATABASE:
        print(f"ABORT: Expected database '{TARGET_DATABASE}', got '{actual_db}'")
        sys.exit(1)
    return actual_db


def find_orphaned_data(conn):
    """Identify orphaned test data by pattern matching."""
    orphans = {}

    for pattern, description in CLEANUP_PATTERNS:
        pattern_orphans = {}

        with conn.cursor() as cur:
            # FK-order: count from leaves to roots
            # tasks2 (leaf)
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM tasks2 WHERE creator_fk LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['tasks2'] = count

            # areas2
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM areas2 WHERE creator_fk LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['areas2'] = count

            # domains2
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM domains2 WHERE creator_fk LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['domains2'] = count

            # profiles2 (root) — profiles use 'id' not 'creator_fk'
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM profiles2 WHERE id LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['profiles2'] = count

        if pattern_orphans:
            orphans[pattern] = {
                'description': description,
                'tables': pattern_orphans,
            }

    return orphans


def delete_orphaned_data(conn, dry_run=True):
    """Delete orphaned test data in FK-safe order.

    GUARDRAIL 5: Only uses DELETE FROM ... WHERE — no DROP or TRUNCATE.
    """
    orphans = find_orphaned_data(conn)

    if not orphans:
        print("No orphaned test data found in darwin2.")
        return 0

    total_deleted = 0
    mode = "DRY RUN" if dry_run else "EXECUTE"

    print(f"\n{'=' * 60}")
    print(f"  darwin2 Cleanup — {mode}")
    print(f"{'=' * 60}\n")

    for pattern, info in orphans.items():
        print(f"  Pattern: {pattern} ({info['description']})")
        tables = info['tables']

        # Delete in FK-safe order: tasks2 → areas2 → domains2 → profiles2
        for table in ('tasks2', 'areas2', 'domains2', 'profiles2'):
            # GUARDRAIL 3: Validate table name has '2' suffix
            if table not in VALID_TABLES:
                print(f"    SKIP: {table} not in valid table list")
                continue

            if table not in tables:
                continue

            count = tables[table]
            column = 'id' if table == 'profiles2' else 'creator_fk'

            if dry_run:
                print(f"    WOULD DELETE {count} rows from {table} WHERE {column} LIKE '{pattern}'")
            else:
                with conn.cursor() as cur:
                    deleted = cur.execute(
                        f"DELETE FROM {table} WHERE {column} LIKE %s",
                        (pattern,),
                    )
                    print(f"    DELETED {deleted} rows from {table}")
                    total_deleted += deleted

        print()

    if not dry_run:
        conn.commit()
        print(f"Total rows deleted: {total_deleted}")
    else:
        print("  Run with --execute to actually delete these rows.")

    return total_deleted


def main():
    parser = argparse.ArgumentParser(
        description='Clean up orphaned test data from darwin2 test database.',
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        default=False,
        help='Actually delete data (default: dry-run showing what WOULD be deleted)',
    )
    args = parser.parse_args()

    # Check env vars
    for var in ('endpoint', 'username', 'db_password'):
        if var not in os.environ:
            print(f"Error: {var} environment variable not set.")
            print("Run: . exports.sh  (from Lambda-Rest/ or Lambda-Cognito/ directory)")
            sys.exit(1)

    conn = get_connection()
    try:
        # GUARDRAIL 2: Verify database before any operations
        db = verify_database(conn)
        print(f"Connected to database: {db}")

        delete_orphaned_data(conn, dry_run=not args.execute)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
