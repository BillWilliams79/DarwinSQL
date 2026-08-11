"""
Test FK constraints, NOT NULL constraints, unique constraints, and defaults.

Tests verify that database constraints prevent invalid data entry.
Each test uses transactions with rollback to keep darwin_dev test DB clean.
"""
import uuid

import pymysql
import pytest


# ---------------------------------------------------------------------------
# Foreign Key Constraint Tests
# ---------------------------------------------------------------------------

def test_task_fk_invalid_area(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with non-existent area_fk → pymysql.IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, 0, 'orphan task', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_area_fk_invalid_domain(db_connection, test_creator_fk):
    """INSERT area with non-existent domain_fk → pymysql.IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                ('orphan area', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_domain_fk_invalid_profile(db_connection):
    """INSERT domain with non-existent creator_fk → pymysql.IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO domains (domain_name, creator_fk, closed) "
                "VALUES (%s, %s, 0)",
                ('orphan domain', 'nonexistent-profile-id')
            )
    db_connection.rollback()


# ---------------------------------------------------------------------------
# NOT NULL Constraint Tests
# ---------------------------------------------------------------------------

def test_domain_name_not_null(db_connection, test_creator_fk):
    """INSERT domain with domain_name=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO domains (domain_name, creator_fk, closed) "
                "VALUES (%s, %s, 0)",
                (None, test_creator_fk)
            )
    db_connection.rollback()


def test_area_name_not_null(db_connection, test_creator_fk):
    """INSERT area with area_name=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                (None, None, test_creator_fk)
            )
    db_connection.rollback()


def test_task_description_not_null(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with description=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, 0, None, seed_test_profile['area_id'], test_creator_fk)
            )
    db_connection.rollback()


def test_task_priority_not_null(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with priority=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (None, 0, 'test task', seed_test_profile['area_id'], test_creator_fk)
            )
    db_connection.rollback()


def test_task_done_not_null(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with done=NULL explicitly → error.

    Note: omitting `done` from INSERT uses MySQL's implicit default (0) for
    BOOLEAN NOT NULL, which succeeds. Only explicit NULL violates the constraint.
    """
    with db_connection.cursor() as cur:
        with pytest.raises((pymysql.IntegrityError, pymysql.OperationalError)):
            cur.execute(
                "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, None, 'test task', seed_test_profile['area_id'], test_creator_fk)
            )
    db_connection.rollback()


def test_profile_name_not_null(db_connection):
    """INSERT profile with name=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO profiles (id, name, email) "
                "VALUES (%s, %s, %s)",
                ('test-profile-id', None, 'test@test.com')
            )
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Default Value Tests
# ---------------------------------------------------------------------------

def test_domain_closed_default(db_connection, test_creator_fk):
    """INSERT domain without specifying closed → closed defaults to 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk) "
            "VALUES (%s, %s)",
            ('test domain default', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        cur.execute("SELECT closed FROM domains WHERE id = %s", (domain_id,))
        row = cur.fetchone()
        assert row['closed'] == 0

    db_connection.rollback()


def test_area_closed_default(db_connection, test_creator_fk):
    """INSERT area without specifying closed → closed defaults to 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('test area default', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT closed FROM areas WHERE id = %s", (area_id,))
        row = cur.fetchone()
        assert row['closed'] == 0

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Nullable Column Tests
# ---------------------------------------------------------------------------

def test_area_sort_order_nullable(db_connection, test_creator_fk):
    """INSERT area with sort_order=NULL → succeeds"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed, sort_order) "
            "VALUES (%s, %s, %s, 0, %s)",
            ('test area nullable', None, test_creator_fk, None)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT sort_order FROM areas WHERE id = %s", (area_id,))
        row = cur.fetchone()
        assert row['sort_order'] is None

    db_connection.rollback()


def test_task_sort_order_nullable(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with sort_order=NULL → succeeds"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk, sort_order) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (0, 0, 'test task nullable', seed_test_profile['area_id'], test_creator_fk, None)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT sort_order FROM tasks WHERE id = %s", (task_id,))
        row = cur.fetchone()
        assert row['sort_order'] is None

    db_connection.rollback()


def test_task_done_ts_nullable(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task without done_ts → NULL stored"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'test task done_ts', seed_test_profile['area_id'], test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT done_ts FROM tasks WHERE id = %s", (task_id,))
        row = cur.fetchone()
        assert row['done_ts'] is None

    db_connection.rollback()


def test_area_domain_fk_nullable(db_connection, test_creator_fk):
    """INSERT area with domain_fk=NULL → succeeds (nullable FK)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('test area no domain', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT domain_fk FROM areas WHERE id = %s", (area_id,))
        row = cur.fetchone()
        assert row['domain_fk'] is None

    db_connection.rollback()


def test_task_area_fk_nullable(db_connection, test_creator_fk):
    """INSERT task with area_fk=NULL → succeeds (nullable FK)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'test task no area', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT area_fk FROM tasks WHERE id = %s", (task_id,))
        row = cur.fetchone()
        assert row['area_fk'] is None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Auto-Increment Tests
# ---------------------------------------------------------------------------

def test_domain_auto_increment(db_connection, test_creator_fk):
    """INSERT domain without specifying id → auto-increment generates id > 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) "
            "VALUES (%s, %s, 0)",
            ('test domain auto_inc', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']
        assert domain_id > 0

    db_connection.rollback()


def test_area_auto_increment(db_connection, test_creator_fk):
    """INSERT area without specifying id → auto-increment generates id > 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('test area auto_inc', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']
        assert area_id > 0

    db_connection.rollback()


def test_task_auto_increment(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task without specifying id → auto-increment generates id > 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'test task auto_inc', seed_test_profile['area_id'], test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']
        assert task_id > 0

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Unique/Primary Key Tests
# ---------------------------------------------------------------------------

def test_profile_pk_duplicate(db_connection):
    """INSERT profile with existing id → IntegrityError (PK violation)"""
    test_id = 'test-pk-duplicate-profile'
    with db_connection.cursor() as cur:
        # Insert first profile
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_id, 'Test Profile 1', 'test1@test.com')
        )

        # Attempt to insert duplicate
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO profiles (id, name, email) "
                "VALUES (%s, %s, %s)",
                (test_id, 'Test Profile 2', 'test2@test.com')
            )

    db_connection.rollback()


def test_domain_pk_auto_unique(db_connection, test_creator_fk):
    """INSERT multiple domains → each gets unique auto-increment id"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) "
            "VALUES (%s, %s, 0)",
            ('domain1', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        id1 = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) "
            "VALUES (%s, %s, 0)",
            ('domain2', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        id2 = cur.fetchone()['id']

        assert id1 != id2
        assert id1 > 0 and id2 > 0

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Roadmap table FK constraint tests
# ---------------------------------------------------------------------------

def test_project_fk_invalid_creator(db_connection):
    """INSERT project with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO projects (project_name, creator_fk) "
                "VALUES (%s, %s)",
                ('orphan project', 'nonexistent-profile-id')
            )
    db_connection.rollback()


def test_category_fk_invalid_project(db_connection, test_creator_fk):
    """INSERT category with non-existent project_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO categories (category_name, project_fk, creator_fk) "
                "VALUES (%s, %s, %s)",
                ('orphan category', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_requirement_fk_invalid_creator(db_connection, test_category_id):
    """INSERT requirement with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO requirements (title, creator_fk, category_fk) "
                "VALUES (%s, %s, %s)",
                ('orphan requirement', 'nonexistent-profile-id', test_category_id)
            )
    db_connection.rollback()


def test_requirement_session_fk_invalid_requirement(db_connection):
    """INSERT requirement_session with non-existent requirement_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO requirement_sessions (requirement_fk, session_fk) "
                "VALUES (%s, %s)",
                (999999, 999999)
            )
    db_connection.rollback()


def test_swarm_session_fk_invalid_creator(db_connection):
    """INSERT swarm_session with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO swarm_sessions (swarm_status, creator_fk) "
                "VALUES (%s, %s)",
                ('starting', 'nonexistent-profile-id')
            )
    db_connection.rollback()


def test_swarm_start_fk_invalid_creator(db_connection):
    """INSERT swarm_start with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO swarm_starts (creator_fk) VALUES (%s)",
                ('nonexistent-profile-id',)
            )
    db_connection.rollback()


def test_swarm_start_session_fk_invalid_swarm_start(db_connection):
    """INSERT swarm_start_session with non-existent swarm_start_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO swarm_start_sessions (swarm_start_fk, session_fk) "
                "VALUES (%s, %s)",
                (999999, 999999)
            )
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Roadmap table NOT NULL tests
# ---------------------------------------------------------------------------

def test_project_name_not_null(db_connection, test_creator_fk):
    """INSERT project with project_name=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO projects (project_name, creator_fk) "
                "VALUES (%s, %s)",
                (None, test_creator_fk)
            )
    db_connection.rollback()


def test_category_name_not_null(db_connection, test_creator_fk, seed_test_profile):
    """INSERT category with category_name=NULL → error"""
    with db_connection.cursor() as cur:
        # Create project first
        cur.execute(
            "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
            ('Test Project', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        project_id = cur.fetchone()['id']

        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO categories (category_name, project_fk, creator_fk) "
                "VALUES (%s, %s, %s)",
                (None, project_id, test_creator_fk)
            )
    db_connection.rollback()


def test_requirement_title_not_null(db_connection, test_creator_fk, test_category_id):
    """INSERT requirement with title=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO requirements (title, creator_fk, category_fk) "
                "VALUES (%s, %s, %s)",
                (None, test_creator_fk, test_category_id)
            )
    db_connection.rollback()


def test_requirement_category_fk_not_null(db_connection, test_creator_fk):
    """INSERT requirement without category_fk → pymysql.IntegrityError (req #2217)"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO requirements (title, creator_fk) "
                "VALUES (%s, %s)",
                ('no-category', test_creator_fk),
            )
    db_connection.rollback()


def test_swarm_status_not_null(db_connection, test_creator_fk):
    """INSERT swarm_session with swarm_status=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises((pymysql.IntegrityError, pymysql.OperationalError)):
            cur.execute(
                "INSERT INTO swarm_sessions (swarm_status, creator_fk) "
                "VALUES (%s, %s)",
                (None, test_creator_fk)
            )
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Roadmap table default value tests
# ---------------------------------------------------------------------------

def test_requirement_status_default(db_connection, test_creator_fk, test_category_id):
    """INSERT requirement without requirement_status → defaults to 'authoring' (migration 039)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO requirements (title, creator_fk, category_fk) VALUES (%s, %s, %s)",
            ('test requirement default', test_creator_fk, test_category_id)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        requirement_id = cur.fetchone()['id']

        cur.execute("SELECT requirement_status FROM requirements WHERE id = %s",
                    (requirement_id,))
        row = cur.fetchone()
        assert row['requirement_status'] == 'authoring'

    db_connection.rollback()


def test_swarm_status_default(db_connection, test_creator_fk):
    """INSERT swarm_session without status → defaults to 'starting'"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO swarm_sessions (creator_fk) VALUES (%s)",
            (test_creator_fk,)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        session_id = cur.fetchone()['id']

        cur.execute("SELECT swarm_status FROM swarm_sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        assert row['swarm_status'] == 'starting'

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Map table FK constraint tests
# ---------------------------------------------------------------------------

def test_map_route_fk_invalid_creator(db_connection):
    """INSERT map_route with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO map_routes (route_id, name, creator_fk) "
                "VALUES (%s, %s, %s)",
                (1, 'Test Route', 'nonexistent-profile-id')
            )
    db_connection.rollback()


def test_map_run_fk_invalid_creator(db_connection):
    """INSERT map_run with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO map_runs (run_id, activity_id, activity_name, start_time, "
                "run_time_sec, distance_mi, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (1, 4, 'Ride', '2025-01-01 00:00:00', 3600, 10.0, 'nonexistent-profile-id')
            )
    db_connection.rollback()


def test_map_run_fk_invalid_route(db_connection, test_creator_fk):
    """INSERT map_run with non-existent map_route_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO map_runs (run_id, map_route_fk, activity_id, activity_name, "
                "start_time, run_time_sec, distance_mi, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (1, 999999, 4, 'Ride', '2025-01-01 00:00:00', 3600, 10.0, test_creator_fk)
            )
    db_connection.rollback()


def test_map_coordinate_fk_invalid_run(db_connection):
    """INSERT map_coordinate with non-existent map_run_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO map_coordinates (map_run_fk, seq, latitude, longitude) "
                "VALUES (%s, %s, %s, %s)",
                (999999, 0, 37.7749295, -122.4194155)
            )
    db_connection.rollback()


def test_map_run_cascade_delete_coordinates(db_connection, test_creator_fk):
    """DELETE map_run → CASCADE deletes its coordinates"""
    with db_connection.cursor() as cur:
        # Create route
        cur.execute(
            "INSERT INTO map_routes (route_id, name, creator_fk) VALUES (%s, %s, %s)",
            (99, 'Cascade Test Route', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        route_id = cur.fetchone()['id']

        # Create run
        cur.execute(
            "INSERT INTO map_runs (run_id, map_route_fk, activity_id, activity_name, "
            "start_time, run_time_sec, distance_mi, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (99, route_id, 4, 'Ride', '2025-01-01 00:00:00', 3600, 10.0, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']

        # Create coordinates
        cur.execute(
            "INSERT INTO map_coordinates (map_run_fk, seq, latitude, longitude, altitude) "
            "VALUES (%s, %s, %s, %s, %s)",
            (run_id, 0, 37.7749295, -122.4194155, 10.0)
        )
        cur.execute(
            "INSERT INTO map_coordinates (map_run_fk, seq, latitude, longitude, altitude) "
            "VALUES (%s, %s, %s, %s, %s)",
            (run_id, 1, 37.7750000, -122.4195000, 11.0)
        )

        # Verify coordinates exist
        cur.execute("SELECT COUNT(*) AS cnt FROM map_coordinates WHERE map_run_fk = %s", (run_id,))
        assert cur.fetchone()['cnt'] == 2

        # Delete run → should cascade
        cur.execute("DELETE FROM map_runs WHERE id = %s", (run_id,))

        # Verify coordinates are gone
        cur.execute("SELECT COUNT(*) AS cnt FROM map_coordinates WHERE map_run_fk = %s", (run_id,))
        assert cur.fetchone()['cnt'] == 0

    db_connection.rollback()


def test_map_route_delete_sets_run_fk_null(db_connection, test_creator_fk):
    """DELETE map_route → ON DELETE SET NULL on map_runs.map_route_fk"""
    with db_connection.cursor() as cur:
        # Create route
        cur.execute(
            "INSERT INTO map_routes (route_id, name, creator_fk) VALUES (%s, %s, %s)",
            (98, 'SetNull Test Route', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        route_id = cur.fetchone()['id']

        # Create run linked to route
        cur.execute(
            "INSERT INTO map_runs (run_id, map_route_fk, activity_id, activity_name, "
            "start_time, run_time_sec, distance_mi, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (98, route_id, 4, 'Ride', '2025-01-01 00:00:00', 3600, 10.0, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']

        # Delete route → should SET NULL on run's map_route_fk
        cur.execute("DELETE FROM map_routes WHERE id = %s", (route_id,))

        # Verify run still exists but map_route_fk is NULL
        cur.execute("SELECT map_route_fk FROM map_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
        assert row is not None
        assert row['map_route_fk'] is None

    db_connection.rollback()


def test_map_routes_unique_creator_route(db_connection, test_creator_fk):
    """INSERT duplicate (creator_fk, route_id) into map_routes → IntegrityError"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO map_routes (route_id, name, creator_fk) VALUES (%s, %s, %s)",
            (500, 'Unique Test Route', test_creator_fk)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO map_routes (route_id, name, creator_fk) VALUES (%s, %s, %s)",
                (500, 'Duplicate Route', test_creator_fk)
            )
    db_connection.rollback()


def test_map_runs_unique_creator_run(db_connection, test_creator_fk):
    """INSERT duplicate (creator_fk, run_id) into map_runs → IntegrityError"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO map_runs (run_id, activity_id, activity_name, start_time, "
            "run_time_sec, distance_mi, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (500, 4, 'Ride', '2025-06-01 10:00:00', 3600, 10.0, test_creator_fk)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO map_runs (run_id, activity_id, activity_name, start_time, "
                "run_time_sec, distance_mi, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (500, 4, 'Ride', '2025-06-02 10:00:00', 1800, 5.0, test_creator_fk)
            )
    db_connection.rollback()


def test_map_run_stopped_time_default(db_connection, test_creator_fk):
    """INSERT map_run without stopped_time_sec → defaults to 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO map_runs (run_id, activity_id, activity_name, "
            "start_time, run_time_sec, distance_mi, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (97, 4, 'Ride', '2025-01-01 00:00:00', 3600, 10.0, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']

        cur.execute("SELECT stopped_time_sec FROM map_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
        assert row['stopped_time_sec'] == 0

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Req #2380 — Swarm Features & Test Cases registry (migrations 042/043/044)
# `features` was dropped at req #3355 (migration 20260811033413); its FK/NOT
# NULL/default coverage went with it.
# ---------------------------------------------------------------------------

# FK invalid-parent rejection tests

def test_test_case_fk_invalid_category(db_connection, test_creator_fk, seed_test_profile):
    """INSERT test_case with non-existent category_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                ('orphan case', '1. step', 'passes', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_test_plan_fk_invalid_category(db_connection, test_creator_fk, seed_test_profile):
    """INSERT test_plan with non-existent category_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_plans (title, category_fk, creator_fk) "
                "VALUES (%s, %s, %s)",
                ('orphan plan', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_test_run_fk_invalid_plan(db_connection, test_creator_fk, seed_test_profile):
    """INSERT test_run with non-existent test_plan_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_runs (test_plan_fk, run_status, creator_fk) "
                "VALUES (%s, %s, %s)",
                (999999, 'in_progress', test_creator_fk)
            )
    db_connection.rollback()


def test_test_result_fk_invalid_run(db_connection, test_creator_fk, seed_test_profile):
    """INSERT test_result with non-existent test_run_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_results "
                "(test_run_fk, test_case_fk, result_status, creator_fk) "
                "VALUES (%s, %s, %s, %s)",
                (999999, 999999, 'passed', test_creator_fk)
            )
    db_connection.rollback()


# NOT NULL constraint tests

def test_test_case_steps_not_null(db_connection, test_creator_fk, test_category_id):
    """INSERT test_case with steps=NULL → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                ('t', None, 'e', test_category_id, test_creator_fk)
            )
    db_connection.rollback()


def test_test_case_expected_not_null(db_connection, test_creator_fk, test_category_id):
    """INSERT test_case with expected=NULL → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                ('t', '1.step', None, test_category_id, test_creator_fk)
            )
    db_connection.rollback()


# Default value tests

def test_test_case_type_default(db_connection, test_creator_fk, test_category_id):
    """INSERT test_case without test_type → defaults to 'manual'."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('type-default', '1.step', 'pass', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        tc_id = cur.fetchone()['id']
        cur.execute("SELECT test_type FROM test_cases WHERE id = %s", (tc_id,))
        assert cur.fetchone()['test_type'] == 'manual'
    db_connection.rollback()


def test_test_run_status_default(db_connection, test_creator_fk, test_category_id):
    """INSERT test_run without run_status → defaults to 'in_progress'."""
    with db_connection.cursor() as cur:
        # Need a plan first
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan-for-run-default', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_runs (test_plan_fk, creator_fk) VALUES (%s, %s)",
            (plan_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']
        cur.execute("SELECT run_status, started_at FROM test_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
        assert row['run_status'] == 'in_progress'
        assert row['started_at'] is not None  # NOT NULL DEFAULT CURRENT_TIMESTAMP
    db_connection.rollback()


def test_test_result_status_default(db_connection, test_creator_fk, test_category_id):
    """INSERT test_result without result_status → defaults to 'not_run'."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan-for-result-default', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case-for-result', '1', 'ok', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_runs (test_plan_fk, creator_fk) VALUES (%s, %s)",
            (plan_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_results (test_run_fk, test_case_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            (run_id, case_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        result_id = cur.fetchone()['id']
        cur.execute("SELECT result_status, executed_at FROM test_results WHERE id = %s",
                    (result_id,))
        row = cur.fetchone()
        assert row['result_status'] == 'not_run'
        assert row['executed_at'] is None  # nullable, not set until result recorded
    db_connection.rollback()


# UNIQUE (test_run_fk, test_case_fk) enforcement

def test_test_results_unique_run_case(db_connection, test_creator_fk, test_category_id):
    """Second INSERT test_result with same (test_run_fk, test_case_fk) → IntegrityError.

    Enforces uq_run_case: a test_run has at most one test_result per test_case.
    """
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan-uq-check', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case-uq', '1', 'ok', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_runs (test_plan_fk, creator_fk) VALUES (%s, %s)",
            (plan_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO test_results (test_run_fk, test_case_fk, result_status, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            (run_id, case_id, 'passed', test_creator_fk)
        )
        # Second insert with same (run, case) must fail
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO test_results (test_run_fk, test_case_fk, result_status, creator_fk) "
                "VALUES (%s, %s, %s, %s)",
                (run_id, case_id, 'failed', test_creator_fk)
            )
    db_connection.rollback()


# Junction-table composite PK uniqueness

# COVERS: SCH-031
def test_requirement_test_cases_composite_pk(db_connection, test_creator_fk, test_category_id):
    """req #3352 — Second INSERT requirement_test_cases with same
    (requirement_fk, test_case_fk) → IntegrityError (the successor of the
    now-dropped feature_test_cases junction, req #3355)."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO requirements (title, category_fk, creator_fk, "
            "requirement_status, coordination_type, ai_model, effort) "
            "VALUES (%s, %s, %s, 'authoring', 'implemented', 'opus', 'high')",
            ('r-dup', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        r_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('tc-dup2', '1', 'ok', test_category_id, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        tc_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO requirement_test_cases (requirement_fk, test_case_fk) VALUES (%s, %s)",
            (r_id, tc_id)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO requirement_test_cases (requirement_fk, test_case_fk) VALUES (%s, %s)",
                (r_id, tc_id)
            )
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Req #2943 — machines registry constraints
# ---------------------------------------------------------------------------

def _insert_machine(cur, creator_fk, hostname, title=None, platform='darwin',
                    arch='arm64'):
    """Insert a machines row and return its id. All-NOT-NULL fields supplied."""
    cur.execute(
        "INSERT INTO machines (title, hostname, platform, arch, creator_fk) "
        "VALUES (%s, %s, %s, %s, %s)",
        (title or hostname, hostname, platform, arch, creator_fk),
    )
    cur.execute("SELECT LAST_INSERT_ID() AS id")
    return cur.fetchone()['id']


def test_machines_hostname_unique(db_connection, test_creator_fk):
    """uq_machines_hostname: a second machine with the same hostname → IntegrityError.

    hostname is the auto-registration match key; duplicates must be rejected so
    machine-identity.sh can rely on it to repair a wiped cache without creating a
    duplicate row."""
    with db_connection.cursor() as cur:
        _insert_machine(cur, test_creator_fk, 'dup-host.local')
        with pytest.raises(pymysql.IntegrityError):
            _insert_machine(cur, test_creator_fk, 'dup-host.local', title='other')
    db_connection.rollback()


def test_machine_fk_restrict_swarm_sessions(db_connection, test_creator_fk):
    """swarm_sessions.machine_fk is ON DELETE RESTRICT: deleting a machine that a
    session references must fail (retire via `closed`, don't hard-delete)."""
    with db_connection.cursor() as cur:
        mid = _insert_machine(cur, test_creator_fk, 'restrict-sess.local')
        cur.execute(
            "INSERT INTO swarm_sessions (task_name, swarm_status, machine_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            ('m-restrict-sess', 'active', mid, test_creator_fk),
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM machines WHERE id = %s", (mid,))
    db_connection.rollback()


def test_machine_fk_restrict_swarm_starts(db_connection, test_creator_fk):
    """swarm_starts.machine_fk is ON DELETE RESTRICT."""
    with db_connection.cursor() as cur:
        mid = _insert_machine(cur, test_creator_fk, 'restrict-start.local')
        cur.execute(
            "INSERT INTO swarm_starts (arguments, machine_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('m-restrict-start', mid, test_creator_fk),
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM machines WHERE id = %s", (mid,))
    db_connection.rollback()


def test_machine_fk_restrict_dev_servers(db_connection, test_creator_fk):
    """dev_servers.machine_fk is ON DELETE RESTRICT."""
    with db_connection.cursor() as cur:
        mid = _insert_machine(cur, test_creator_fk, 'restrict-dev.local')
        cur.execute(
            "INSERT INTO dev_servers (port, pid, workspace_path, machine_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (3000, 111, '/tmp/ws', mid, test_creator_fk),
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM machines WHERE id = %s", (mid,))
    db_connection.rollback()


def test_machine_fk_restrict_requirements(db_connection, test_creator_fk, test_category_id):
    """requirements.machine_fk is ON DELETE RESTRICT (req #2978, migration 066).

    A machine PINNED BY a requirement cannot be hard-deleted — retire it via
    closed=1 instead. This is the fourth referencing table alongside the three
    execution tables from req #2943, and the MCP delete_machine guard message
    names it.
    """
    with db_connection.cursor() as cur:
        mid = _insert_machine(cur, test_creator_fk, 'restrict-req.local')
        cur.execute(
            "INSERT INTO requirements (title, machine_fk, creator_fk, category_fk) "
            "VALUES (%s, %s, %s, %s)",
            ('m-restrict-req', mid, test_creator_fk, test_category_id),
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM machines WHERE id = %s", (mid,))
    db_connection.rollback()


def test_requirement_machine_fk_defaults_null(db_connection, test_creator_fk, test_category_id):
    """A requirement created without machine_fk is NULL = "Any machine" (req #2978).

    This is what makes migration 066 backfill-free: every pre-existing and every
    newly-created requirement is "Any" unless explicitly pinned.
    """
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO requirements (title, creator_fk, category_fk) VALUES (%s, %s, %s)",
            ('m-default-any', test_creator_fk, test_category_id),
        )
        cur.execute("SELECT machine_fk FROM requirements WHERE id = LAST_INSERT_ID()")
        assert cur.fetchone()['machine_fk'] is None
    db_connection.rollback()


def test_requirement_machine_fk_invalid_reference(db_connection, test_creator_fk, test_category_id):
    """A requirement referencing a non-existent machine_fk → IntegrityError."""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO requirements (title, machine_fk, creator_fk, category_fk) "
                "VALUES (%s, %s, %s, %s)",
                ('m-req-bad-fk', 999999999, test_creator_fk, test_category_id),
            )
    db_connection.rollback()


def test_machine_fk_invalid_reference(db_connection, test_creator_fk):
    """A swarm_session referencing a non-existent machine_fk → IntegrityError."""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO swarm_sessions (task_name, swarm_status, machine_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s)",
                ('m-bad-fk', 'active', 999999999, test_creator_fk),
            )
    db_connection.rollback()


def test_dev_servers_uq_machine_port(db_connection, test_creator_fk):
    """uq_machine_port(machine_fk, port): the SAME port is allowed on two DIFFERENT
    machines (ports are machine-local — the whole point of req #2943), but a
    DUPLICATE port on the SAME machine is rejected."""
    with db_connection.cursor() as cur:
        m1 = _insert_machine(cur, test_creator_fk, 'port-a.local')
        m2 = _insert_machine(cur, test_creator_fk, 'port-b.local')
        # Port 3005 on machine 1.
        cur.execute(
            "INSERT INTO dev_servers (port, pid, workspace_path, machine_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (3005, 201, '/tmp/a', m1, test_creator_fk),
        )
        # SAME port 3005 on machine 2 → allowed (no false cross-machine contention).
        cur.execute(
            "INSERT INTO dev_servers (port, pid, workspace_path, machine_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (3005, 202, '/tmp/b', m2, test_creator_fk),
        )
        # DUPLICATE port 3005 on machine 1 → rejected.
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO dev_servers (port, pid, workspace_path, machine_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (3005, 203, '/tmp/c', m1, test_creator_fk),
            )
    db_connection.rollback()


def test_machines_creator_fk_cascade(db_connection):
    """machines.creator_fk is ON DELETE CASCADE — deleting the owning profile
    removes the machine (profile removal takes all owned data)."""
    cfk = f"schema-test-mach-{uuid.uuid4().hex[:8]}"
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO profiles (id, name, email) VALUES (%s, %s, %s)",
                    (cfk, 'Mach Cascade', 'mc@test.com'))
        _insert_machine(cur, cfk, 'cascade-host.local')
        cur.execute("DELETE FROM profiles WHERE id = %s", (cfk,))
        cur.execute("SELECT COUNT(*) AS c FROM machines WHERE creator_fk = %s", (cfk,))
        assert cur.fetchone()['c'] == 0
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Req #2997 — agents registry constraints
#
# The rule this requirement exists to enforce: AT MOST ONE 'owned' agent per
# architecture document. It is a DB constraint, not a convention — these tests
# are what prove that.
# ---------------------------------------------------------------------------

def _insert_agent(cur, creator_fk, name=None):
    """Insert an agents row and return its id."""
    name = name or f"Test Agent {uuid.uuid4().hex[:8]}"
    cur.execute(
        "INSERT INTO agents (name, file_name, creator_fk) VALUES (%s, %s, %s)",
        (name, f"{name.lower().replace(' ', '-')}.md", creator_fk),
    )
    return cur.lastrowid


def _insert_document(cur, creator_fk, name=None):
    """Insert an architecture_documents row and return its id."""
    name = name or f"Test Doc {uuid.uuid4().hex[:8]}"
    cur.execute(
        "INSERT INTO architecture_documents (name, doc_type, location, creator_fk) "
        "VALUES (%s, 'markdown', %s, %s)",
        (name, f"memory/{uuid.uuid4().hex[:8]}.md", creator_fk),
    )
    return cur.lastrowid


def test_agents_name_unique(db_connection, test_creator_fk):
    """uq_agents_name: `name` is the MCP lookup key — a duplicate would make
    darwin://agents/<name> ambiguous, so the DB forbids it."""
    with db_connection.cursor() as cur:
        _insert_agent(cur, test_creator_fk, 'Duplicate Name Architect')
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO agents (name, file_name, creator_fk) VALUES (%s, %s, %s)",
                ('Duplicate Name Architect', 'other-file.md', test_creator_fk),
            )
    db_connection.rollback()


def test_agents_file_name_unique(db_connection, test_creator_fk):
    """uq_agents_file_name: file_name is the fallback lookup key and must also
    resolve unambiguously."""
    with db_connection.cursor() as cur:
        _insert_agent(cur, test_creator_fk, 'File Name Architect')
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO agents (name, file_name, creator_fk) VALUES (%s, %s, %s)",
                ('Some Other Architect', 'file-name-architect.md', test_creator_fk),
            )
    db_connection.rollback()


def test_agents_model_effort_defaults(db_connection, test_creator_fk):
    """The standard header pin: an agent created without ai_model/effort lands on
    opus[1m] / high (req #2997), replacing the stale per-agent claude-opus-4-6
    pins the ownership survey found."""
    with db_connection.cursor() as cur:
        aid = _insert_agent(cur, test_creator_fk)
        cur.execute("SELECT ai_model, effort, closed FROM agents WHERE id = %s", (aid,))
        row = cur.fetchone()
        assert row['ai_model'] == 'opus[1m]'
        assert row['effort'] == 'high'
        assert row['closed'] == 0
    db_connection.rollback()


def test_agent_documents_single_owner_on_insert(db_connection, test_creator_fk):
    """uq_agent_documents_owner: a SECOND agent claiming 'owned' on the same
    document is rejected. This is the core ownership rule of req #2997."""
    with db_connection.cursor() as cur:
        a1 = _insert_agent(cur, test_creator_fk)
        a2 = _insert_agent(cur, test_creator_fk)
        doc = _insert_document(cur, test_creator_fk)

        cur.execute(
            "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
            "VALUES (%s, %s, 'owned')", (a1, doc))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
                "VALUES (%s, %s, 'owned')", (a2, doc))
    db_connection.rollback()


def test_agent_documents_single_owner_on_update(db_connection, test_creator_fk):
    """The ownership rule must not be bypassable by linking as 'curated' and then
    UPDATEing to 'owned' — the generated column is recomputed on update (via
    FIND_IN_SET), so the UNIQUE key catches this path too."""
    with db_connection.cursor() as cur:
        a1 = _insert_agent(cur, test_creator_fk)
        a2 = _insert_agent(cur, test_creator_fk)
        doc = _insert_document(cur, test_creator_fk)

        cur.execute(
            "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
            "VALUES (%s, %s, 'owned')", (a1, doc))
        cur.execute(
            "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
            "VALUES (%s, %s, 'curated')", (a2, doc))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "UPDATE agent_documents SET relationship = 'owned' "
                "WHERE agent_fk = %s AND document_fk = %s", (a2, doc))
    db_connection.rollback()


def test_agent_documents_multiple_non_owned_allowed(db_connection, test_creator_fk):
    """NULLs are distinct in a MySQL UNIQUE key, so any number of non-'owned'
    links may coexist on one document. Many architects may reference a document;
    only one may own it."""
    with db_connection.cursor() as cur:
        doc = _insert_document(cur, test_creator_fk)
        # Non-'owned' links, including a multi-role SET value — none set the
        # owned_document_fk virtual column, so all coexist on one document.
        for rel in ('curated', 'autoload', 'referenced', 'curated,autoload'):
            cur.execute(
                "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
                "VALUES (%s, %s, %s)", (_insert_agent(cur, test_creator_fk), doc, rel))
        cur.execute("SELECT COUNT(*) AS c FROM agent_documents WHERE document_fk = %s",
                    (doc,))
        assert cur.fetchone()['c'] == 4
    db_connection.rollback()


def test_agent_documents_ownership_transfer(db_connection, test_creator_fk):
    """Ownership is transferable: once the incumbent's link is removed, another
    agent may claim 'owned'. The constraint blocks CONCURRENT owners, not
    reassignment."""
    with db_connection.cursor() as cur:
        a1 = _insert_agent(cur, test_creator_fk)
        a2 = _insert_agent(cur, test_creator_fk)
        doc = _insert_document(cur, test_creator_fk)

        cur.execute(
            "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
            "VALUES (%s, %s, 'owned')", (a1, doc))
        cur.execute(
            "DELETE FROM agent_documents WHERE agent_fk = %s AND document_fk = %s",
            (a1, doc))
        cur.execute(
            "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
            "VALUES (%s, %s, 'owned')", (a2, doc))
        cur.execute(
            "SELECT agent_fk FROM agent_documents "
            "WHERE document_fk = %s AND relationship = 'owned'", (doc,))
        assert cur.fetchone()['agent_fk'] == a2
    db_connection.rollback()


def test_agent_documents_cascade_from_agent(db_connection, test_creator_fk):
    """Deleting an agent cascades its links away; the DOCUMENT row survives
    (documents are a shared catalog, not agent-private data)."""
    with db_connection.cursor() as cur:
        aid = _insert_agent(cur, test_creator_fk)
        doc = _insert_document(cur, test_creator_fk)
        cur.execute(
            "INSERT INTO agent_documents (agent_fk, document_fk, relationship) "
            "VALUES (%s, %s, 'owned')", (aid, doc))

        cur.execute("DELETE FROM agents WHERE id = %s", (aid,))
        cur.execute("SELECT COUNT(*) AS c FROM agent_documents WHERE agent_fk = %s",
                    (aid,))
        assert cur.fetchone()['c'] == 0
        cur.execute("SELECT COUNT(*) AS c FROM architecture_documents WHERE id = %s",
                    (doc,))
        assert cur.fetchone()['c'] == 1
    db_connection.rollback()


def test_agent_instructions_cascade_and_sharing(db_connection, test_creator_fk):
    """One instruction row may bind MANY agents — this is how the common curating
    duty reaches every architect. Deleting one agent must not disturb the others'
    bindings."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO instructions (name, content, creator_fk) VALUES (%s, %s, %s)",
            (f"shared-{uuid.uuid4().hex[:8]}", 'binding text', test_creator_fk))
        instr = cur.lastrowid
        a1 = _insert_agent(cur, test_creator_fk)
        a2 = _insert_agent(cur, test_creator_fk)
        for aid in (a1, a2):
            cur.execute(
                "INSERT INTO agent_instructions (agent_fk, instruction_fk, sort_order) "
                "VALUES (%s, %s, 1)", (aid, instr))

        cur.execute("DELETE FROM agents WHERE id = %s", (a1,))
        cur.execute("SELECT COUNT(*) AS c FROM agent_instructions WHERE instruction_fk = %s",
                    (instr,))
        assert cur.fetchone()['c'] == 1, "surviving agent's binding must remain"
        cur.execute("SELECT COUNT(*) AS c FROM instructions WHERE id = %s", (instr,))
        assert cur.fetchone()['c'] == 1, "shared instruction row must survive"
    db_connection.rollback()


def test_instructions_name_unique(db_connection, test_creator_fk):
    """uq_instructions_name: `name` is the idempotent-seed key, so the seeder can
    upsert rather than duplicate on every run."""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO instructions (name, content, creator_fk) VALUES (%s, %s, %s)",
            ('dup-instruction-name', 'a', test_creator_fk))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO instructions (name, content, creator_fk) VALUES (%s, %s, %s)",
                ('dup-instruction-name', 'b', test_creator_fk))
    db_connection.rollback()


def test_architecture_documents_name_unique(db_connection, test_creator_fk):
    """uq_architecture_documents_name: the document registry's upsert key."""
    with db_connection.cursor() as cur:
        _insert_document(cur, test_creator_fk, 'Duplicate Doc Name')
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO architecture_documents (name, doc_type, creator_fk) "
                "VALUES (%s, 'markdown', %s)", ('Duplicate Doc Name', test_creator_fk))
    db_connection.rollback()


def test_agents_creator_fk_cascade(db_connection):
    """agents.creator_fk is ON DELETE CASCADE — removing the owning profile takes
    its agents with it."""
    cfk = f"schema-test-agent-{uuid.uuid4().hex[:8]}"
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO profiles (id, name, email) VALUES (%s, %s, %s)",
                    (cfk, 'Agent Cascade', 'ac@test.com'))
        _insert_agent(cur, cfk)
        cur.execute("DELETE FROM profiles WHERE id = %s", (cfk,))
        cur.execute("SELECT COUNT(*) AS c FROM agents WHERE creator_fk = %s", (cfk,))
        assert cur.fetchone()['c'] == 0
    db_connection.rollback()


# ===========================================================================
# Req #3075 — agent_instructions per-agent load-slot uniqueness (migration 073)
# ===========================================================================
#
# `agent_instructions.sort_order` is the BOOT LOAD ORDER, and since migration 072
# it is the only instruction ordering left in the schema. Before migration 073
# nothing stopped two instructions from claiming the same slot on one agent — the
# composite PK (agent_fk, instruction_fk) is satisfied by both rows — so the agent
# booted with those two rules in arbitrary relative order, with no error and a
# payload that still looked well-formed. Production `darwin` was carrying exactly
# one such pair (agent 5, slot 1) when this key was added.


def _insert_instruction(cur, creator_fk, name=None):
    """Insert an instructions row and return its id."""
    name = name or f"Test Instruction {uuid.uuid4().hex[:8]}"
    cur.execute(
        "INSERT INTO instructions (name, content, creator_fk) VALUES (%s, %s, %s)",
        (name, 'binding text', creator_fk))
    return cur.lastrowid


def test_agent_instructions_duplicate_slot_rejected_on_insert(
        db_connection, test_creator_fk):
    """uq_agent_instructions_slot: THE guard. One agent, one numbered slot, one
    instruction. This is the insert path `nextInstructionSortOrder` feeds when two
    concurrent binds both compute max+1 from the same pre-write cache."""
    with db_connection.cursor() as cur:
        agent = _insert_agent(cur, test_creator_fk)
        first = _insert_instruction(cur, test_creator_fk)
        second = _insert_instruction(cur, test_creator_fk)

        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 1)", (agent, first))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                        "sort_order) VALUES (%s, %s, 1)", (agent, second))
    db_connection.rollback()


def test_agent_instructions_duplicate_slot_rejected_on_update(
        db_connection, test_creator_fk):
    """The guard must not be bypassable by inserting at a free slot and then
    UPDATEing onto an occupied one — the same shape as the agent_documents
    owner-key update test. This is the path a reorder takes when it moves a row
    onto a slot it did not first vacate."""
    with db_connection.cursor() as cur:
        agent = _insert_agent(cur, test_creator_fk)
        first = _insert_instruction(cur, test_creator_fk)
        second = _insert_instruction(cur, test_creator_fk)

        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 1)", (agent, first))
        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 2)", (agent, second))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("UPDATE agent_instructions SET sort_order = 1 "
                        "WHERE agent_fk = %s AND instruction_fk = %s",
                        (agent, second))
    db_connection.rollback()


def test_agent_instructions_slot_is_per_agent_not_global(
        db_connection, test_creator_fk):
    """agent_fk LEADS the key on purpose. Every agent has its own slot 1 — the
    banded scheme puts per-agent rules at 1..N on all of them — so a global
    UNIQUE(sort_order) would have been catastrophically wrong."""
    with db_connection.cursor() as cur:
        agent_a = _insert_agent(cur, test_creator_fk)
        agent_b = _insert_agent(cur, test_creator_fk)
        instruction = _insert_instruction(cur, test_creator_fk)

        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 1)", (agent_a, instruction))
        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 1)", (agent_b, instruction))

        cur.execute("SELECT COUNT(*) AS c FROM agent_instructions "
                    "WHERE instruction_fk = %s AND sort_order = 1", (instruction,))
        assert cur.fetchone()['c'] == 2
    db_connection.rollback()


def test_agent_instructions_multiple_null_slots_allowed(
        db_connection, test_creator_fk):
    """NULL claims NO slot, and MySQL UNIQUE treats NULLs as distinct — so one
    agent may hold any number of unordered links. That is the deliberate scope of
    the invariant, not a hole in it: forcing NOT NULL would invent a slot for a
    link that has none and would break link_agent_instruction's COALESCE contract
    (req #3049), where an omitted sort_order must leave the stored value alone.

    Unnumbered links stay deterministically ordered anyway: darwin-mcp sorts
    NULLs last then by id, and the Darwin UI's stable sort leaves them in the
    junction's clustered-PK order."""
    with db_connection.cursor() as cur:
        agent = _insert_agent(cur, test_creator_fk)
        first = _insert_instruction(cur, test_creator_fk)
        second = _insert_instruction(cur, test_creator_fk)
        third = _insert_instruction(cur, test_creator_fk)

        for instruction in (first, second, third):
            cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                        "sort_order) VALUES (%s, %s, NULL)", (agent, instruction))

        cur.execute("SELECT COUNT(*) AS c FROM agent_instructions "
                    "WHERE agent_fk = %s AND sort_order IS NULL", (agent,))
        assert cur.fetchone()['c'] == 3
    db_connection.rollback()


def test_agent_instructions_banded_sparse_slots_allowed(
        db_connection, test_creator_fk):
    """The live layout must remain legal: per-agent rules at 1..N, the shared
    `common-*` rows together at 100+, and the 4..99 gap kept free for extension.
    UNIQUE forbids duplicates, not sparseness — nothing here pushes toward a 1..N
    renumber, which is what `repairInstructionOrders` exists to avoid."""
    with db_connection.cursor() as cur:
        agent = _insert_agent(cur, test_creator_fk)
        for slot in (1, 2, 3, 100, 101, 102):
            instruction = _insert_instruction(cur, test_creator_fk)
            cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                        "sort_order) VALUES (%s, %s, %s)", (agent, instruction, slot))

        cur.execute("SELECT sort_order FROM agent_instructions "
                    "WHERE agent_fk = %s ORDER BY sort_order", (agent,))
        assert [r['sort_order'] for r in cur.fetchall()] == [1, 2, 3, 100, 101, 102]
    db_connection.rollback()


def test_agent_instructions_delete_then_repost_swap_is_legal(
        db_connection, test_creator_fk):
    """The reorder path, replayed exactly as the UI performs it.

    `setAgentInstructionOrder` DELETEs EVERY row in the write set and only then
    re-creates them all in one array-body POST — it never holds two rows of one
    agent at the same numbered slot, not even transiently. That sequencing is the
    reason a plain UNIQUE key is safe here, so it is pinned as a test rather than
    left as a claim in a comment."""
    with db_connection.cursor() as cur:
        agent = _insert_agent(cur, test_creator_fk)
        first = _insert_instruction(cur, test_creator_fk)
        second = _insert_instruction(cur, test_creator_fk)

        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 1), (%s, %s, 2)",
                    (agent, first, agent, second))

        # DELETE both, then re-POST both swapped — the real write sequence.
        cur.execute("DELETE FROM agent_instructions WHERE agent_fk = %s AND "
                    "instruction_fk IN (%s, %s)", (agent, first, second))
        cur.execute("INSERT INTO agent_instructions (agent_fk, instruction_fk, "
                    "sort_order) VALUES (%s, %s, 2), (%s, %s, 1)",
                    (agent, first, agent, second))

        cur.execute("SELECT instruction_fk, sort_order FROM agent_instructions "
                    "WHERE agent_fk = %s ORDER BY sort_order", (agent,))
        assert [(r['instruction_fk'], r['sort_order']) for r in cur.fetchall()] == \
            [(second, 1), (first, 2)]
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Req #3111 — Swarm Orchestration schema foundation (migration 076)
#
# Every new FK gets a behavioural test, because the FK policy here is where the
# design rules acquire teeth. Three policies are in play and they are NOT
# interchangeable:
#   RESTRICT  — the delete must FAIL (dep_step_fk, requirement_fk, category_fk,
#               machine_fk). This is design rule 4 enforced by the database:
#               a step something else gates on cannot be deleted or merged away,
#               and a requirement in a plan cannot be deleted.
#   CASCADE   — the delete must take the children (pipeline -> steps, step ->
#               its links and its own dep conditions).
#   SET NULL  — the delete must DEMOTE, not destroy (e.g. requirements.project_fk).
#               Deleting a parent must never take child history with it.
# ---------------------------------------------------------------------------

def _insert_epic(cur, creator_fk, category_fk, title=None):
    cur.execute(
        "INSERT INTO epics (title, description, category_fk, creator_fk) "
        "VALUES (%s, %s, %s, %s)",
        (title or f'epic-{uuid.uuid4().hex[:6]}', 'fixture epic', category_fk, creator_fk))
    return cur.lastrowid


def _insert_requirement(cur, creator_fk, category_fk):
    cur.execute(
        "INSERT INTO requirements (title, category_fk, creator_fk, ai_model, effort) "
        "VALUES (%s, %s, %s, 'opus', 'high')",
        (f'req-{uuid.uuid4().hex[:6]}', category_fk, creator_fk))
    return cur.lastrowid


def _insert_pipeline(cur, creator_fk, machine_fk=None, status='draft'):
    cur.execute(
        "INSERT INTO pipelines (title, description, pipeline_status, machine_fk, creator_fk) "
        "VALUES (%s, %s, %s, %s, %s)",
        (f'pipe-{uuid.uuid4().hex[:6]}', 'fixture goal', status, machine_fk, creator_fk))
    return cur.lastrowid


def _insert_step(cur, creator_fk, pipeline_fk, run='auto'):
    cur.execute(
        "INSERT INTO pipeline_steps (pipeline_fk, title, run, creator_fk) "
        "VALUES (%s, %s, %s, %s)",
        (pipeline_fk, f'step-{uuid.uuid4().hex[:6]}', run, creator_fk))
    return cur.lastrowid


# --- epics -----------------------------------------------------------------

def test_epics_category_fk_invalid_rejected(db_connection, test_creator_fk):
    """A non-existent category_fk is refused outright."""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO epics (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
                ('orphan epic', 999999, test_creator_fk))
    db_connection.rollback()


def test_epics_category_delete_restricted(db_connection, test_creator_fk, seed_test_profile):
    """epics -> categories is RESTRICT: you cannot orphan an epic by deleting its
    category. Move it first. Same policy as requirements."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
                    ('epic-restrict proj', test_creator_fk))
        project = cur.lastrowid
        cur.execute("INSERT INTO categories (category_name, project_fk, creator_fk) "
                    "VALUES (%s, %s, %s)", ('epic-restrict cat', project, test_creator_fk))
        category = cur.lastrowid
        _insert_epic(cur, test_creator_fk, category)

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM categories WHERE id = %s", (category,))
    db_connection.rollback()


# `features` and `requirements.feature_fk` were dropped at req #3355
# (migration 20260811033413) — the Feature tier's SET NULL/FK coverage went
# with them. Pipeline 2.0 seats a step under an epic directly (epic_fk on the
# step), never through Feature.

# --- pipelines -------------------------------------------------------------

def test_pipeline_status_defaults_to_draft(db_connection, test_creator_fk):
    """A pipeline is born `draft` — not active. started_at stays NULL until the
    transition, which is why it is NULL-able unlike the execution-table baseline."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipelines (title, creator_fk) VALUES (%s, %s)",
                    ('defaults probe', test_creator_fk))
        pipeline = cur.lastrowid
        cur.execute("SELECT pipeline_status, started_at, completed_at "
                    "FROM pipelines WHERE id = %s", (pipeline,))
        row = cur.fetchone()
        assert row['pipeline_status'] == 'draft'
        assert row['started_at'] is None
        assert row['completed_at'] is None
    db_connection.rollback()


def test_pipeline_machine_delete_restricted(db_connection, test_creator_fk):
    """pipelines -> machines is RESTRICT, matching every other machine reference
    in the schema: a machine with history pointing at it cannot be deleted out
    from under that history."""
    with db_connection.cursor() as cur:
        machine = _insert_machine(cur, test_creator_fk,
                                  hostname=f'pipe-{uuid.uuid4().hex[:8]}')
        _insert_pipeline(cur, test_creator_fk, machine_fk=machine)

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM machines WHERE id = %s", (machine,))
    db_connection.rollback()


def test_pipeline_machine_fk_nullable(db_connection, test_creator_fk):
    """NULL machine_fk means 'any machine' — a legal and common state."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk, machine_fk=None)
        cur.execute("SELECT machine_fk FROM pipelines WHERE id = %s", (pipeline,))
        assert cur.fetchone()['machine_fk'] is None
    db_connection.rollback()


# --- pipeline_steps --------------------------------------------------------

def test_pipeline_step_cascades_from_pipeline(db_connection, test_creator_fk):
    """The pipeline is the container: deleting a plan takes its steps."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)

        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline,))
        cur.execute("SELECT id FROM pipeline_steps WHERE id = %s", (step,))
        assert cur.fetchone() is None
    db_connection.rollback()


def test_pipeline_step_run_defaults_to_auto(db_connection, test_creator_fk):
    """`run` is the second dimension alongside derived state: auto launches as
    soon as deps complete, manual waits for the user. Default auto."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        cur.execute("INSERT INTO pipeline_steps (pipeline_fk, title, creator_fk) "
                    "VALUES (%s, %s, %s)", (pipeline, 'run default probe', test_creator_fk))
        step = cur.lastrowid
        cur.execute("SELECT run, completed_at, notes FROM pipeline_steps WHERE id = %s",
                    (step,))
        row = cur.fetchone()
        assert row['run'] == 'auto'
        assert row['completed_at'] is None
        assert row['notes'] is None
    db_connection.rollback()


def test_pipeline_step_pipeline_fk_invalid_rejected(db_connection, test_creator_fk):
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("INSERT INTO pipeline_steps (pipeline_fk, title, creator_fk) "
                        "VALUES (%s, %s, %s)", (999999, 'orphan step', test_creator_fk))
    db_connection.rollback()


def test_pipeline_step_notes_holds_gate_exception_prose(db_connection, test_creator_fk):
    """`notes` must hold the evidence a status enum cannot express. This exact
    shape is a real fixture value: a gate that passed WITH documented exceptions
    rather than raw green (req #3080, plan stage 1.4)."""
    evidence = ('gate passed WITH exceptions: skill harness 3709/3713, '
                '4 pre-existing failures dispositioned into #3061 scope')
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        cur.execute("INSERT INTO pipeline_steps (pipeline_fk, title, notes, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (pipeline, 'regression gate', evidence, test_creator_fk))
        step = cur.lastrowid
        cur.execute("SELECT notes FROM pipeline_steps WHERE id = %s", (step,))
        assert cur.fetchone()['notes'] == evidence
    db_connection.rollback()


# --- pipeline_step_requirements (asymmetric junction) ----------------------

def test_step_requirement_link_cascades_from_step(
        db_connection, test_creator_fk, test_category_id):
    """step_fk CASCADE: the links are the step's own data."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        req = _insert_requirement(cur, test_creator_fk, test_category_id)
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (step, req))

        cur.execute("DELETE FROM pipeline_steps WHERE id = %s", (step,))
        cur.execute("SELECT step_fk FROM pipeline_step_requirements WHERE step_fk = %s",
                    (step,))
        assert cur.fetchone() is None
        # ...and the requirement itself survives untouched.
        cur.execute("SELECT id FROM requirements WHERE id = %s", (req,))
        assert cur.fetchone() is not None
    db_connection.rollback()


def test_requirement_in_a_plan_cannot_be_deleted(
        db_connection, test_creator_fk, test_category_id):
    """requirement_fk is RESTRICT — the deliberate deviation from the
    CASCADE-both-sides junction default. Silently dropping a requirement out of
    an execution plan is exactly the residue failure this schema exists to
    prevent."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        req = _insert_requirement(cur, test_creator_fk, test_category_id)
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (step, req))

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM requirements WHERE id = %s", (req,))
    db_connection.rollback()


def test_step_requirement_duplicate_link_rejected(
        db_connection, test_creator_fk, test_category_id):
    """Composite PK: one requirement appears at most once in a given step."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        req = _insert_requirement(cur, test_creator_fk, test_category_id)
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (step, req))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                        "VALUES (%s, %s)", (step, req))
    db_connection.rollback()


def test_step_is_a_launch_unit_of_many_requirements(
        db_connection, test_creator_fk, test_category_id):
    """Design rule 2: requirements aggregate by the swarm-start that launches
    them. The fixture plan carries eight such steps (1, 12, 13, 19, 33, 38, 39,
    40); step 12 is a seven-requirement parallel launch. The POC rendered same-gate rows as
    scattered singles until they were merged by hand."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        reqs = [_insert_requirement(cur, test_creator_fk, test_category_id)
                for _ in range(7)]
        cur.executemany("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                        "VALUES (%s, %s)", [(step, r) for r in reqs])

        cur.execute("SELECT COUNT(*) AS c FROM pipeline_step_requirements "
                    "WHERE step_fk = %s", (step,))
        assert cur.fetchone()['c'] == 7
    db_connection.rollback()


def test_step_with_zero_requirements_is_legal(db_connection, test_creator_fk):
    """A step may legitimately have NO requirements — fixture plan step 7,
    "record the all-passing regression baseline". It has nothing to derive state
    from, which is precisely why completed_at exists as the manual stamp."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        cur.execute("INSERT INTO pipeline_steps (pipeline_fk, title, completed_at, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (pipeline, 'record regression baseline', '2026-07-26 01:30:00',
                     test_creator_fk))
        step = cur.lastrowid
        cur.execute("SELECT COUNT(*) AS c FROM pipeline_step_requirements "
                    "WHERE step_fk = %s", (step,))
        assert cur.fetchone()['c'] == 0
        cur.execute("SELECT completed_at FROM pipeline_steps WHERE id = %s", (step,))
        assert cur.fetchone()['completed_at'] is not None
    db_connection.rollback()


# --- pipeline_step_deps ----------------------------------------------------

def test_dep_step_cannot_be_deleted_while_referenced(db_connection, test_creator_fk):
    """DESIGN RULE 4, ENFORCED BY THE DATABASE. Ids are assigned once and never
    reused, and deleting or merging away a step that another step depends on
    must be BLOCKED — not silently orphan the graph."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        gate = _insert_step(cur, test_creator_fk, pipeline)
        dependent = _insert_step(cur, test_creator_fk, pipeline)
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) VALUES (%s, %s)",
                    (dependent, gate))

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM pipeline_steps WHERE id = %s", (gate,))
    db_connection.rollback()


def test_dep_rows_cascade_from_their_own_step(db_connection, test_creator_fk):
    """step_fk CASCADEs: the conditions ON a step are the step's own data, so
    deleting the dependent step takes them. (Contrast dep_step_fk above.)"""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        gate = _insert_step(cur, test_creator_fk, pipeline)
        dependent = _insert_step(cur, test_creator_fk, pipeline)
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) VALUES (%s, %s)",
                    (dependent, gate))

        cur.execute("DELETE FROM pipeline_steps WHERE id = %s", (dependent,))
        cur.execute("SELECT id FROM pipeline_step_deps WHERE step_fk = %s", (dependent,))
        assert cur.fetchone() is None
        # The gate step survives — nothing referenced IT.
        cur.execute("SELECT id FROM pipeline_steps WHERE id = %s", (gate,))
        assert cur.fetchone() is not None
    db_connection.rollback()


def test_dual_condition_gate_is_two_rows(db_connection, test_creator_fk):
    """THE s0.4 CASE. That gate waited on requirement #3050's session completing
    AND a 2-hour wall-clock gate at 06:31:38 PDT — two independent wait
    mechanisms on one step. Modeling it as two rows rather than a gate_expr
    string is what keeps both the topological sort and the watchdog able to read
    it."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        gate = _insert_step(cur, test_creator_fk, pipeline)
        dependent = _insert_step(cur, test_creator_fk, pipeline)

        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk, time_at) "
                    "VALUES (%s, %s, NULL)", (dependent, gate))
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk, time_at) "
                    "VALUES (%s, NULL, %s)", (dependent, '2026-07-24 13:31:38'))

        cur.execute("SELECT dep_step_fk, time_at FROM pipeline_step_deps "
                    "WHERE step_fk = %s ORDER BY id", (dependent,))
        rows = cur.fetchall()
        assert len(rows) == 2
        assert rows[0]['dep_step_fk'] == gate and rows[0]['time_at'] is None
        assert rows[1]['dep_step_fk'] is None and rows[1]['time_at'] is not None
    db_connection.rollback()


def test_duplicate_step_to_step_edge_rejected(db_connection, test_creator_fk):
    """UNIQUE(step_fk, dep_step_fk): the same gate cannot be recorded twice."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        gate = _insert_step(cur, test_creator_fk, pipeline)
        dependent = _insert_step(cur, test_creator_fk, pipeline)
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) VALUES (%s, %s)",
                    (dependent, gate))
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) "
                        "VALUES (%s, %s)", (dependent, gate))
    db_connection.rollback()


def test_multiple_time_only_deps_allowed_on_one_step(db_connection, test_creator_fk):
    """MySQL treats NULLs as distinct in a UNIQUE key, so the composite
    deliberately does NOT collapse time conditions: a step may carry more than
    one wall-clock gate. That is the intended scope of the invariant, not a hole
    in it — the key exists to forbid duplicate STEP edges."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        for stamp in ('2026-07-24 13:31:38', '2026-07-25 09:00:00'):
            cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk, time_at) "
                        "VALUES (%s, NULL, %s)", (step, stamp))

        cur.execute("SELECT COUNT(*) AS c FROM pipeline_step_deps "
                    "WHERE step_fk = %s AND dep_step_fk IS NULL", (step,))
        assert cur.fetchone()['c'] == 2
    db_connection.rollback()


def test_dep_step_fk_invalid_rejected(db_connection, test_creator_fk):
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) "
                        "VALUES (%s, %s)", (step, 999999))
    db_connection.rollback()


def test_deleting_a_pipeline_with_internal_deps_is_refused(
        db_connection, test_creator_fk):
    """THE OPERATIONAL CONSEQUENCE of dep_step_fk RESTRICT, pinned as a test so it
    can never be discovered by surprise in production.

    A plain `DELETE FROM pipelines` does NOT work once any step gates on another.
    MySQL evaluates the RESTRICT on dep_step_fk while cascading pipeline -> steps,
    and refuses — even though the referencing dep row is itself part of the same
    cascade. Every non-trivial plan hits this immediately (the fixture plan has 39
    step-to-step edges).

    This is the correct trade, not a defect: design rule 4 requires the database
    to block a referenced step from disappearing, and MySQL cannot express "block
    unless the whole graph is going." The price is that deleting a plan is a
    documented two-phase operation (see the next test), and the accidental
    one-line destruction of a plan is refused as a side benefit."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        gate = _insert_step(cur, test_creator_fk, pipeline)
        dependent = _insert_step(cur, test_creator_fk, pipeline)
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) VALUES (%s, %s)",
                    (dependent, gate))

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline,))
    db_connection.rollback()


def test_pipeline_teardown_order_clears_the_whole_graph(
        db_connection, test_creator_fk, test_category_id):
    """THE SUPPORTED TEARDOWN: drop the dependency edges first, then the pipeline.
    Steps and requirement links CASCADE from the pipeline, so two statements are
    enough. Any delete_pipeline implementation must follow this order.

    The requirements themselves must survive — they are not the plan's to delete.
    """
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        gate = _insert_step(cur, test_creator_fk, pipeline)
        dependent = _insert_step(cur, test_creator_fk, pipeline)
        req = _insert_requirement(cur, test_creator_fk, test_category_id)
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (dependent, req))
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) VALUES (%s, %s)",
                    (dependent, gate))

        # Phase 1 — edges.
        cur.execute("DELETE FROM pipeline_step_deps WHERE step_fk IN "
                    "(SELECT id FROM pipeline_steps WHERE pipeline_fk = %s)", (pipeline,))
        # Phase 2 — the container; steps and links cascade.
        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline,))

        for sql, params in (
                ("SELECT id FROM pipeline_steps WHERE pipeline_fk = %s", (pipeline,)),
                ("SELECT step_fk FROM pipeline_step_requirements WHERE step_fk IN (%s, %s)",
                 (gate, dependent)),
                ("SELECT id FROM pipeline_step_deps WHERE step_fk IN (%s, %s)",
                 (gate, dependent))):
            cur.execute(sql, params)
            assert cur.fetchone() is None, sql
        cur.execute("SELECT id FROM requirements WHERE id = %s", (req,))
        assert cur.fetchone() is not None
    db_connection.rollback()


def test_pipeline_without_internal_deps_deletes_directly(
        db_connection, test_creator_fk, test_category_id):
    """The simple case still works in one statement: a plan whose steps carry no
    step-to-step edges cascades cleanly. Only dep_step_fk RESTRICT blocks, and
    only when an edge exists."""
    with db_connection.cursor() as cur:
        pipeline = _insert_pipeline(cur, test_creator_fk)
        step = _insert_step(cur, test_creator_fk, pipeline)
        req = _insert_requirement(cur, test_creator_fk, test_category_id)
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (step, req))
        # A time-only condition references no step, so it never RESTRICTs.
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk, time_at) "
                    "VALUES (%s, NULL, %s)", (step, '2026-07-24 13:31:38'))

        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline,))

        cur.execute("SELECT id FROM pipeline_steps WHERE id = %s", (step,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM pipeline_step_deps WHERE step_fk = %s", (step,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM requirements WHERE id = %s", (req,))
        assert cur.fetchone() is not None
    db_connection.rollback()
