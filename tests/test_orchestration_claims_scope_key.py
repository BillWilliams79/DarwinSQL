"""`orchestration_claims`'s scope key, proved AT THE DATABASE.

The one thing a schema-derived Lambda-Rest/darwin-mcp test cannot show: the
generated-column UNIQUE key `uq_orchestration_claims_scope` really does refuse
a duplicate whole-plan claim, where a key written over the nullable `initiative_fk`
directly would let both inserts through (MySQL treats NULLs in a UNIQUE index as
DISTINCT).

WAS `test_orchestration_claims_parallel_era.py` until req #3356 renamed this
table's columns twice in succession: migration 20260812175325 dropped the
first-generation `pipeline_fk`/`initiative_fk`/`initiative_key`/`uq_orchestration_claims_scope`
entirely (the parallel era this file was originally named for), then migration
20260812184333, in the same requirement's second half, renamed the surviving
second-generation pair — until then `pipeline2_fk`/`initiative2_fk`/`initiative2_key`/
`uq_orchestration_claims_scope2` — into those same freed plain names. There is
only one scope pair on this table now, under the plain names, and only one
scope key (`uq_orchestration_claims_scope`) backing it.

# COVERS: ENG-018
"""
import uuid

import pymysql
import pytest


@pytest.fixture
def p2_pipeline(db_connection, test_creator_fk):
    """One pipeline to reserve scopes over. Function-scoped: the duplicate
    probe below mutates `orchestration_claims`."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipelines (title, creator_fk) "
                    "VALUES (%s, %s)",
                    (f'oc-p2-{uuid.uuid4().hex[:8]}', test_creator_fk))
        pipeline_id = cur.lastrowid
    db_connection.commit()

    yield pipeline_id

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM orchestration_claims WHERE pipeline_fk = %s",
                    (pipeline_id,))
        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline_id,))
    db_connection.commit()


def _columns(cur, table):
    cur.execute(f"DESCRIBE {table}")
    return {row['Field']: row for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

def test_the_scope_pair_is_nullable_and_the_key_column_is_generated(db_connection):
    # `initiative_fk` NULL is what "whole-plan scope" MEANS, so the key cannot sit on
    # it directly — `initiative_key` is the VIRTUAL generated column that folds NULL
    # into a comparable 0. `pipeline_fk` is nullable because an initiative scope may
    # name the plan implicitly; the both-or-neither refusal is an
    # application-layer check in darwin-mcp, not a SQL CHECK.
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'orchestration_claims')
    assert cols['pipeline_fk']['Null'] == 'YES'
    assert cols['initiative_fk']['Null'] == 'YES'
    assert cols['initiative_key']['Extra'] == 'VIRTUAL GENERATED'


def test_only_the_plain_scope_key_survives(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SHOW INDEX FROM orchestration_claims "
                    "WHERE Key_name IN "
                    "('uq_orchestration_claims_scope', "
                    "'uq_orchestration_claims_scope2')")
        rows = cur.fetchall()
    by_key = {}
    for row in rows:
        by_key.setdefault(row['Key_name'], []).append(row['Column_name'])
    # The era-suffixed key name (`…_scope2`) is gone with the rest of the
    # `pipeline2_*` era marker; only the plain-named key survives, on the
    # same two columns it always carried.
    # req #3678 — the machine joined the key, so a SECOND machine may hold a
    # subscriber row on a scope another machine leads.
    assert by_key == {'uq_orchestration_claims_scope':
                      ['pipeline_fk', 'initiative_key', 'machine_key']}, by_key


# ---------------------------------------------------------------------------
# The constraint itself — ENG-018
# ---------------------------------------------------------------------------

def test_a_second_whole_plan_claim_is_refused_by_the_database(
        db_connection, p2_pipeline, test_creator_fk):
    # THE regression this column exists for: `initiative_fk` is NULL on both rows,
    # and MySQL treats NULLs in a UNIQUE index as DISTINCT. A key written
    # directly over `initiative_fk` would let both inserts succeed.
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline_fk, creator_fk) "
            "VALUES (%s, %s)", (p2_pipeline, test_creator_fk))
    db_connection.commit()

    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO orchestration_claims (pipeline_fk, creator_fk) "
                "VALUES (%s, %s)", (p2_pipeline, test_creator_fk))
    db_connection.rollback()
    assert exc.value.args[0] == 1062
    assert 'uq_orchestration_claims_scope' in str(exc.value.args[1])


def test_the_generated_column_carries_the_key_not_initiative_fk_directly(
        db_connection, p2_pipeline, test_creator_fk):
    # Assert the stored key value directly, mirroring
    # test_pipeline2_behaviours.py's SCH-005 pattern — pins the MECHANISM, not
    # merely its effect.
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline_fk, creator_fk) "
            "VALUES (%s, %s)", (p2_pipeline, test_creator_fk))
        cur.execute("SELECT initiative_fk, initiative_key FROM orchestration_claims "
                    "WHERE pipeline_fk = %s", (p2_pipeline,))
        row = cur.fetchone()
    db_connection.commit()
    assert row['initiative_fk'] is None
    assert row['initiative_key'] == 0


def test_two_different_initiatives_of_one_plan_both_insert(
        db_connection, p2_pipeline, test_creator_fk):
    # The mirror of the refusal above: two DIFFERENT initiative scopes on the same
    # plan are not a collision — the constraint must not be over-eager.
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
                    (f'oc-proj-{uuid.uuid4().hex[:8]}', test_creator_fk))
        project_id = cur.lastrowid
        cur.execute("INSERT INTO categories (category_name, project_fk, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (f'oc-cat-{uuid.uuid4().hex[:8]}', project_id, test_creator_fk))
        category_id = cur.lastrowid
        cur.execute("INSERT INTO initiatives "
                    "(pipeline_fk, title, category_fk, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (p2_pipeline, f'oc-e2a-{uuid.uuid4().hex[:8]}', category_id,
                     test_creator_fk))
        initiative_a = cur.lastrowid
        cur.execute("INSERT INTO initiatives "
                    "(pipeline_fk, title, category_fk, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (p2_pipeline, f'oc-e2b-{uuid.uuid4().hex[:8]}', category_id,
                     test_creator_fk))
        initiative_b = cur.lastrowid
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline_fk, initiative_fk, creator_fk) "
            "VALUES (%s, %s, %s)", (p2_pipeline, initiative_a, test_creator_fk))
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline_fk, initiative_fk, creator_fk) "
            "VALUES (%s, %s, %s)", (p2_pipeline, initiative_b, test_creator_fk))
        cur.execute("SELECT COUNT(*) AS n FROM orchestration_claims "
                    "WHERE pipeline_fk = %s", (p2_pipeline,))
        count = cur.fetchone()['n']
    db_connection.commit()
    assert count == 2

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM orchestration_claims WHERE pipeline_fk = %s",
                    (p2_pipeline,))
        cur.execute("DELETE FROM initiatives WHERE id IN (%s, %s)",
                    (initiative_a, initiative_b))
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    db_connection.commit()


# ---------------------------------------------------------------------------
# req #3678 — one row per scope PER MACHINE
# ---------------------------------------------------------------------------

@pytest.fixture
def two_machines(db_connection, test_creator_fk):
    ids = []
    with db_connection.cursor() as cur:
        for tag in ('a', 'b'):
            cur.execute("INSERT INTO machines (title, hostname, platform, arch, creator_fk) "
                        "VALUES (%s, %s, 'darwin', 'arm64', %s)",
                        (f'oc-m-{tag}-{uuid.uuid4().hex[:6]}',
                         f'oc-host-{tag}-{uuid.uuid4().hex[:6]}', test_creator_fk))
            ids.append(cur.lastrowid)
    db_connection.commit()
    yield ids
    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM orchestration_claims WHERE machine_fk IN (%s, %s)",
                    tuple(ids))
        cur.execute("DELETE FROM machines WHERE id IN (%s, %s)", tuple(ids))
    db_connection.commit()


def test_two_machines_may_hold_the_same_scope(
        db_connection, p2_pipeline, two_machines, test_creator_fk):
    # The lead and a subscriber: same whole-plan scope, different machines.
    with db_connection.cursor() as cur:
        for machine in two_machines:
            cur.execute(
                "INSERT INTO orchestration_claims (pipeline_fk, machine_fk, creator_fk) "
                "VALUES (%s, %s, %s)", (p2_pipeline, machine, test_creator_fk))
        cur.execute("SELECT COUNT(*) AS n FROM orchestration_claims "
                    "WHERE pipeline_fk = %s", (p2_pipeline,))
        count = cur.fetchone()['n']
    db_connection.commit()
    assert count == 2


def test_one_machine_may_not_hold_the_same_scope_twice(
        db_connection, p2_pipeline, two_machines, test_creator_fk):
    machine = two_machines[0]
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO orchestration_claims (pipeline_fk, machine_fk, creator_fk) "
            "VALUES (%s, %s, %s)", (p2_pipeline, machine, test_creator_fk))
    db_connection.commit()
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO orchestration_claims (pipeline_fk, machine_fk, creator_fk) "
                "VALUES (%s, %s, %s)", (p2_pipeline, machine, test_creator_fk))
    db_connection.rollback()
    assert exc.value.args[0] == 1062
    assert 'uq_orchestration_claims_scope' in str(exc.value.args[1])
