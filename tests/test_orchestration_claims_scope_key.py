"""`orchestration_claims`'s scope key, proved AT THE DATABASE.

The one thing a schema-derived Lambda-Rest/darwin-mcp test cannot show: the
generated-column UNIQUE key `uq_orchestration_claims_scope2` really does refuse
a duplicate whole-plan claim, where a key written over the nullable `epic2_fk`
directly would let both inserts through (MySQL treats NULLs in a UNIQUE index as
DISTINCT).

WAS `test_orchestration_claims_parallel_era.py` until req #3356 (migration
20260812175325). The parallel era it was named for is over: `pipeline_fk`,
`epic_fk`, `epic_key` and `uq_orchestration_claims_scope` are gone with the rest
of the 1.0 plan layer, so the two cases that asserted the two eras standing side
by side had no subject left. The `pipeline2_*` cases below are unchanged, and
`test_only_the_2_0_scope_key_survives` now asserts the 1.0 key's ABSENCE.

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

def test_the_scope_pair_is_nullable_and_the_key_column_is_generated(db_connection):
    # `epic2_fk` NULL is what "whole-plan scope" MEANS, so the key cannot sit on
    # it directly — `epic2_key` is the VIRTUAL generated column that folds NULL
    # into a comparable 0. `pipeline2_fk` is nullable because an epic scope may
    # name the plan implicitly; the both-or-neither refusal is an
    # application-layer check in darwin-mcp, not a SQL CHECK.
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'orchestration_claims')
    assert cols['pipeline2_fk']['Null'] == 'YES'
    assert cols['epic2_fk']['Null'] == 'YES'
    assert cols['epic2_key']['Extra'] == 'VIRTUAL GENERATED'
    # req #3356 — the 1.0 scope trio is gone, named so the eradication is
    # asserted rather than merely absent from the list above.
    assert 'pipeline_fk' not in cols
    assert 'epic_fk' not in cols
    assert 'epic_key' not in cols


def test_only_the_2_0_scope_key_survives(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SHOW INDEX FROM orchestration_claims "
                    "WHERE Key_name IN "
                    "('uq_orchestration_claims_scope', "
                    "'uq_orchestration_claims_scope2')")
        rows = cur.fetchall()
    by_key = {}
    for row in rows:
        by_key.setdefault(row['Key_name'], []).append(row['Column_name'])
    assert by_key == {'uq_orchestration_claims_scope2':
                      ['pipeline2_fk', 'epic2_key']}, by_key


# ---------------------------------------------------------------------------
# The constraint itself — ENG-018
# ---------------------------------------------------------------------------

def test_a_second_2_0_whole_plan_claim_is_refused_by_the_database(
        db_connection, p2_pipeline, test_creator_fk):
    # THE regression this column exists for: `epic2_fk` is NULL on both rows,
    # and MySQL treats NULLs in a UNIQUE index as DISTINCT. A key written
    # directly over `epic2_fk` would let both inserts succeed.
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
    # plan are not a collision — the constraint must not be over-eager.
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
