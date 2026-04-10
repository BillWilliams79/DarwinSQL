#!/usr/bin/env python3
"""
Create and seed the darwin_dev test database.

Creates the darwin_dev database with production-identical table names,
grants read-only access to claude_ro, and seeds the E2E test user profile
plus 8 parallel E2E worker profiles.

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
}

# Parallel E2E worker profiles — one per dev server port (3000-3007)
E2E_WORKERS = [
    {'id': '0807ca6e-2f48-45b0-a9c4-15177859735b', 'name': 'E2E Worker 1', 'email': 'e2e-worker-1@test.invalid'},
    {'id': 'c0479250-4db9-4586-ad2f-5662deafdcd9', 'name': 'E2E Worker 2', 'email': 'e2e-worker-2@test.invalid'},
    {'id': 'de2018a8-964e-437d-8191-ca5b6f9cb8ac', 'name': 'E2E Worker 3', 'email': 'e2e-worker-3@test.invalid'},
    {'id': '3e2a706e-9f79-4a74-9ca5-f783296b6f33', 'name': 'E2E Worker 4', 'email': 'e2e-worker-4@test.invalid'},
    {'id': '2766f048-530d-40dd-8066-d8daf96ef0d9', 'name': 'E2E Worker 5', 'email': 'e2e-worker-5@test.invalid'},
    {'id': '0e724beb-3a62-422f-923b-57633bfafc7f', 'name': 'E2E Worker 6', 'email': 'e2e-worker-6@test.invalid'},
    {'id': 'cc5a9202-e1f0-4973-aa88-0caaba7a7140', 'name': 'E2E Worker 7', 'email': 'e2e-worker-7@test.invalid'},
    {'id': '3857b0d2-1b9b-4f64-8660-6a5b8db29c33', 'name': 'E2E Worker 8', 'email': 'e2e-worker-8@test.invalid'},
]


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
                timezone        VARCHAR(64)     NULL,
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

        # Roadmap / requirement tracking tables

        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                project_name    VARCHAR(128)    NOT NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                sort_order      SMALLINT        NULL,
                closed          TINYINT(1)      NOT NULL DEFAULT 0,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                category_name   VARCHAR(128)    NOT NULL,
                project_fk      INT             NOT NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                sort_order      SMALLINT        NULL,
                sort_mode       VARCHAR(8)      NOT NULL DEFAULT 'priority',
                closed          TINYINT(1)      NOT NULL DEFAULT 0,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_fk)
                    REFERENCES projects (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS requirements (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                title           VARCHAR(256)    NOT NULL,
                description     TEXT            NULL,
                in_progress     TINYINT(1)      NOT NULL DEFAULT 0,
                closed          TINYINT(1)      NOT NULL DEFAULT 0,
                started_at      TIMESTAMP       NULL,
                completed_at    TIMESTAMP       NULL,
                project_fk      INT             NULL,
                category_fk     INT             NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                sort_order      SMALLINT        NULL,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                scheduled       TINYINT         NOT NULL DEFAULT 0,
                FOREIGN KEY (project_fk)
                    REFERENCES projects (id)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                FOREIGN KEY (category_fk)
                    REFERENCES categories (id)
                    ON UPDATE CASCADE ON DELETE SET NULL,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        # Swarm session management

        cur.execute("""
            CREATE TABLE IF NOT EXISTS swarm_sessions (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                branch          VARCHAR(128)    NULL,
                task_name       VARCHAR(128)    NULL,
                source_type     VARCHAR(16)     NULL,
                source_ref      VARCHAR(64)     NULL,
                title           VARCHAR(256)    NULL,
                pr_url          VARCHAR(512)    NULL,
                swarm_status    VARCHAR(16)     NOT NULL DEFAULT 'starting',
                worktree_path   VARCHAR(512)    NULL,
                started_at      TIMESTAMP       NULL,
                completed_at    TIMESTAMP       NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS requirement_sessions (
                requirement_fk  INT             NOT NULL,
                session_fk      INT             NOT NULL,
                PRIMARY KEY (requirement_fk, session_fk),
                FOREIGN KEY (requirement_fk)
                    REFERENCES requirements (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (session_fk)
                    REFERENCES swarm_sessions (id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)

        # Dev server port coordination

        cur.execute("""
            CREATE TABLE IF NOT EXISTS dev_servers (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                port            SMALLINT        NOT NULL,
                pid             INT             NOT NULL,
                workspace_path  VARCHAR(512)    NOT NULL,
                session_fk      INT             NULL,
                creator_fk      VARCHAR(64)     NOT NULL,
                started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
                create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
                update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_port (port),
                FOREIGN KEY (creator_fk)
                    REFERENCES profiles (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (session_fk)
                    REFERENCES swarm_sessions (id)
                    ON UPDATE CASCADE ON DELETE SET NULL
            )
        """)

        # Priority card hand-sort order

        cur.execute("""
            CREATE TABLE IF NOT EXISTS priority_card_order (
                id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
                domain_id       INT             NOT NULL,
                task_id         INT             NOT NULL,
                sort_order      SMALLINT        NOT NULL,
                UNIQUE KEY uq_domain_task (domain_id, task_id)
            )
        """)

        print("Tables created: profiles, domains, areas, tasks, projects, categories, "
              "requirements, swarm_sessions, requirement_sessions, dev_servers, priority_card_order")


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
            "INSERT IGNORE INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (p['id'], p['name'], p['email']),
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

    # Seed worker profiles
    seeded = 0
    with conn.cursor() as cur:
        cur.execute(f"USE {TARGET_DATABASE}")
        for w in E2E_WORKERS:
            cur.execute(
                "INSERT IGNORE INTO profiles (id, name, email) "
                "VALUES (%s, %s, %s)",
                (w['id'], w['name'], w['email']),
            )
            if cur.rowcount:
                seeded += 1
            cur.execute(
                "INSERT IGNORE INTO domains (domain_name, creator_fk, closed) "
                "VALUES ('Personal', %s, 0)",
                (w['id'],),
            )
        print(f"E2E workers: {seeded} new, {len(E2E_WORKERS) - seeded} already existed.")


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
