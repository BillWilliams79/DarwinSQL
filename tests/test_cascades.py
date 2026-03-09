"""
Test CASCADE DELETE and CASCADE UPDATE behavior on foreign keys.

Verifies that deleting parent records automatically cascades to children
as defined in the schema (profiles→domains→areas→tasks).
Each test uses transactions with rollback to keep darwin_dev test DB clean.
"""


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


def test_delete_category_sets_priority_fk_null(db_connection):
    """DELETE category → priorities.category_fk set to NULL (ON DELETE SET NULL)"""
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
            "INSERT INTO priorities (title, category_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('Cascade Test Priority', category_id, test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        priority_id = cur.fetchone()['id']

        # Delete category
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))

        # Priority survives but category_fk is NULL
        cur.execute("SELECT category_fk FROM priorities WHERE id = %s", (priority_id,))
        row = cur.fetchone()
        assert row is not None
        assert row['category_fk'] is None

    db_connection.rollback()


def test_delete_priority_cascades_to_priority_sessions(db_connection):
    """DELETE priority → associated priority_sessions rows are deleted"""
    test_creator = 'cascade-test-priority-1'

    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator, 'Cascade Test Profile', 'cascade@test.com')
        )
        cur.execute(
            "INSERT INTO priorities (title, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Priority', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        priority_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO swarm_sessions (swarm_status, creator_fk) VALUES (%s, %s)",
            ('active', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        session_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO priority_sessions (priority_fk, session_fk) VALUES (%s, %s)",
            (priority_id, session_id)
        )

        # Delete priority
        cur.execute("DELETE FROM priorities WHERE id = %s", (priority_id,))

        # Verify priority_session link is gone
        cur.execute(
            "SELECT * FROM priority_sessions WHERE priority_fk = %s AND session_fk = %s",
            (priority_id, session_id)
        )
        assert cur.fetchone() is None

    db_connection.rollback()


def test_delete_swarm_session_cascades_to_priority_sessions(db_connection):
    """DELETE swarm_session → associated priority_sessions rows are deleted,
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
            "INSERT INTO priorities (title, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Priority', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        priority_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO priority_sessions (priority_fk, session_fk) VALUES (%s, %s)",
            (priority_id, session_id)
        )

        # Delete swarm session
        cur.execute("DELETE FROM swarm_sessions WHERE id = %s", (session_id,))

        # Verify priority_session link is gone
        cur.execute(
            "SELECT * FROM priority_sessions WHERE session_fk = %s",
            (session_id,)
        )
        assert cur.fetchone() is None

        # Priority itself survives
        cur.execute("SELECT id FROM priorities WHERE id = %s", (priority_id,))
        assert cur.fetchone() is not None

    db_connection.rollback()


def test_delete_profile_cascades_to_roadmap_tables(db_connection):
    """DELETE profile → cascades through projects→categories, priorities, swarm_sessions"""
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
            "INSERT INTO priorities (title, creator_fk) VALUES (%s, %s)",
            ('Cascade Test Priority', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        priority_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO swarm_sessions (swarm_status, creator_fk) VALUES (%s, %s)",
            ('active', test_creator)
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        session_id = cur.fetchone()['id']

        # Delete profile — should cascade to all owned records
        cur.execute("DELETE FROM profiles WHERE id = %s", (test_creator,))

        cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
        assert cur.fetchone() is None
        cur.execute("SELECT id FROM priorities WHERE id = %s", (priority_id,))
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
