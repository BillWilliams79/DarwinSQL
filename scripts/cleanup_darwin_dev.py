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

# E2E test worker creator_fk UUIDs (exact match, not LIKE patterns)
# Port 3000 → worker 1, 3001 → worker 2, ..., 3007 → worker 8
E2E_WORKER_CREATOR_FKS = [
    ('0807ca6e-2f48-45b0-a9c4-15177859735b', 'E2E worker 1 (port 3000)'),
    ('c0479250-4db9-4586-ad2f-5662deafdcd9', 'E2E worker 2 (port 3001)'),
    ('de2018a8-964e-437d-8191-ca5b6f9cb8ac', 'E2E worker 3 (port 3002)'),
    ('3e2a706e-9f79-4a74-9ca5-f783296b6f33', 'E2E worker 4 (port 3003)'),
    ('2766f048-530d-40dd-8066-d8daf96ef0d9', 'E2E worker 5 (port 3004)'),
    ('0e724beb-3a62-422f-923b-57633bfafc7f', 'E2E worker 6 (port 3005)'),
    ('cc5a9202-e1f0-4973-aa88-0caaba7a7140', 'E2E worker 7 (port 3006)'),
    ('3857b0d2-1b9b-4f64-8660-6a5b8db29c33', 'E2E worker 8 (port 3007)'),
    ('42145f1d-e6dc-4d83-ad1c-1adac53fcbc9', 'E2E original test user'),
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
    """Identify orphaned test data by pattern matching and exact creator_fk."""
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

    # E2E worker data uses exact creator_fk match (not LIKE)
    for creator_fk, description in E2E_WORKER_CREATOR_FKS:
        worker_orphans = {}

        with conn.cursor() as cur:
            for table in ('tasks', 'areas', 'domains'):
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table} WHERE creator_fk = %s",
                    (creator_fk,),
                )
                count = cur.fetchone()['cnt']
                if count > 0:
                    worker_orphans[table] = count

        if worker_orphans:
            orphans[creator_fk] = {
                'description': description,
                'tables': worker_orphans,
                'exact_match': True,
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
        is_exact = info.get('exact_match', False)
        match_type = '=' if is_exact else 'LIKE'
        print(f"  {'Creator' if is_exact else 'Pattern'}: {pattern} ({info['description']})")
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
                print(f"    WOULD DELETE {count} rows from {table} WHERE {column} {match_type} '{pattern}'")
            else:
                with conn.cursor() as cur:
                    op = '=' if is_exact else 'LIKE'
                    deleted = cur.execute(
                        f"DELETE FROM {table} WHERE {column} {op} %s",
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
