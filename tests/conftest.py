"""
DarwinSQL pytest shared fixtures.

All tests use darwin_dev test database. Never touches darwin production.
Constraint/integrity tests use existing darwin_dev tables (profiles, domains, areas, tasks).
Migration tests create temp tables with unique prefix, then DROP them.
"""
import os
import uuid

import pymysql
import pytest


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_connection():
    """Direct pymysql connection to darwin_dev test database."""
    conn = pymysql.connect(
        host=os.environ['endpoint'],
        user=os.environ['username'],
        password=os.environ['db_password'],
        database='darwin_dev',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Test data isolation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_creator_fk():
    """Unique creator_fk for schema test data isolation."""
    return f"schema-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session", autouse=True)
def seed_test_profile(db_connection, test_creator_fk):
    """Create a test profile so FK constraints can be satisfied.

    Also creates a domain and area for child-record tests.
    Cleans up everything after session.
    """
    ids = {}
    with db_connection.cursor() as cur:
        # Profile
        cur.execute(
            "INSERT INTO profiles (id, name, email, subject, userName, region, userPoolId) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (test_creator_fk, 'Schema Test', 'schema@test.com',
             test_creator_fk, test_creator_fk, 'us-west-1', 'test-pool'),
        )
        # Domain
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Schema Test Domain', test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        ids['domain_id'] = cur.fetchone()['id']

        # Area
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed, sort_order) "
            "VALUES (%s, %s, %s, 0, 1)",
            ('Schema Test Area', ids['domain_id'], test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        ids['area_id'] = cur.fetchone()['id']

    db_connection.commit()

    yield ids

    # Cleanup
    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM areas WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM domains WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM profiles WHERE id = %s", (test_creator_fk,))
    db_connection.commit()


# ---------------------------------------------------------------------------
# Migration test helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def migration_prefix():
    """Unique table prefix for module-scoped migration tests."""
    return f"mig_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="function")
def migration_test_prefix():
    """Unique table prefix for function-scoped migration tests."""
    return f"mig_{uuid.uuid4().hex[:6]}"
