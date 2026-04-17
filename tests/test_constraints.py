"""
Test FK constraints, NOT NULL constraints, unique constraints, and defaults.

Tests verify that database constraints prevent invalid data entry.
Each test uses transactions with rollback to keep darwin_dev test DB clean.
"""
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
