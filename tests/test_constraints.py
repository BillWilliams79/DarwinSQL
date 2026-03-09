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


def test_priority_fk_invalid_creator(db_connection):
    """INSERT priority with non-existent creator_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO priorities (title, creator_fk) "
                "VALUES (%s, %s)",
                ('orphan priority', 'nonexistent-profile-id')
            )
    db_connection.rollback()


def test_priority_session_fk_invalid_priority(db_connection):
    """INSERT priority_session with non-existent priority_fk → IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO priority_sessions (priority_fk, session_fk) "
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


def test_priority_title_not_null(db_connection, test_creator_fk):
    """INSERT priority with title=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO priorities (title, creator_fk) "
                "VALUES (%s, %s)",
                (None, test_creator_fk)
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

def test_priority_closed_default(db_connection, test_creator_fk):
    """INSERT priority without closed → defaults to 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO priorities (title, creator_fk) VALUES (%s, %s)",
            ('test priority default', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        priority_id = cur.fetchone()['id']

        cur.execute("SELECT closed, in_progress, scheduled FROM priorities WHERE id = %s",
                    (priority_id,))
        row = cur.fetchone()
        assert row['closed'] == 0
        assert row['in_progress'] == 0
        assert row['scheduled'] == 0

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
