"""
Cross-table referential integrity tests.

Verifies FK relationships work correctly across the full hierarchy:
profiles2 → domains2 → areas2 → tasks2.

All tests use darwin2. Rollback after each test.
"""
import pymysql
import pytest


# ---------------------------------------------------------------------------
# FK relationship verification
# ---------------------------------------------------------------------------

def test_task_references_valid_area(db_connection, test_creator_fk, seed_test_profile):
    """Task with valid area_fk succeeds and can be joined back."""
    area_id = seed_test_profile['area_id']
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'cross-table test task', area_id, test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        # Join task → area → domain → verify chain
        cur.execute(
            "SELECT t.description, a.area_name, d.domain_name "
            "FROM tasks2 t "
            "JOIN areas2 a ON t.area_fk = a.id "
            "JOIN domains2 d ON a.domain_fk = d.id "
            "WHERE t.id = %s",
            (task_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row['description'] == 'cross-table test task'
        assert row['area_name'] is not None
        assert row['domain_name'] is not None
    db_connection.rollback()


def test_area_references_valid_domain(db_connection, test_creator_fk, seed_test_profile):
    """Area with valid domain_fk can be joined to domain."""
    domain_id = seed_test_profile['domain_id']
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas2 (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('cross-table area', domain_id, test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute(
            "SELECT a.area_name, d.domain_name "
            "FROM areas2 a JOIN domains2 d ON a.domain_fk = d.id "
            "WHERE a.id = %s",
            (area_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row['area_name'] == 'cross-table area'
    db_connection.rollback()


def test_domain_references_valid_profile(db_connection, test_creator_fk, seed_test_profile):
    """Domain with valid creator_fk can be joined to profile."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains2 (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('cross-table domain', test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        cur.execute(
            "SELECT d.domain_name, p.name "
            "FROM domains2 d JOIN profiles2 p ON d.creator_fk = p.id "
            "WHERE d.id = %s",
            (domain_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row['domain_name'] == 'cross-table domain'
        assert row['name'] == 'Schema Test'
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------

def test_no_orphan_areas_for_test_data(db_connection, test_creator_fk, seed_test_profile):
    """All areas for our test creator have valid domain_fk (or NULL)."""
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.area_name, a.domain_fk "
            "FROM areas2 a "
            "WHERE a.creator_fk = %s AND a.domain_fk IS NOT NULL "
            "AND a.domain_fk NOT IN (SELECT id FROM domains2)",
            (test_creator_fk,),
        )
        orphans = cur.fetchall()
        assert len(orphans) == 0, f"Orphan areas found: {orphans}"


def test_no_orphan_tasks_for_test_data(db_connection, test_creator_fk, seed_test_profile):
    """All tasks for our test creator have valid area_fk (or NULL)."""
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT t.id, t.description, t.area_fk "
            "FROM tasks2 t "
            "WHERE t.creator_fk = %s AND t.area_fk IS NOT NULL "
            "AND t.area_fk NOT IN (SELECT id FROM areas2)",
            (test_creator_fk,),
        )
        orphans = cur.fetchall()
        assert len(orphans) == 0, f"Orphan tasks found: {orphans}"


# ---------------------------------------------------------------------------
# Creator scoping
# ---------------------------------------------------------------------------

def test_creator_fk_scopes_data(db_connection, test_creator_fk, seed_test_profile):
    """All records for our creator_fk are properly scoped — no cross-user data."""
    with db_connection.cursor() as cur:
        # Domains belong to our creator
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM domains2 WHERE creator_fk = %s",
            (test_creator_fk,),
        )
        domain_count = cur.fetchone()['cnt']
        assert domain_count >= 1

        # Areas belong to our creator
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM areas2 WHERE creator_fk = %s",
            (test_creator_fk,),
        )
        area_count = cur.fetchone()['cnt']
        assert area_count >= 1

        # All areas' domains belong to our creator too
        cur.execute(
            "SELECT a.id FROM areas2 a "
            "JOIN domains2 d ON a.domain_fk = d.id "
            "WHERE a.creator_fk = %s AND d.creator_fk != %s",
            (test_creator_fk, test_creator_fk),
        )
        mismatched = cur.fetchall()
        assert len(mismatched) == 0, f"Areas referencing other creators' domains: {mismatched}"


# ---------------------------------------------------------------------------
# Timestamp auto-population
# ---------------------------------------------------------------------------

def test_create_ts_auto_populated(db_connection, test_creator_fk, seed_test_profile):
    """create_ts is automatically set on INSERT."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains2 (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('timestamp test domain', test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        cur.execute("SELECT create_ts FROM domains2 WHERE id = %s", (domain_id,))
        row = cur.fetchone()
        assert row['create_ts'] is not None
    db_connection.rollback()


def test_update_ts_auto_populated_on_update(db_connection, test_creator_fk, seed_test_profile):
    """update_ts is automatically set on UPDATE."""
    domain_id = seed_test_profile['domain_id']
    with db_connection.cursor() as cur:
        # Initial update_ts may be NULL
        cur.execute(
            "UPDATE domains2 SET domain_name = %s WHERE id = %s",
            ('updated for ts test', domain_id),
        )
        cur.execute("SELECT update_ts FROM domains2 WHERE id = %s", (domain_id,))
        row = cur.fetchone()
        assert row['update_ts'] is not None
    db_connection.rollback()
