#!/usr/bin/env python3
"""
Seed E2E worker profiles into a target database.

Creates profile records for 8 parallel E2E test workers (e2e-worker-1 through
e2e-worker-8). Each worker maps to a dev server port (3000-3007) and gets its
own data partition via creator_fk scoping.

GUARDRAILS:
1. Target database via --database arg (default: darwin_dev)
2. INSERT IGNORE — idempotent, safe to re-run
3. No schema changes — profiles table must already exist

Usage:
    cd Lambda-Rest && . exports.sh && python3 ../DarwinSQL/scripts/seed_e2e_workers.py
    cd Lambda-Rest && . exports.sh && python3 ../DarwinSQL/scripts/seed_e2e_workers.py --database darwin

Environment variables required (from exports.sh):
    endpoint     — RDS MySQL hostname
    username     — Database username (admin)
    db_password  — Database password
"""
import argparse
import os
import sys

import pymysql

# Worker profiles: Cognito sub UUIDs from admin-create-user
WORKERS = [
    {'id': '0807ca6e-2f48-45b0-a9c4-15177859735b', 'name': 'E2E Worker 1', 'email': 'e2e-worker-1@test.invalid', 'port': 3000},
    {'id': 'c0479250-4db9-4586-ad2f-5662deafdcd9', 'name': 'E2E Worker 2', 'email': 'e2e-worker-2@test.invalid', 'port': 3001},
    {'id': 'de2018a8-964e-437d-8191-ca5b6f9cb8ac', 'name': 'E2E Worker 3', 'email': 'e2e-worker-3@test.invalid', 'port': 3002},
    {'id': '3e2a706e-9f79-4a74-9ca5-f783296b6f33', 'name': 'E2E Worker 4', 'email': 'e2e-worker-4@test.invalid', 'port': 3003},
    {'id': '2766f048-530d-40dd-8066-d8daf96ef0d9', 'name': 'E2E Worker 5', 'email': 'e2e-worker-5@test.invalid', 'port': 3004},
    {'id': '0e724beb-3a62-422f-923b-57633bfafc7f', 'name': 'E2E Worker 6', 'email': 'e2e-worker-6@test.invalid', 'port': 3005},
    {'id': 'cc5a9202-e1f0-4973-aa88-0caaba7a7140', 'name': 'E2E Worker 7', 'email': 'e2e-worker-7@test.invalid', 'port': 3006},
    {'id': '3857b0d2-1b9b-4f64-8660-6a5b8db29c33', 'name': 'E2E Worker 8', 'email': 'e2e-worker-8@test.invalid', 'port': 3007},
]


def get_connection(database):
    """Connect to the target database."""
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def seed_workers(conn, database):
    """Seed worker profiles and their Personal domains."""
    with conn.cursor() as cur:
        # Verify we're on the right database
        cur.execute("SELECT DATABASE() AS db")
        actual = cur.fetchone()['db']
        if actual != database:
            print(f"ABORT: Expected '{database}', got '{actual}'")
            sys.exit(1)

        seeded = 0
        for w in WORKERS:
            cur.execute(
                "INSERT IGNORE INTO profiles (id, name, email) "
                "VALUES (%s, %s, %s)",
                (w['id'], w['name'], w['email']),
            )
            if cur.rowcount:
                seeded += 1
                print(f"  Seeded: {w['name']} ({w['id']}) — port {w['port']}")
            else:
                print(f"  Exists: {w['name']} ({w['id']}) — port {w['port']}")

            # Seed Personal domain (what Cognito post-confirmation trigger creates)
            cur.execute(
                "INSERT IGNORE INTO domains (domain_name, creator_fk, closed) "
                "VALUES ('Personal', %s, 0)",
                (w['id'],),
            )

        print(f"\n{seeded} new profiles seeded into '{database}' ({len(WORKERS) - seeded} already existed).")


def main():
    parser = argparse.ArgumentParser(description='Seed E2E worker profiles')
    parser.add_argument('--database', default='darwin_dev',
                        help='Target database (default: darwin_dev)')
    args = parser.parse_args()

    for var in ('endpoint', 'username', 'db_password'):
        if var not in os.environ:
            print(f"Error: {var} environment variable not set.")
            print("Run: . exports.sh  (from Lambda-Rest/ directory)")
            sys.exit(1)

    conn = get_connection(args.database)
    try:
        print(f"Seeding E2E worker profiles into '{args.database}'...")
        seed_workers(conn, args.database)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
