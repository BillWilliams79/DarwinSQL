"""`orchestration_claims` serves BOTH eras (req #3369, migration 20260809024954).

Structural proof, against a live `darwin_dev`, of the additive shape
`memory/pipeline-2-data-architecture.md` § 9.4 specifies: `pipeline_fk` (1.0)
became NULLable, `pipeline2_fk` / `epic2_fk` sit beside it, and — the one thing
a schema-derived Lambda-Rest/darwin-mcp test cannot show — the SECOND
generated-column UNIQUE key really does refuse a duplicate 2.0 whole-plan claim
AT THE DATABASE, the same way `uq_orchestration_claims_scope` already does for
1.0 (req #3224).

# COVERS: ENG-018
"""
import uuid

import pymysql
import pytest


@pytest.fixture
def p2_pipeline(db_connection, test_creator_fk):
    """One 2.0 pipeline to reserve scopes over. Function-scoped: the duplicate
    probe below mutates `orchestration_claims`."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipeline2_pipelines (title, creator_fk) "
                    "VALUES (%s, %s)",
                    (f'oc-p2-{uuid.uuid4().hex[:8]}', test_creator_fk))
        pipeline_id = cur.lastrowid
    db_connection.commit()

    yield pipeline_id

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM orchestration_claims WHERE pipeline2_fk = %s",
                    (pipeline_id,))
        cur.execute("DELETE FROM pipeline2_pipelines WHERE id = %s", (pipeline_id,))
    db_connection.commit()


def _columns(cur, table):
    cur.execute(f"DESCRIBE {table}")
    return {row['Field']: row for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

def test_pipeline_fk_became_nullable(db_connection):
    # Era is discriminated by WHICH PAIR IS NON-NULL — meaningless unless the
    # 1.0 pipeline_fk, NOT NULL since migration 20260801150404, can also be
    # NULL on a 2.0-only claim.
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'orchestration_claims')
    assert cols['pipeline_fk']['Null'] == 'YES'
    assert cols['pipeline2_fk']['Null'] == 'YES'
    assert cols['epic2_fk']['Null'] == 'YES'
    assert cols['epic2_key']['Extra'] == 'VIRTUAL GENERATED'


def test_both_scope_pairs_carry_their_own_unique_key(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SHOW INDEX FROM orchestration_claims "
                    "WHERE Key_name IN "
                    "('uq_orchestration_claims_scope', "
                    "'uq_orchestration_claims_scope2')")
        rows = cur.fetchall()
    by_key = {}
    for row in rows:
        by_key.setdefault(row['Key_name'], []).append(row['Column_name'])
    assert by_key['uq_orchestration_claims_scope'] == ['pipeline_fk', 'epic_key']
    assert by_key['uq_orchestration_claims_scope2'] == ['pipeline2_fk', 'epic2_key']


# ---------------------------------------------------------------------------
# The constraint itself — ENG-018
# ---------------------------------------------------------------------------

def test_a_second_2_0_whole_plan_claim_is_refused_by_the_database(
        db_connection, p2_pipeline, test_creator_fk):
    # THE regression this column exists for, on the 2.0 side: `epic2_fk` is
    # NULL on both rows, and MySQL treats NULLs in a UNIQUE index as DISTINCT.
    # A key written directly over `epic2_fk` — or the 1.0 key merely widened to
    # include the 2.0 columns, which `pipeline_fk` being NULL on every 2.0 row
    # would exempt from just as completely — would let both inserts succeed.
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline2_fk, creator_fk) "
            "VALUES (%s, %s)", (p2_pipeline, test_creator_fk))
    db_connection.commit()

    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO orchestration_claims (pipeline2_fk, creator_fk) "
                "VALUES (%s, %s)", (p2_pipeline, test_creator_fk))
    db_connection.rollback()
    assert exc.value.args[0] == 1062
    assert 'uq_orchestration_claims_scope2' in str(exc.value.args[1])


def test_the_generated_column_carries_the_key_not_epic2_fk_directly(
        db_connection, p2_pipeline, test_creator_fk):
    # Assert the stored key value directly, mirroring
    # test_pipeline2_behaviours.py's SCH-005 pattern — pins the MECHANISM, not
    # merely its effect.
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline2_fk, creator_fk) "
            "VALUES (%s, %s)", (p2_pipeline, test_creator_fk))
        cur.execute("SELECT epic2_fk, epic2_key FROM orchestration_claims "
                    "WHERE pipeline2_fk = %s", (p2_pipeline,))
        row = cur.fetchone()
    db_connection.commit()
    assert row['epic2_fk'] is None
    assert row['epic2_key'] == 0


def test_two_different_2_0_epics_of_one_plan_both_insert(
        db_connection, p2_pipeline, test_creator_fk):
    # The mirror of the refusal above: two DIFFERENT epic scopes on the same
    # 2.0 plan are not a collision — the constraint must not be over-eager.
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
                    (f'oc-proj-{uuid.uuid4().hex[:8]}', test_creator_fk))
        project_id = cur.lastrowid
        cur.execute("INSERT INTO categories (category_name, project_fk, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (f'oc-cat-{uuid.uuid4().hex[:8]}', project_id, test_creator_fk))
        category_id = cur.lastrowid
        cur.execute("INSERT INTO pipeline2_epics "
                    "(pipeline_fk, title, category_fk, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (p2_pipeline, f'oc-e2a-{uuid.uuid4().hex[:8]}', category_id,
                     test_creator_fk))
        epic_a = cur.lastrowid
        cur.execute("INSERT INTO pipeline2_epics "
                    "(pipeline_fk, title, category_fk, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (p2_pipeline, f'oc-e2b-{uuid.uuid4().hex[:8]}', category_id,
                     test_creator_fk))
        epic_b = cur.lastrowid
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline2_fk, epic2_fk, creator_fk) "
            "VALUES (%s, %s, %s)", (p2_pipeline, epic_a, test_creator_fk))
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline2_fk, epic2_fk, creator_fk) "
            "VALUES (%s, %s, %s)", (p2_pipeline, epic_b, test_creator_fk))
        cur.execute("SELECT COUNT(*) AS n FROM orchestration_claims "
                    "WHERE pipeline2_fk = %s", (p2_pipeline,))
        count = cur.fetchone()['n']
    db_connection.commit()
    assert count == 2

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM orchestration_claims WHERE pipeline2_fk = %s",
                    (p2_pipeline,))
        cur.execute("DELETE FROM pipeline2_epics WHERE id IN (%s, %s)",
                    (epic_a, epic_b))
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    db_connection.commit()


# ---------------------------------------------------------------------------
# 1.0 is unaffected — acceptance's explicit demonstration
# ---------------------------------------------------------------------------

def test_a_1_0_whole_plan_claim_still_succeeds_on_the_migrated_schema(
        db_connection, test_creator_fk):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipelines (title, creator_fk) VALUES (%s, %s)",
                    (f'oc-p1-{uuid.uuid4().hex[:8]}', test_creator_fk))
        pipeline_id = cur.lastrowid
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline_fk, creator_fk) "
            "VALUES (%s, %s)", (pipeline_id, test_creator_fk))
        cur.execute("SELECT pipeline_fk, pipeline2_fk, epic2_fk "
                    "FROM orchestration_claims WHERE pipeline_fk = %s",
                    (pipeline_id,))
        row = cur.fetchone()
    db_connection.commit()
    assert row['pipeline_fk'] == pipeline_id
    assert row['pipeline2_fk'] is None
    assert row['epic2_fk'] is None

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM orchestration_claims WHERE pipeline_fk = %s",
                    (pipeline_id,))
        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline_id,))
    db_connection.commit()
