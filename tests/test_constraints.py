"""
Test FK constraints, NOT NULL constraints, unique constraints, and defaults.

Tests verify that database constraints prevent invalid data entry.
Each test uses transactions with rollback to keep darwin2 test DB clean.
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
                "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, 0, 'orphan task', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_area_fk_invalid_domain(db_connection, test_creator_fk):
    """INSERT area with non-existent domain_fk → pymysql.IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO areas2 (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                ('orphan area', 999999, test_creator_fk)
            )
    db_connection.rollback()


def test_domain_fk_invalid_profile(db_connection):
    """INSERT domain with non-existent creator_fk → pymysql.IntegrityError"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO domains2 (domain_name, creator_fk, closed) "
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
                "INSERT INTO domains2 (domain_name, creator_fk, closed) "
                "VALUES (%s, %s, 0)",
                (None, test_creator_fk)
            )
    db_connection.rollback()


def test_area_name_not_null(db_connection, test_creator_fk):
    """INSERT area with area_name=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO areas2 (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                (None, None, test_creator_fk)
            )
    db_connection.rollback()


def test_task_description_not_null(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with description=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, 0, None, seed_test_profile['area_id'], test_creator_fk)
            )
    db_connection.rollback()


def test_task_priority_not_null(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with priority=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
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
                "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, None, 'test task', seed_test_profile['area_id'], test_creator_fk)
            )
    db_connection.rollback()


def test_profile_name_not_null(db_connection):
    """INSERT profile with name=NULL → error"""
    with db_connection.cursor() as cur:
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO profiles2 (id, name, email, subject, userName, region, userPoolId) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                ('test-profile-id', None, 'test@test.com', 'test-subject',
                 'testuser', 'us-west-1', 'test-pool')
            )
    db_connection.rollback()


# ---------------------------------------------------------------------------
# Default Value Tests
# ---------------------------------------------------------------------------

def test_domain_closed_default(db_connection, test_creator_fk):
    """INSERT domain without specifying closed → closed defaults to 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains2 (domain_name, creator_fk) "
            "VALUES (%s, %s)",
            ('test domain default', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        cur.execute("SELECT closed FROM domains2 WHERE id = %s", (domain_id,))
        row = cur.fetchone()
        assert row['closed'] == 0

    db_connection.rollback()


def test_area_closed_default(db_connection, test_creator_fk):
    """INSERT area without specifying closed → closed defaults to 0"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas2 (area_name, domain_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('test area default', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT closed FROM areas2 WHERE id = %s", (area_id,))
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
            "INSERT INTO areas2 (area_name, domain_fk, creator_fk, closed, sort_order) "
            "VALUES (%s, %s, %s, 0, %s)",
            ('test area nullable', None, test_creator_fk, None)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT sort_order FROM areas2 WHERE id = %s", (area_id,))
        row = cur.fetchone()
        assert row['sort_order'] is None

    db_connection.rollback()


def test_task_sort_order_nullable(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task with sort_order=NULL → succeeds"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk, sort_order) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (0, 0, 'test task nullable', seed_test_profile['area_id'], test_creator_fk, None)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT sort_order FROM tasks2 WHERE id = %s", (task_id,))
        row = cur.fetchone()
        assert row['sort_order'] is None

    db_connection.rollback()


def test_task_done_ts_nullable(db_connection, test_creator_fk, seed_test_profile):
    """INSERT task without done_ts → NULL stored"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'test task done_ts', seed_test_profile['area_id'], test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT done_ts FROM tasks2 WHERE id = %s", (task_id,))
        row = cur.fetchone()
        assert row['done_ts'] is None

    db_connection.rollback()


def test_area_domain_fk_nullable(db_connection, test_creator_fk):
    """INSERT area with domain_fk=NULL → succeeds (nullable FK)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas2 (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('test area no domain', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT domain_fk FROM areas2 WHERE id = %s", (area_id,))
        row = cur.fetchone()
        assert row['domain_fk'] is None

    db_connection.rollback()


def test_task_area_fk_nullable(db_connection, test_creator_fk):
    """INSERT task with area_fk=NULL → succeeds (nullable FK)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'test task no area', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT area_fk FROM tasks2 WHERE id = %s", (task_id,))
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
            "INSERT INTO domains2 (domain_name, creator_fk, closed) "
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
            "INSERT INTO areas2 (area_name, domain_fk, creator_fk, closed) "
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
            "INSERT INTO tasks2 (priority, done, description, area_fk, creator_fk) "
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
            "INSERT INTO profiles2 (id, name, email, subject, userName, region, userPoolId) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (test_id, 'Test Profile 1', 'test1@test.com', 'subject1',
             'testuser1', 'us-west-1', 'test-pool')
        )

        # Attempt to insert duplicate
        with pytest.raises(pymysql.IntegrityError):
            cur.execute(
                "INSERT INTO profiles2 (id, name, email, subject, userName, region, userPoolId) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (test_id, 'Test Profile 2', 'test2@test.com', 'subject2',
                 'testuser2', 'us-west-1', 'test-pool')
            )

    db_connection.rollback()


def test_domain_pk_auto_unique(db_connection, test_creator_fk):
    """INSERT multiple domains → each gets unique auto-increment id"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO domains2 (domain_name, creator_fk, closed) "
            "VALUES (%s, %s, 0)",
            ('domain1', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        id1 = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO domains2 (domain_name, creator_fk, closed) "
            "VALUES (%s, %s, 0)",
            ('domain2', test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        id2 = cur.fetchone()['id']

        assert id1 != id2
        assert id1 > 0 and id2 > 0

    db_connection.rollback()
