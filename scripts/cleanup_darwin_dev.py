#!/usr/bin/env python3
"""
Cleanup orphaned test data from darwin_dev test database.

This script identifies and removes test data left behind by failed or
interrupted test runs. It operates ONLY on the darwin_dev test database.

GUARDRAILS (5 layers):
1. Hardcoded database: connects to 'darwin_dev' only (literal string, not env var)
2. Runtime verification: SELECT DATABASE() check before any DELETE
3. Table validation: only operates on known tables
4. Dry-run default: --execute flag required for actual deletes
5. No DROP/TRUNCATE: only DELETE FROM ... WHERE with specific patterns

Usage:
    # Dry run (default) — shows what WOULD be deleted
    python3 cleanup_darwin_dev.py

    # Actually delete orphaned data
    python3 cleanup_darwin_dev.py --execute

    # Chain after test runs
    cd Lambda-Rest && . exports.sh && pytest tests/ -v && \\
        python3 ../DarwinSQL/scripts/cleanup_darwin_dev.py --execute

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
TARGET_DATABASE = 'darwin_dev'

# ============================================================================
# GUARDRAIL 3: Only known tables
# ============================================================================
VALID_TABLES = ('profiles', 'domains', 'areas', 'tasks')

# Test data identification patterns
# These match the creator_fk/id patterns used by each test suite
CLEANUP_PATTERNS = [
    # Lambda-Cognito tests: conftest.py generates 'cognito-test-{hex}'
    ('cognito-test-%', 'Lambda-Cognito test data'),
    # Lambda-Rest tests: conftest.py generates 'pytest-{timestamp}-{hex}'
    ('pytest-%', 'Lambda-Rest test data'),
]


def get_connection():
    """Connect to darwin_dev with hardcoded database name."""
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=TARGET_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def verify_database(conn):
    """GUARDRAIL 2: Runtime verification that we're on darwin_dev."""
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
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE creator_fk LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['tasks'] = count

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM areas WHERE creator_fk LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['areas'] = count

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM domains WHERE creator_fk LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['domains'] = count

            # profiles use 'id' not 'creator_fk'
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM profiles WHERE id LIKE %s",
                (pattern,),
            )
            count = cur.fetchone()['cnt']
            if count > 0:
                pattern_orphans['profiles'] = count

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
        print("No orphaned test data found in darwin_dev.")
        return 0

    total_deleted = 0
    mode = "DRY RUN" if dry_run else "EXECUTE"

    print(f"\n{'=' * 60}")
    print(f"  darwin_dev Cleanup — {mode}")
    print(f"{'=' * 60}\n")

    for pattern, info in orphans.items():
        print(f"  Pattern: {pattern} ({info['description']})")
        tables = info['tables']

        # Delete in FK-safe order: tasks → areas → domains → profiles
        for table in ('tasks', 'areas', 'domains', 'profiles'):
            # GUARDRAIL 3: Validate table name
            if table not in VALID_TABLES:
                print(f"    SKIP: {table} not in valid table list")
                continue

            if table not in tables:
                continue

            count = tables[table]
            column = 'id' if table == 'profiles' else 'creator_fk'

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
        description='Clean up orphaned test data from darwin_dev test database.',
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
