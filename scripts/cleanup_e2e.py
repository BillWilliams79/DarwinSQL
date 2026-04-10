#!/usr/bin/env python3
"""
Cleanup orphaned E2E test data from darwin_dev or darwin database.

E2E tests create domains, areas, tasks, projects, categories, requirements,
swarm_sessions, and requirement_sessions. When tests are interrupted (Ctrl+C,
timeout, crash), afterAll cleanup never runs and stale data accumulates.

This script targets all 9 E2E test user creator_fk UUIDs (8 workers + original).

GUARDRAILS (5 layers):
1. Default database: darwin_dev (--database darwin required for production)
2. Runtime verification: SELECT DATABASE() check before any DELETE
3. Table validation: only operates on known tables
4. Dry-run default: --execute flag required for actual deletes
5. No DROP/TRUNCATE: only DELETE FROM ... WHERE with specific creator_fk values

Usage:
    # Dry run on darwin_dev (default)
    python3 cleanup_e2e.py

    # Dry run on production
    python3 cleanup_e2e.py --database darwin

    # Actually delete from darwin_dev
    python3 cleanup_e2e.py --execute

    # Actually delete from production
    python3 cleanup_e2e.py --database darwin --execute

Environment variables required (from exports.sh or mcp_credentials.sh):
    endpoint     — RDS MySQL hostname
    username     — Database username
    db_password  — Database password
"""
import argparse
import os
import sys

import pymysql

# E2E worker creator_fk UUIDs (port → worker mapping)
# Port 3000 → worker 1, 3001 → worker 2, ..., 3007 → worker 8
E2E_CREATOR_FKS = [
    ('0807ca6e-2f48-45b0-a9c4-15177859735b', 'worker 1 (port 3000)'),
    ('c0479250-4db9-4586-ad2f-5662deafdcd9', 'worker 2 (port 3001)'),
    ('de2018a8-964e-437d-8191-ca5b6f9cb8ac', 'worker 3 (port 3002)'),
    ('3e2a706e-9f79-4a74-9ca5-f783296b6f33', 'worker 4 (port 3003)'),
    ('2766f048-530d-40dd-8066-d8daf96ef0d9', 'worker 5 (port 3004)'),
    ('0e724beb-3a62-422f-923b-57633bfafc7f', 'worker 6 (port 3005)'),
    ('cc5a9202-e1f0-4973-aa88-0caaba7a7140', 'worker 7 (port 3006)'),
    ('3857b0d2-1b9b-4f64-8660-6a5b8db29c33', 'worker 8 (port 3007)'),
    ('42145f1d-e6dc-4d83-ad1c-1adac53fcbc9', 'original e2e test user'),
]

# ============================================================================
# GUARDRAIL 3: Only known tables, in FK-safe deletion order
# ============================================================================
# requirement_sessions → swarm_sessions → requirements → categories → projects → domains
# (areas/tasks cascade from domains; requirements cascade from categories)
CLEANUP_TABLES = [
    'requirement_sessions',
    'swarm_sessions',
    'requirements',
    'categories',
    'projects',
    'domains',
]

# Tables that use session_fk instead of creator_fk
SESSION_FK_TABLES = {'requirement_sessions'}


def get_connection(database):
    """Connect to the specified database."""
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def verify_database(conn, expected):
    """GUARDRAIL 2: Runtime verification of target database."""
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS db")
        result = cur.fetchone()
    actual_db = result['db']
    if actual_db != expected:
        print(f"ABORT: Expected database '{expected}', got '{actual_db}'")
        sys.exit(1)
    return actual_db


def find_e2e_data(conn):
    """Count E2E test data per creator_fk and table."""
    results = {}

    for creator_fk, label in E2E_CREATOR_FKS:
        table_counts = {}

        for table in CLEANUP_TABLES:
            if table in SESSION_FK_TABLES:
                continue  # requirement_sessions counted via session lookup

            with conn.cursor() as cur:
                try:
                    cur.execute(
                        f"SELECT COUNT(*) AS cnt FROM {table} WHERE creator_fk = %s",
                        (creator_fk,),
                    )
                    count = cur.fetchone()['cnt']
                    if count > 0:
                        table_counts[table] = count
                except pymysql.err.ProgrammingError:
                    pass  # Table doesn't exist in this database

        if table_counts:
            results[creator_fk] = {'label': label, 'tables': table_counts}

    return results


def delete_e2e_data(conn, dry_run=True):
    """Delete E2E test data in FK-safe order.

    GUARDRAIL 5: Only uses DELETE FROM ... WHERE — no DROP or TRUNCATE.
    """
    data = find_e2e_data(conn)

    if not data:
        print("No E2E test data found.")
        return 0

    total_deleted = 0
    mode = "DRY RUN" if dry_run else "EXECUTE"

    print(f"\n{'=' * 60}")
    print(f"  E2E Cleanup — {mode}")
    print(f"{'=' * 60}\n")

    for creator_fk, info in data.items():
        print(f"  {info['label']} ({creator_fk})")
        tables = info['tables']

        # First handle requirement_sessions via swarm_sessions for this creator
        if 'swarm_sessions' in tables:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "SELECT id FROM swarm_sessions WHERE creator_fk = %s",
                        (creator_fk,),
                    )
                    session_ids = [r['id'] for r in cur.fetchall()]

                    if session_ids:
                        placeholders = ','.join(['%s'] * len(session_ids))
                        cur.execute(
                            f"SELECT COUNT(*) AS cnt FROM requirement_sessions WHERE session_fk IN ({placeholders})",
                            session_ids,
                        )
                        ps_count = cur.fetchone()['cnt']

                        if ps_count > 0:
                            if dry_run:
                                print(f"    WOULD DELETE {ps_count} rows from requirement_sessions")
                            else:
                                deleted = cur.execute(
                                    f"DELETE FROM requirement_sessions WHERE session_fk IN ({placeholders})",
                                    session_ids,
                                )
                                print(f"    DELETED {deleted} rows from requirement_sessions")
                                total_deleted += deleted
                except pymysql.err.ProgrammingError:
                    pass  # Table doesn't exist

        # Delete remaining tables in FK-safe order
        for table in CLEANUP_TABLES:
            if table in SESSION_FK_TABLES:
                continue  # Handled above
            if table not in tables:
                continue

            count = tables[table]
            if dry_run:
                print(f"    WOULD DELETE {count} rows from {table}")
            else:
                with conn.cursor() as cur:
                    deleted = cur.execute(
                        f"DELETE FROM {table} WHERE creator_fk = %s",
                        (creator_fk,),
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
        description='Clean up orphaned E2E test data.',
    )
    parser.add_argument(
        '--database',
        default='darwin_dev',
        help='Target database (default: darwin_dev)',
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        default=False,
        help='Actually delete data (default: dry-run)',
    )
    args = parser.parse_args()

    # Check env vars
    for var in ('endpoint', 'username', 'db_password'):
        if var not in os.environ:
            print(f"Error: {var} environment variable not set.")
            print("Run: . exports.sh  (from Lambda-Rest/ directory)")
            print("  or: . ~/.darwin-credentials/mcp_credentials.sh")
            sys.exit(1)

    # GUARDRAIL 1: Validate database name
    if args.database not in ('darwin', 'darwin_dev'):
        print(f"ABORT: Invalid database '{args.database}'. Must be 'darwin' or 'darwin_dev'.")
        sys.exit(1)

    conn = get_connection(args.database)
    try:
        # GUARDRAIL 2: Verify database before any operations
        db = verify_database(conn, args.database)
        print(f"Connected to database: {db}")

        delete_e2e_data(conn, dry_run=not args.execute)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
