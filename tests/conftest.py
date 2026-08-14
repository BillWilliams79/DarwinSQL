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
            "INSERT INTO profiles (id, name, email) "
            "VALUES (%s, %s, %s)",
            (test_creator_fk, 'Schema Test', 'schema@test.com'),
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

    # Cleanup — FK-safe order (leaves first, roots last)
    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM map_run_partners WHERE map_run_fk IN "
                    "(SELECT id FROM map_runs WHERE creator_fk = %s)", (test_creator_fk,))
        cur.execute("DELETE FROM map_partners WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM map_coordinates WHERE map_run_fk IN "
                    "(SELECT id FROM map_runs WHERE creator_fk = %s)", (test_creator_fk,))
        cur.execute("DELETE FROM map_runs WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM map_routes WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM requirement_sessions WHERE requirement_fk IN "
                    "(SELECT id FROM requirements WHERE creator_fk = %s)", (test_creator_fk,))
        cur.execute("DELETE FROM dev_servers WHERE creator_fk = %s", (test_creator_fk,))
        # Req #3337: the Pipeline 2.0 plan layer.
        # `pipeline_step_requirements.requirement_fk` and
        # `pipeline_step_deps.dep_step_fk` are both ON DELETE RESTRICT, so the
        # plan graph MUST be torn down before requirements and steps — a
        # leftover row blocks the deletes below. (The identical 1.0 teardown
        # stood here until req #3356, migration 20260812175325, dropped that
        # layer.)
        #
        # Scoped from BOTH ends on purpose. Deleting only rows whose step_fk
        # belongs to the test creator misses the row that points the other way,
        # and that row is constructible: darwin_dev permanently holds seeded
        # plan fixtures whose steps are owned by the real user. A test that
        # links its own requirement to a FIXTURE step (or gates a fixture step
        # on its own step) would otherwise survive teardown, fail the
        # requirements DELETE with a 1451, and take the whole session-scoped
        # teardown down with it — leaking the test profile, domain, area,
        # project and category into darwin_dev for every later run to
        # accumulate on.
        cur.execute("DELETE FROM pipeline_step_deps WHERE step_fk IN "
                    "(SELECT id FROM pipeline_steps WHERE creator_fk = %s) "
                    "OR dep_step_fk IN "
                    "(SELECT id FROM pipeline_steps WHERE creator_fk = %s)",
                    (test_creator_fk, test_creator_fk))
        cur.execute("DELETE FROM pipeline_step_requirements WHERE step_fk IN "
                    "(SELECT id FROM pipeline_steps WHERE creator_fk = %s) "
                    "OR requirement_fk IN "
                    "(SELECT id FROM requirements WHERE creator_fk = %s)",
                    (test_creator_fk, test_creator_fk))
        cur.execute("DELETE FROM pipeline_steps WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM epics WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM pipelines WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM requirements WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM swarm_sessions WHERE creator_fk = %s", (test_creator_fk,))
        # Req #2943: swarm_starts + machines. machine_fk is ON DELETE RESTRICT on
        # dev_servers/swarm_sessions/swarm_starts, so machines must be deleted
        # AFTER those three (all cleared just above) to satisfy the constraint.
        cur.execute("DELETE FROM swarm_starts WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM machines WHERE creator_fk = %s", (test_creator_fk,))
        # Req #3031: agent context telemetry. rows CASCADE from runs, so deleting
        # runs is sufficient; rows deleted first defensively for tests that commit
        # rows without a run parent.
        cur.execute("DELETE FROM agent_telemetry_rows WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM agent_telemetry_runs WHERE creator_fk = %s", (test_creator_fk,))
        # Req #2997: agents registry. Junctions CASCADE from both parents, so
        # deleting agents + instructions + architecture_documents is sufficient;
        # agents is deleted first so its links go before the shared catalogs.
        cur.execute("DELETE FROM agents WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM instructions WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM architecture_documents WHERE creator_fk = %s",
                    (test_creator_fk,))
        # Req #2380: test_cases/test_plans RESTRICT on categories, so delete
        # these BEFORE categories. test_results and test_runs also clean up
        # explicitly to handle tests that commit mid-run. The Feature-tier
        # catalog table and its test-case junction were dropped at req #3355
        # (migration 20260811033413) — test cases now re-home onto Requirement
        # via `requirement_test_cases`, cleaned up above with `requirements`
        # (ON DELETE CASCADE).
        cur.execute("DELETE FROM test_results WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM test_runs WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM test_plan_cases WHERE test_plan_fk IN "
                    "(SELECT id FROM test_plans WHERE creator_fk = %s)", (test_creator_fk,))
        cur.execute("DELETE FROM test_plans WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM test_cases WHERE creator_fk = %s", (test_creator_fk,))
        # `epics -> categories` is RESTRICT; the epics are already
        # cleared above, with the rest of the plan layer. (1.0's `epics` was
        # deleted here for the same reason until req #3356 dropped it.)
        cur.execute("DELETE FROM categories WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM projects WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM tasks WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM areas WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM domains WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM profiles WHERE id = %s", (test_creator_fk,))
    db_connection.commit()


# ---------------------------------------------------------------------------
# Shared project/category fixtures for requirement tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_category_id(db_connection, test_creator_fk, seed_test_profile):
    """Session-scoped project + category so requirement tests have a valid category_fk.

    Cleanup happens in seed_test_profile teardown (DELETE FROM categories, projects).
    """
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
            ('Schema Test Project', test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        project_id = cur.fetchone()['id']

        cur.execute(
            "INSERT INTO categories (category_name, project_fk, creator_fk) "
            "VALUES (%s, %s, %s)",
            ('Schema Test Category', project_id, test_creator_fk),
        )
        cur.execute("SELECT LAST_INSERT_ID() AS id")
        category_id = cur.fetchone()['id']
    db_connection.commit()
    return category_id


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
