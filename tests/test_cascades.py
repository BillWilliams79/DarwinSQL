"""
Test CASCADE DELETE and CASCADE UPDATE behavior on foreign keys.

Verifies that deleting parent records automatically cascades to children
as defined in the schema (profiles→domains→areas→tasks).
Each test uses transactions with rollback to keep darwin_dev test DB clean.
"""
import pymysql
import pytest


# ---------------------------------------------------------------------------
# Cascade Delete Tests — Single Level
# ---------------------------------------------------------------------------

def test_delete_profile_cascades_to_domains(db_connection):
    """DELETE profile → all domains with that creator_fk are deleted"""
    test_creator = 'cascade-test-profile-1'

    with db_connection.cursor() as cur:
        # Create profile
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )

        # Create domain under profile
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Cascade Test Domain', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        # Delete profile
        cur.execute("DELETE FROM profiles WHERE id = %s", (test_creator,))

        # Verify domain is gone
        cur.execute("SELECT id FROM domains WHERE id = %s", (domain_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_domain_cascades_to_areas(db_connection):
    """DELETE domain → all areas with that domain_fk are deleted"""
    test_creator = 'cascade-test-domain-1'

    with db_connection.cursor() as cur:
        # Create profile (to satisfy domain FK)
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )

        # Create domain
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Cascade Test Domain', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        # Create area under domain
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('Cascade Test Area', domain_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        # Delete domain
        cur.execute("DELETE FROM domains WHERE id = %s", (domain_id,))

        # Verify area is gone
        cur.execute("SELECT id FROM areas WHERE id = %s", (area_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_area_cascades_to_tasks(db_connection):
    """DELETE area → all tasks with that area_fk are deleted"""
    test_creator = 'cascade-test-area-1'

    with db_connection.cursor() as cur:
        # Create profile (to satisfy FKs)
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )

        # Create domain
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Cascade Test Domain', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        # Create area
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('Cascade Test Area', domain_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        # Create task under area
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'Cascade Test Task', area_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        # Delete area
        cur.execute("DELETE FROM areas WHERE id = %s", (area_id,))

        # Verify task is gone
        cur.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Cascade Delete Tests — Full Hierarchy
# ---------------------------------------------------------------------------

def test_delete_profile_cascades_full_hierarchy(db_connection):
    """DELETE profile → cascades through domain→area→task (all children deleted)"""
    test_creator = 'cascade-test-full-hierarchy'

    with db_connection.cursor() as cur:
        # Create profile
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )

        # Create domain
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Cascade Test Domain', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        # Create area
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('Cascade Test Area', domain_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        # Create task
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'Cascade Test Task', area_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        # Delete profile — should cascade to all children
        cur.execute("DELETE FROM profiles WHERE id = %s", (test_creator,))

        # Verify all children are gone
        cur.execute("SELECT id FROM domains WHERE id = %s", (domain_id,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM areas WHERE id = %s", (area_id,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_domain_cascades_full_subtree(db_connection):
    """DELETE domain → cascades through area→task (all children deleted)"""
    test_creator = 'cascade-test-domain-subtree'

    with db_connection.cursor() as cur:
        # Create profile
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )

        # Create domain
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Cascade Test Domain', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        # Create multiple areas
        area_ids = []
        task_ids = []
        for i in range(3):
            cur.execute(
                "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                (f'Cascade Test Area {i}', domain_id, test_creator)
            )
            cur.execute("SELECT LAST_INSERT_ID() AS id")
            area_id = cur.fetchone()['id']
            area_ids.append(area_id)

            # Create task under area
            cur.execute(
                "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, 0, f'Cascade Test Task {i}', area_id, test_creator)
            )
            cur.execute("SELECT LAST_INSERT_ID() AS id")
            task_ids.append(cur.fetchone()['id'])

        # Delete domain
        cur.execute("DELETE FROM domains WHERE id = %s", (domain_id,))

        # Verify all areas and tasks are gone
        for area_id in area_ids:
            cur.execute("SELECT id FROM areas WHERE id = %s", (area_id,))
            assert cur.fetchone() is None

        for task_id in task_ids:
            cur.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
            assert cur.fetchone() is None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Nullable Foreign Key Tests
# ---------------------------------------------------------------------------

def test_domain_fk_null_allowed(db_connection, test_creator_fk):
    """INSERT area with domain_fk=NULL → succeeds (FK is nullable)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
            "VALUES (%s, %s, %s, 0)",
            ('area with no domain', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        area_id = cur.fetchone()['id']

        cur.execute("SELECT domain_fk FROM areas WHERE id = %s", (area_id,))
        row = cur.fetchone()
        assert row['domain_fk'] is None

    db_connection.rollback()


def test_task_area_fk_null_allowed(db_connection, test_creator_fk):
    """INSERT task with area_fk=NULL → succeeds (FK is nullable)"""
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            (0, 0, 'task with no area', None, test_creator_fk)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        task_id = cur.fetchone()['id']

        cur.execute("SELECT area_fk FROM tasks WHERE id = %s", (task_id,))
        row = cur.fetchone()
        assert row['area_fk'] is None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Cascade Isolation Tests (Verify Cascades Don't Delete Unrelated Records)
# ---------------------------------------------------------------------------

def test_delete_domain_does_not_cascade_cross_creator(db_connection):
    """DELETE domain → only cascades to children with matching domain_fk,
    not to other areas with different domain_fk"""
    creator1 = 'cascade-test-creator-1'
    creator2 = 'cascade-test-creator-2'

    with db_connection.cursor() as cur:
        # Create two profiles
        for creator in [creator1, creator2]:
            cur.execute(
                "INSERT INTO profiles (id, name, email) "
                "VALUES (%s, %s, %s)",
                (creator, f'Profile {creator}', f'{creator}@test.com')
            )

        # Create two domains (one per creator)
        domain_ids = {}
        area_ids = {}
        for creator in [creator1, creator2]:
            cur.execute(
                "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
                (f'Domain {creator}', creator)
            )
            cur.execute("SELECT LAST_INSERT_ID() AS id")
            domain_id = cur.fetchone()['id']
            domain_ids[creator] = domain_id

            # Create area under domain
            cur.execute(
                "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                (f'Area {creator}', domain_id, creator)
            )
            cur.execute("SELECT LAST_INSERT_ID() AS id")
            area_ids[creator] = cur.fetchone()['id']

        # Delete only creator1's domain
        cur.execute("DELETE FROM domains WHERE id = %s", (domain_ids[creator1],))

        # Verify creator1's area is gone, but creator2's area survives
        cur.execute("SELECT id FROM areas WHERE id = %s", (area_ids[creator1],))
        assert cur.fetchone() is None

        cur.execute("SELECT id FROM areas WHERE id = %s", (area_ids[creator2],))
        assert cur.fetchone() is not None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Cascade Delete Tests — Roadmap Tables
# ---------------------------------------------------------------------------

def test_delete_project_cascades_to_categories(db_connection):
    """DELETE project → all categories with that project_fk are deleted"""
    test_creator = 'cascade-test-project-1'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Project', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        project_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO categories (category_name, project_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('Cascade Test Category', project_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        category_id = cur.fetchone()['id']

        # Delete project
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))

        # Verify category is gone
        cur.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_category_with_requirements_rejected(db_connection):
    """DELETE category with live requirements → IntegrityError (ON DELETE RESTRICT, req #2217).

    This replaces the old SET NULL semantics (pre-migration 041). Deleting a category
    that still has requirements linked to it is now blocked — callers must move or
    delete the requirements first.
    """
    test_creator = 'cascade-test-category-1'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Project', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        project_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO categories (category_name, project_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('Cascade Test Category', project_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        category_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO requirements (title, category_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('Cascade Test Requirement', category_id, test_creator)
        )

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))

    db_connection.rollback()


def test_delete_empty_category_succeeds(db_connection):
    """DELETE empty category → succeeds (RESTRICT only blocks when requirements exist)."""
    test_creator = 'cascade-test-category-empty'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Project', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        project_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO categories (category_name, project_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('Empty Category', project_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        category_id = cur.fetchone()['id']

        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))

        cur.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_requirement_cascades_to_requirement_sessions(db_connection, test_category_id):
    """DELETE requirement → associated requirement_sessions rows are deleted"""
    test_creator = 'cascade-test-requirement-1'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO requirements (title, creator_fk, category_fk) VALUES (%s, %s, %s)",
            ('Cascade Test Requirement', test_creator, test_category_id)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        requirement_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO swarm_sessions (swarm_status, creator_fk) VALUES (%s, %s)",
            ('active', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        session_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO requirement_sessions (requirement_fk, session_fk) VALUES (%s, %s)",
            (requirement_id, session_id)
        )

        # Delete requirement
        cur.execute("DELETE FROM requirements WHERE id = %s", (requirement_id,))

        # Verify requirement_session link is gone
        cur.execute(
            "SELECT * FROM requirement_sessions WHERE requirement_fk = %s AND session_fk = %s",
            (requirement_id, session_id)
        )
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_swarm_session_cascades_to_requirement_sessions(db_connection, test_category_id):
    """DELETE swarm_session → associated requirement_sessions rows are deleted,
    dev_servers.session_fk set to NULL"""
    test_creator = 'cascade-test-session-1'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO swarm_sessions (swarm_status, creator_fk) VALUES (%s, %s)",
            ('active', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        session_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO requirements (title, creator_fk, category_fk) VALUES (%s, %s, %s)",
            ('Cascade Test Requirement', test_creator, test_category_id)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        requirement_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO requirement_sessions (requirement_fk, session_fk) VALUES (%s, %s)",
            (requirement_id, session_id)
        )

        # Delete swarm session
        cur.execute("DELETE FROM swarm_sessions WHERE id = %s", (session_id,))

        # Verify requirement_session link is gone
        cur.execute(
            "SELECT * FROM requirement_sessions WHERE session_fk = %s",
            (session_id,)
        )
        assert cur.fetchone() is None

        # Requirement itself survives
        cur.execute("SELECT id FROM requirements WHERE id = %s", (requirement_id,))
        assert cur.fetchone() is not None

    db_connection.rollback()


def test_delete_profile_cascades_to_roadmap_tables(db_connection, test_category_id):
    """DELETE profile → cascades through projects→categories, requirements, swarm_sessions.

    Requirement references a category owned by a different creator (the session
    test_creator_fk), so the profile cascade deletes this profile's requirements
    without tripping the RESTRICT FK on that other creator's category.
    """
    test_creator = 'cascade-test-roadmap-full'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Project', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        project_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO requirements (title, creator_fk, category_fk) VALUES (%s, %s, %s)",
            ('Cascade Test Requirement', test_creator, test_category_id)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        requirement_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO swarm_sessions (swarm_status, creator_fk) VALUES (%s, %s)",
            ('active', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        session_id = cur.fetchone()['id']

        # Delete profile — should cascade to all owned records. The category
        # referenced by the requirement is owned by a different creator, so
        # the cascade here only touches this profile's rows.
        cur.execute("DELETE FROM profiles WHERE id = %s", (test_creator,))

        cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM requirements WHERE id = %s", (requirement_id,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM swarm_sessions WHERE id = %s", (session_id,))
        assert cur.fetchone() is None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Cascade Isolation Tests (Verify Cascades Don't Delete Unrelated Records)
# ---------------------------------------------------------------------------

def test_delete_area_does_not_affect_sibling_areas(db_connection):
    """DELETE area → only cascades to tasks under that area,
    not to tasks under sibling areas"""
    test_creator = 'cascade-test-siblings'

    with db_connection.cursor() as cur:
        # Create profile
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )

        # Create domain
        cur.execute(
            "INSERT INTO domains (domain_name, creator_fk, closed) VALUES (%s, %s, 0)",
            ('Cascade Test Domain', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        domain_id = cur.fetchone()['id']

        # Create two sibling areas
        area_ids = {}
        task_ids = {}
        for i in range(2):
            cur.execute(
                "INSERT INTO areas (area_name, domain_fk, creator_fk, closed) "
                "VALUES (%s, %s, %s, 0)",
                (f'Cascade Test Area {i}', domain_id, test_creator)
            )
            cur.execute("SELECT LAST_INSERT_ID() AS id")
            area_id = cur.fetchone()['id']
            area_ids[i] = area_id

            # Create task under area
            cur.execute(
                "INSERT INTO tasks (priority, done, description, area_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s, %s)",
                (0, 0, f'Cascade Test Task {i}', area_id, test_creator)
            )
            cur.execute("SELECT LAST_INSERT_ID() AS id")
            task_ids[i] = cur.fetchone()['id']

        # Delete only area 0
        cur.execute("DELETE FROM areas WHERE id = %s", (area_ids[0],))

        # Verify area 0 and its task are gone, but area 1 and its task survive
        cur.execute("SELECT id FROM areas WHERE id = %s", (area_ids[0],))
        assert cur.fetchone() is None

        cur.execute("SELECT id FROM tasks WHERE id = %s", (task_ids[0],))
        assert cur.fetchone() is None

        cur.execute("SELECT id FROM areas WHERE id = %s", (area_ids[1],))
        assert cur.fetchone() is not None

        cur.execute("SELECT id FROM tasks WHERE id = %s", (task_ids[1],))
        assert cur.fetchone() is not None

    db_connection.rollback()


# ---------------------------------------------------------------------------
# Req #2380 — Swarm Features & Test Cases registry CASCADE/RESTRICT
# ---------------------------------------------------------------------------

def _setup_validation_creator(cur, prefix):
    """Create a dedicated profile + project + category for a cascade test scenario.

    Returns (creator, project_id, category_id). Caller is responsible for
    rollback (tests use the usual rollback pattern).
    """
    creator = f'{prefix}-{__import__("uuid").uuid4().hex[:6]}'
    cur.execute(
        "INSERT INTO profiles (id, name, email) VALUES (%s, %s, %s)",
        (creator, 'Validation Cascade', f'{creator}@test.com')
    )
    cur.execute(
        "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
        ('validation cascade project', creator)
    )
    cur.execute("SELECT LAST_INSERT_ID() AS id")
    project_id = cur.fetchone()['id']
    cur.execute(
        "INSERT INTO categories (category_name, project_fk, creator_fk) "
        "VALUES (%s, %s, %s)",
        ('validation cascade category', project_id, creator)
    )
    cur.execute("SELECT LAST_INSERT_ID() AS id")
    category_id = cur.fetchone()['id']
    return creator, project_id, category_id


def test_delete_category_with_features_rejected(db_connection):
    """DELETE category with live features → IntegrityError (ON DELETE RESTRICT)."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-feat-cat')
        cur.execute(
            "INSERT INTO features (title, description, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            ('blocker feature', 'd', category_id, creator)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    db_connection.rollback()


def test_delete_category_with_test_cases_rejected(db_connection):
    """DELETE category with live test_cases → IntegrityError (ON DELETE RESTRICT)."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-tc-cat')
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('blocker case', '1', 'ok', category_id, creator)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    db_connection.rollback()


def test_delete_category_with_test_plans_rejected(db_connection):
    """DELETE category with live test_plans → IntegrityError (ON DELETE RESTRICT)."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-plan-cat')
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('blocker plan', category_id, creator)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    db_connection.rollback()


def test_delete_feature_cascades_to_feature_test_cases(db_connection):
    """DELETE feature → CASCADE removes its feature_test_cases rows."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-feat-del')
        cur.execute(
            "INSERT INTO features (title, description, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            ('feat', 'd', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        feature_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case', '1', 'ok', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO feature_test_cases (feature_fk, test_case_fk) VALUES (%s, %s)",
            (feature_id, case_id)
        )

        cur.execute("DELETE FROM features WHERE id = %s", (feature_id,))

        cur.execute(
            "SELECT COUNT(*) AS c FROM feature_test_cases "
            "WHERE feature_fk = %s OR test_case_fk = %s",
            (feature_id, case_id)
        )
        assert cur.fetchone()['c'] == 0  # CASCADE removed the junction row
        # Test case itself is untouched
        cur.execute("SELECT id FROM test_cases WHERE id = %s", (case_id,))
        assert cur.fetchone() is not None
    db_connection.rollback()


def test_delete_test_case_cascades_to_feature_test_cases(db_connection):
    """DELETE test_case → CASCADE removes its feature_test_cases rows."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-case-del')
        cur.execute(
            "INSERT INTO features (title, description, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            ('feat', 'd', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        feature_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case', '1', 'ok', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO feature_test_cases (feature_fk, test_case_fk) VALUES (%s, %s)",
            (feature_id, case_id)
        )

        cur.execute("DELETE FROM test_cases WHERE id = %s", (case_id,))

        cur.execute(
            "SELECT COUNT(*) AS c FROM feature_test_cases WHERE test_case_fk = %s",
            (case_id,)
        )
        assert cur.fetchone()['c'] == 0
        # Feature itself untouched
        cur.execute("SELECT id FROM features WHERE id = %s", (feature_id,))
        assert cur.fetchone() is not None
    db_connection.rollback()


def test_delete_test_plan_with_runs_rejected(db_connection):
    """DELETE test_plan with live test_runs → IntegrityError (ON DELETE RESTRICT).

    A plan with run history cannot be deleted; the caller must close or archive first.
    """
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-plan-run')
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan with history', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_runs (test_plan_fk, creator_fk) VALUES (%s, %s)",
            (plan_id, creator)
        )
        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM test_plans WHERE id = %s", (plan_id,))
    db_connection.rollback()


def test_delete_test_run_cascades_to_results(db_connection):
    """DELETE test_run → CASCADE removes its test_results rows."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-run-del')
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case', '1', 'ok', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_runs (test_plan_fk, creator_fk) VALUES (%s, %s)",
            (plan_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_results "
            "(test_run_fk, test_case_fk, result_status, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            (run_id, case_id, 'passed', creator)
        )

        cur.execute("DELETE FROM test_runs WHERE id = %s", (run_id,))

        cur.execute("SELECT COUNT(*) AS c FROM test_results WHERE test_run_fk = %s", (run_id,))
        assert cur.fetchone()['c'] == 0  # CASCADE removed results
        # Case is untouched
        cur.execute("SELECT id FROM test_cases WHERE id = %s", (case_id,))
        assert cur.fetchone() is not None
    db_connection.rollback()


def test_delete_test_case_with_results_rejected(db_connection):
    """DELETE test_case with live test_results → IntegrityError (ON DELETE RESTRICT).

    Protects historical run data: cannot remove a test_case that already has
    recorded outcomes.
    """
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-case-result')
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case with result', '1', 'ok', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_runs (test_plan_fk, creator_fk) VALUES (%s, %s)",
            (plan_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        run_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_results "
            "(test_run_fk, test_case_fk, result_status, creator_fk) "
            "VALUES (%s, %s, %s, %s)",
            (run_id, case_id, 'failed', creator)
        )

        with pytest.raises(pymysql.IntegrityError):
            cur.execute("DELETE FROM test_cases WHERE id = %s", (case_id,))
    db_connection.rollback()


def test_delete_test_plan_cascades_to_plan_cases(db_connection):
    """DELETE test_plan (when no runs exist) → CASCADE removes its test_plan_cases rows."""
    with db_connection.cursor() as cur:
        creator, _project, category_id = _setup_validation_creator(cur, 'cascade-plan-cases')
        cur.execute(
            "INSERT INTO test_plans (title, category_fk, creator_fk) VALUES (%s, %s, %s)",
            ('plan to delete', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        plan_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_cases (title, steps, expected, category_fk, creator_fk) "
            "VALUES (%s, %s, %s, %s, %s)",
            ('case', '1', 'ok', category_id, creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        case_id = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO test_plan_cases (test_plan_fk, test_case_fk, sort_order) "
            "VALUES (%s, %s, 1)",
            (plan_id, case_id)
        )

        cur.execute("DELETE FROM test_plans WHERE id = %s", (plan_id,))

        cur.execute(
            "SELECT COUNT(*) AS c FROM test_plan_cases WHERE test_plan_fk = %s",
            (plan_id,)
        )
        assert cur.fetchone()['c'] == 0  # CASCADE removed the junction row
        # Case itself is untouched
        cur.execute("SELECT id FROM test_cases WHERE id = %s", (case_id,))
        assert cur.fetchone() is not None
    db_connection.rollback()
