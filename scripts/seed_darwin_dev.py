#!/usr/bin/env python3
"""
Create and seed the darwin_dev test database.

Creates the darwin_dev database with production-identical table names,
grants read-only access to claude_ro, and seeds the E2E test user profile.

GUARDRAILS:
1. Hardcoded database: creates/uses 'darwin_dev' only
2. Runtime verification: SELECT DATABASE() check after USE
3. Idempotent: CREATE DATABASE IF NOT EXISTS, INSERT IGNORE for seed data
4. No production tables touched

Usage:
    cd Lambda-Rest && . exports.sh && python3 ../DarwinSQL/scripts/seed_darwin_dev.py

Environment variables required (from exports.sh):
    endpoint     — RDS MySQL hostname
    username     — Database username (admin)
    db_password  — Database password
"""
import os
import sys

import pymysql

TARGET_DATABASE = 'darwin_dev'

# E2E test user — pre-provisioned so E2E tests can run without real Cognito signup
E2E_TEST_SUB = '42145f1d-e6dc-4d83-ad1c-1adac53fcbc9'
E2E_TEST_PROFILE = {
    'id': E2E_TEST_SUB,
    'name': 'E2E Test User',
    'email': 'e2e-test@test.invalid',
    'subject': E2E_TEST_SUB,
    'userName': 'e2e-test-user',
    'region': 'us-west-1',
    'userPoolId': 'us-west-1_jqN0WLASK',
}


def get_admin_connection():
    """Connect as admin WITHOUT specifying a database."""
    return pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def create_database(conn):
    """Create darwin_dev database if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {TARGET_DATABASE}")
        print(f"Database '{TARGET_DATABASE}' ready.")


def create_tables(conn):
    """Create tables from schema.sql DDL (production-identical names)."""
    with conn.cursor() as cur:
        cur.execute(f"USE {TARGET_DATABASE}")

        # Verify we're on the right database
        cur.execute("SELECT DATABASE() AS db")
        actual = cur.fetchone()['db']
        if actual != TARGET_DATABASE:
            print(f"ABORT: Expected '{TARGET_DATABASE}', got '{actual}'")
            sys.exit(1)

        # Create tables (same DDL as schema.sql, no suffixes)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id              VARCHAR(64)     NOT NULL PRIMARY KEY,
                name            VARCHAR(256)    NOT NULL,
                email           VARCHAR(256)    NOT NULL,
                subject         VARCHAR(64)     NOT NULL,
                userName        VARCHAR(256)    NOT NULL,
                region          VARCHAR(128)    NOT NULL,
                userPoolId      VARCHAR(128)    NOT NULL,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS domains (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                domain_name     VARCHAR(32)     NOT NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                closed          TINYINT         NOT NULL DEFAULT 0,
                sort_order      SMALLINT        NULL,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS areas (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                area_name       VARCHAR(32)     NOT NULL,
                domain_fk       INT             NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                closed          TINYINT         NOT NULL DEFAULT 0,
                sort_order      SMALLINT        NULL,
                sort_mode       VARCHAR(8)      NOT NULL DEFAULT 'priority',
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (domain_fk)
                    REFERENCES domains (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                priority        BOOLEAN         NOT NULL,
                done            BOOLEAN         NOT NULL,
                description     VARCHAR(1024)   NOT NULL,
                area_fk         INT             NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                done_ts         TIMESTAMP       NULL,
                sort_order      SMALLINT        NULL,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (area_fk)
                    REFERENCES areas (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        print("Tables created: profiles, domains, areas, tasks")


def grant_claude_ro(conn):
    """Grant SELECT on darwin_dev to claude_ro user."""
    with conn.cursor() as cur:
        cur.execute(f"GRANT SELECT ON {TARGET_DATABASE}.* TO 'claude_ro'@'%'")
        cur.execute("FLUSH PRIVILEGES")
        print("Granted SELECT on darwin_dev.* to claude_ro.")


def seed_e2e_user(conn):
    """Seed the E2E test user profile (INSERT IGNORE for idempotency)."""
    with conn.cursor() as cur:
        cur.execute(f"USE {TARGET_DATABASE}")
        p = E2E_TEST_PROFILE
        cur.execute(
            "INSERT IGNORE INTO profiles (id, name, email, subject, userName, region, userPoolId) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (p['id'], p['name'], p['email'], p['subject'], p['userName'], p['region'], p['userPoolId']),
        )
        if cur.rowcount:
            print(f"Seeded E2E test user: {p['id']}")
        else:
            print(f"E2E test user already exists: {p['id']}")

        # Also seed the user's "Personal" domain (what Cognito trigger creates)
        cur.execute(
            "INSERT IGNORE INTO domains (domain_name, creator_fk, closed) "
            "VALUES ('Personal', %s, 0)",
            (p['id'],),
        )
        if cur.rowcount:
            print("Seeded 'Personal' domain for E2E test user.")


def main():
    for var in ('endpoint', 'username', 'db_password'):
        if var not in os.environ:
            print(f"Error: {var} environment variable not set.")
            print("Run: . exports.sh  (from Lambda-Rest/ directory)")
            sys.exit(1)

    conn = get_admin_connection()
    try:
        create_database(conn)
        create_tables(conn)
        grant_claude_ro(conn)
        seed_e2e_user(conn)
        print(f"\ndarwin_dev setup complete.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
