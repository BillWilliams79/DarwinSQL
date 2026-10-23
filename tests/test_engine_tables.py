"""Orchestration Engine 2's data-contract tables, proved AT THE DATABASE (req #3756).

Three properties a schema-derived Lambda-Rest or darwin-mcp test cannot show:

  * the scope keys really refuse a duplicate WHOLE-PLAN row — `initiative_fk` is NULL
    there, and MySQL treats NULLs in a UNIQUE index as DISTINCT, which is why
    `engine_states` keys on the generated `initiative_key`;
  * a desired-state flip on `engine_states` never stamps a heartbeat — the
    reason the heartbeat is a table of its own;
  * a decision record's JSON reads back equal to what was written, and the
    executor's outcome dies with the record that admitted it.
"""
import json
import uuid

import pymysql
import pytest

HASH = 'sha256:' + '0' * 64


@pytest.fixture
def scope(db_connection, test_creator_fk):
    """A plan, an initiative and a machine to hang engine rows on."""
    tag = uuid.uuid4().hex[:8]
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipelines (title, creator_fk) VALUES (%s, %s)",
                    (f'eng-{tag}', test_creator_fk))
        pipeline_id = cur.lastrowid
        cur.execute("INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
                    (f'eng-{tag}', test_creator_fk))
        project_id = cur.lastrowid
        cur.execute("INSERT INTO categories (category_name, project_fk, creator_fk) "
                    "VALUES (%s, %s, %s)", (f'eng-{tag}', project_id, test_creator_fk))
        category_id = cur.lastrowid
        cur.execute("INSERT INTO initiatives (title, pipeline_fk, category_fk, creator_fk) "
                    "VALUES (%s, %s, %s, %s)",
                    (f'eng-{tag}', pipeline_id, category_id, test_creator_fk))
        initiative_id = cur.lastrowid
        cur.execute("INSERT INTO machines (title, hostname, platform, arch, creator_fk) "
                    "VALUES (%s, %s, 'darwin', 'arm64', %s)",
                    (f'eng-{tag}', f'eng-{tag}.local', test_creator_fk))
        machine_id = cur.lastrowid
    db_connection.commit()

    yield {'pipeline': pipeline_id, 'initiative': initiative_id, 'machine': machine_id}

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM engine_inputs WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline_id,))
        cur.execute("DELETE FROM machines WHERE id = %s", (machine_id,))
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    db_connection.commit()


def _columns(cur, table):
    cur.execute(f"DESCRIBE {table}")
    return {row['Field']: row for row in cur.fetchall()}


def _insert_state(cur, scope, creator, initiative=None):
    cur.execute("INSERT INTO engine_states (pipeline_fk, initiative_fk, machine_fk, creator_fk) "
                "VALUES (%s, %s, %s, %s)", (scope['pipeline'], initiative, scope['machine'], creator))
    return cur.lastrowid


def _insert_record(cur, scope, creator, record, record_hash=HASH):
    cur.execute(
        "INSERT INTO engine_decision_records (record_hash, pipeline_fk, machine_fk, seq, "
        "verdict, plan_payload_hash, capacity_hash, claims_hash, clock_hash, record, "
        "creator_fk) VALUES (%s, %s, %s, 1, 'OK', %s, %s, %s, %s, %s, %s)",
        (record_hash, scope['pipeline'], scope['machine'], HASH, HASH, HASH, HASH,
         json.dumps(record), creator))
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

def test_engine_states_defaults_are_off_and_stopped(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'engine_states')
    assert cols['desired_state']['Default'] == 'off'
    assert cols['desired_state']['Null'] == 'NO'
    assert cols['actual_state']['Default'] == 'stopped'
    assert cols['actual_state']['Null'] == 'NO'
    assert cols['initiative_key']['Extra'] == 'VIRTUAL GENERATED'
    assert cols['machine_fk']['Null'] == 'NO'


def test_heartbeat_clock_is_on_update(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'engine_heartbeats')
    assert 'on update CURRENT_TIMESTAMP' in cols['beat_at']['Extra']
    assert cols['health']['Type'] == 'json'
    assert cols['beats']['Default'] == '0'


def test_record_and_input_bodies_are_json(db_connection):
    with db_connection.cursor() as cur:
        records = _columns(cur, 'engine_decision_records')
        inputs = _columns(cur, 'engine_inputs')
        outcomes = _columns(cur, 'engine_outcomes')
    assert records['record']['Type'] == 'json' and records['record']['Null'] == 'NO'
    assert records['record_hash']['Type'] == 'char(71)'
    assert inputs['body']['Type'] == 'json' and inputs['body']['Null'] == 'NO'
    assert outcomes['outcome_state']['Default'] == 'pending'


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def test_a_second_whole_plan_state_on_one_machine_is_refused(db_connection, scope,
                                                             test_creator_fk):
    with db_connection.cursor() as cur:
        _insert_state(cur, scope, test_creator_fk)
    db_connection.commit()
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            _insert_state(cur, scope, test_creator_fk)
    db_connection.rollback()
    assert exc.value.args[0] == 1062
    assert 'uq_engine_states_scope' in str(exc.value.args[1])


def test_an_initiative_scope_beside_the_whole_plan_scope_is_allowed(db_connection, scope,
                                                              test_creator_fk):
    with db_connection.cursor() as cur:
        _insert_state(cur, scope, test_creator_fk)
        _insert_state(cur, scope, test_creator_fk, initiative=scope['initiative'])
    db_connection.commit()


def test_a_desired_flip_never_stamps_a_heartbeat(db_connection, scope, test_creator_fk):
    """The reason the heartbeat is its own table: ON UPDATE CURRENT_TIMESTAMP
    fires on ANY changed column, so a desired-state flip on a shared row would
    make a dead engine read alive."""
    with db_connection.cursor() as cur:
        state_id = _insert_state(cur, scope, test_creator_fk)
        cur.execute("INSERT INTO engine_heartbeats (engine_state_fk, creator_fk) "
                    "VALUES (%s, %s)", (state_id, test_creator_fk))
        cur.execute("UPDATE engine_states SET desired_state = 'on' WHERE id = %s",
                    (state_id,))
        cur.execute("SELECT beat_at FROM engine_heartbeats WHERE engine_state_fk = %s",
                    (state_id,))
        assert cur.fetchone()['beat_at'] is None
        cur.execute("UPDATE engine_heartbeats SET beats = beats + 1 "
                    "WHERE engine_state_fk = %s", (state_id,))
        cur.execute("SELECT beat_at FROM engine_heartbeats WHERE engine_state_fk = %s",
                    (state_id,))
        assert cur.fetchone()['beat_at'] is not None
    db_connection.commit()


def test_record_json_reads_back_equal(db_connection, scope, test_creator_fk):
    record = {'schema': 'engine2.decision_record/1', 'queue': [{'step_id': 1,
              'requirement_id': 2, 'code': 'ADMITTED', 'detail': None}],
              'cut': 1, 'outcomes': {'2': {'state': 'pending', 'session_ids': []}},
              'cycle': {'seq': 1, 'now': '2026-10-22T07:00:00Z'}}
    with db_connection.cursor() as cur:
        record_id = _insert_record(cur, scope, test_creator_fk, record)
        cur.execute("SELECT record FROM engine_decision_records WHERE id = %s", (record_id,))
        assert json.loads(cur.fetchone()['record']) == record
    db_connection.commit()


def test_a_record_hash_is_unique_per_creator(db_connection, scope, test_creator_fk):
    with db_connection.cursor() as cur:
        _insert_record(cur, scope, test_creator_fk, {})
    db_connection.commit()
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            _insert_record(cur, scope, test_creator_fk, {})
    db_connection.rollback()
    assert exc.value.args[0] == 1062


def test_an_outcome_dies_with_its_record(db_connection, scope, test_creator_fk):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO requirements (title, category_fk, creator_fk) "
                    "SELECT 'eng-outcome', category_fk, %s FROM initiatives WHERE id = %s",
                    (test_creator_fk, scope['initiative']))
        req_id = cur.lastrowid
        record_id = _insert_record(cur, scope, test_creator_fk, {})
        cur.execute("INSERT INTO engine_outcomes (record_fk, requirement_fk, creator_fk) "
                    "VALUES (%s, %s, %s)", (record_id, req_id, test_creator_fk))
        cur.execute("DELETE FROM engine_decision_records WHERE id = %s", (record_id,))
        cur.execute("SELECT COUNT(*) AS n FROM engine_outcomes WHERE record_fk = %s",
                    (record_id,))
        assert cur.fetchone()['n'] == 0
        cur.execute("DELETE FROM requirements WHERE id = %s", (req_id,))
    db_connection.commit()


def test_an_input_hash_is_stored_once_per_creator(db_connection, test_creator_fk):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO engine_inputs (content_hash, input_kind, body, creator_fk) "
                    "VALUES (%s, 'clock', %s, %s)", (HASH, '{"now": "x"}', test_creator_fk))
    db_connection.commit()
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("INSERT INTO engine_inputs (content_hash, input_kind, body, creator_fk) "
                        "VALUES (%s, 'clock', %s, %s)", (HASH, '{"now": "x"}', test_creator_fk))
    db_connection.rollback()
    assert exc.value.args[0] == 1062
