"""Pipeline 2.0 plan-layer schema behaviours (req #3337).

# COVERS: SCH-001, SCH-002, SCH-003, SCH-004, SCH-005, SCH-006, SCH-007,
# COVERS: SCH-008, SCH-010, SCH-011, SCH-012, SCH-030, SCH-036

Structural (DESCRIBE / SHOW INDEX / information_schema) and functional
(insert/delete against real rows) proof for the behaviours stated by
`memory/pipeline-2-data-architecture.md` § 3 and the stage-2 gate deltas
(req #3336) for the five `pipeline2_*` tables created by migration
20260808115509. Runs against `darwin_dev`, the only database this
requirement touches.
"""
import uuid

import pymysql
import pytest


def _columns(cur, table):
    cur.execute(f"DESCRIBE {table}")
    return {row['Field']: row for row in cur.fetchall()}


def _referential_action(cur, constraint_name):
    """(UPDATE_RULE, DELETE_RULE) for a named FK constraint in darwin_dev."""
    cur.execute(
        "SELECT UPDATE_RULE, DELETE_RULE FROM "
        "INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = 'darwin_dev' AND CONSTRAINT_NAME = %s",
        (constraint_name,))
    row = cur.fetchone()
    assert row, f'{constraint_name} not found in darwin_dev'
    return row['UPDATE_RULE'], row['DELETE_RULE']


# ---------------------------------------------------------------------------
# Fixture graph: project -> category -> pipelines -> epics
# -> pipeline_steps, plus one requirement to link/gate with.
# ---------------------------------------------------------------------------

@pytest.fixture
def p2_graph(db_connection, test_creator_fk):
    """One owned row per table, built fresh per test and torn down after.

    Function-scoped (not module-scoped) because several tests below mutate or
    delete rows in this graph (SCH-005's duplicate-edge probe, SCH-012's
    cascade-delete probe, SCH-036's duplicate-requirement probe).
    """
    ids = {}
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO projects (project_name, creator_fk) VALUES (%s, %s)",
                    (f'p2-proj-{uuid.uuid4().hex[:8]}', test_creator_fk))
        ids['project'] = cur.lastrowid
        cur.execute("INSERT INTO categories (category_name, project_fk, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (f'p2-cat-{uuid.uuid4().hex[:8]}', ids['project'], test_creator_fk))
        ids['category'] = cur.lastrowid
        cur.execute("INSERT INTO requirements (title, category_fk, creator_fk, "
                    "ai_model, effort) VALUES (%s, %s, %s, 'opus', 'high')",
                    (f'p2-req-{uuid.uuid4().hex[:8]}', ids['category'], test_creator_fk))
        ids['requirement'] = cur.lastrowid
        cur.execute("INSERT INTO pipelines (title, creator_fk) VALUES (%s, %s)",
                    (f'p2-pipeline-{uuid.uuid4().hex[:8]}', test_creator_fk))
        ids['pipeline'] = cur.lastrowid
        cur.execute("INSERT INTO epics (pipeline_fk, title, category_fk, "
                    "creator_fk) VALUES (%s, %s, %s, %s)",
                    (ids['pipeline'], f'p2-epic-{uuid.uuid4().hex[:8]}',
                     ids['category'], test_creator_fk))
        ids['epic'] = cur.lastrowid
        cur.execute("INSERT INTO pipeline_steps (epic_fk, title, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (ids['epic'], f'p2-step-a-{uuid.uuid4().hex[:8]}', test_creator_fk))
        ids['step_a'] = cur.lastrowid
        cur.execute("INSERT INTO pipeline_steps (epic_fk, title, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (ids['epic'], f'p2-step-b-{uuid.uuid4().hex[:8]}', test_creator_fk))
        ids['step_b'] = cur.lastrowid
    db_connection.commit()

    yield ids

    with db_connection.cursor() as cur:
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
        cur.execute("DELETE FROM requirements WHERE creator_fk = %s AND id = %s",
                    (test_creator_fk, ids['requirement']))
        cur.execute("DELETE FROM categories WHERE creator_fk = %s AND id = %s",
                    (test_creator_fk, ids['category']))
        cur.execute("DELETE FROM projects WHERE creator_fk = %s AND id = %s",
                    (test_creator_fk, ids['project']))
    db_connection.commit()


# ---------------------------------------------------------------------------
# SCH-001 / SCH-002 / SCH-003 — containment is in the DDL
# ---------------------------------------------------------------------------

def test_epic_belongs_to_exactly_one_pipeline(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epics')
    assert cols['pipeline_fk']['Null'] == 'NO'


def test_step_belongs_to_exactly_one_epic(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipeline_steps')
    assert cols['epic_fk']['Null'] == 'NO'


def test_step_carries_no_pipeline_reference(db_connection):
    """A step's pipeline is reached through its epic — zero extra reads (§ 6)."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipeline_steps')
    assert 'pipeline_fk' not in cols


# ---------------------------------------------------------------------------
# SCH-004 — no step table carries a state column
# ---------------------------------------------------------------------------

# Parametrized over both eras until req #3356 (migration 20260812175325)
# dropped `pipeline_steps`; the design rule it carried forward is 2.0's now.
@pytest.mark.parametrize('table', ['pipeline_steps'])
def test_no_step_table_carries_a_state_column(db_connection, table):
    with db_connection.cursor() as cur:
        cols = _columns(cur, table)
    assert 'state' not in cols and 'status' not in cols


# ---------------------------------------------------------------------------
# SCH-005 — dep_step_fk NOT NULL makes uq_p2_step_deps a TOTAL unique key
# ---------------------------------------------------------------------------

def test_step_deps_columns_have_no_time_gate(db_connection):
    """SCH-006: the time gate is pipeline_steps.not_before, not a dep row."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipeline_step_deps')
    assert set(cols.keys()) == {'id', 'step_fk', 'dep_step_fk'}
    with db_connection.cursor() as cur:
        step_cols = _columns(cur, 'pipeline_steps')
    assert 'not_before' in step_cols
    assert step_cols['not_before']['Null'] == 'YES'


def test_dep_step_fk_is_not_null(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipeline_step_deps')
    assert cols['dep_step_fk']['Null'] == 'NO'


def test_duplicate_step_dependency_edge_is_refused(db_connection, p2_graph):
    """The UNIQUE key is TOTAL (unlike 1.0's, where a nullable dep_step_fk lets
    MySQL treat two NULLs as distinct): a second identical edge is a 1062, not
    a silently accepted duplicate."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) "
                    "VALUES (%s, %s)", (p2_graph['step_a'], p2_graph['step_b']))
    db_connection.commit()

    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) "
                        "VALUES (%s, %s)", (p2_graph['step_a'], p2_graph['step_b']))
    db_connection.rollback()
    assert exc.value.args[0] == 1062


# ---------------------------------------------------------------------------
# SCH-007 — pipeline_step_requirements is asymmetric: step_fk CASCADE,
# requirement_fk RESTRICT
# ---------------------------------------------------------------------------

def test_step_requirements_fk_actions_are_asymmetric(db_connection):
    with db_connection.cursor() as cur:
        step_update, step_delete = _referential_action(cur, 'fk_p2_psr_step')
        req_update, req_delete = _referential_action(cur, 'fk_p2_psr_requirement')
    assert (step_update, step_delete) == ('CASCADE', 'CASCADE')
    assert (req_update, req_delete) == ('CASCADE', 'RESTRICT')


# ---------------------------------------------------------------------------
# SCH-008 — sort_order is NULLABLE, no default (stage-2 gate ruling, #3336)
# ---------------------------------------------------------------------------

def test_epics_sort_order_is_nullable_with_no_default(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epics')
    assert cols['sort_order']['Null'] == 'YES'
    assert cols['sort_order']['Default'] is None


# ---------------------------------------------------------------------------
# SCH-010 — epic_status (suppression) and closed (completion) are distinct
# ---------------------------------------------------------------------------

def test_epic_status_and_closed_are_independent_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epics')
    assert cols['epic_status']['Default'] == 'active'
    assert cols['closed']['Default'] == '0'


# ---------------------------------------------------------------------------
# SCH-011 — pipeline_status keeps draft as the birth value
# ---------------------------------------------------------------------------

def test_pipeline_status_default_is_draft(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipelines')
    assert cols['pipeline_status']['Default'] == 'draft'


# ---------------------------------------------------------------------------
# SCH-012 — deleting a pipeline cascades epics -> steps -> both edge tables,
# and can never delete a requirement
# ---------------------------------------------------------------------------

def test_deleting_a_pipeline_cascades_and_spares_the_requirement(db_connection, p2_graph):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (p2_graph['step_a'], p2_graph['requirement']))
        cur.execute("INSERT INTO pipeline_step_deps (step_fk, dep_step_fk) "
                    "VALUES (%s, %s)", (p2_graph['step_a'], p2_graph['step_b']))
    db_connection.commit()

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM pipelines WHERE id = %s", (p2_graph['pipeline'],))
    db_connection.commit()

    with db_connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM epics WHERE id = %s",
                    (p2_graph['epic'],))
        assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM pipeline_steps WHERE id IN (%s, %s)",
                    (p2_graph['step_a'], p2_graph['step_b']))
        assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM pipeline_step_requirements "
                    "WHERE step_fk = %s", (p2_graph['step_a'],))
        assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM pipeline_step_deps WHERE step_fk = %s",
                    (p2_graph['step_a'],))
        assert cur.fetchone()['n'] == 0
        # The requirement itself is untouched — containment stops at Requirement.
        cur.execute("SELECT COUNT(*) AS n FROM requirements WHERE id = %s",
                    (p2_graph['requirement'],))
        assert cur.fetchone()['n'] == 1


# ---------------------------------------------------------------------------
# SCH-030 — the explicit CREATE INDEX lines were measured, not assumed, and
# none duplicates an FK-auto-created index
# ---------------------------------------------------------------------------

def _index_count_as_leftmost(cur, table, column):
    cur.execute(f"SHOW INDEX FROM {table} WHERE Column_name = %s AND Seq_in_index = 1",
                (column,))
    return len(cur.fetchall())


@pytest.mark.parametrize('table,column', [
    ('epics', 'pipeline_fk'),
    ('pipeline_steps', 'epic_fk'),
    ('pipeline_step_deps', 'dep_step_fk'),
    # Not a CREATE INDEX line — the gate-delta PRIMARY KEY (requirement_fk)
    # alone already serves this lookup, which is why ix_p2_psr_requirement_fk
    # does not exist. A future migration re-adding it alongside the PK would
    # be the fourth duplicate the record's § 3.1 measurement excluded.
    ('pipeline_step_requirements', 'requirement_fk'),
])
def test_explicit_index_is_not_duplicated_by_the_fk_auto_index(db_connection, table, column):
    """Measured 2026-08-08 against darwin_dev after the migration 20260808115509
    apply: each of these four columns carries exactly ONE index with it as the
    leftmost column — mirroring 1.0's identical measured behaviour on
    pipeline_steps/pipeline_step_deps/pipeline_step_requirements. A second entry
    here would mean a future migration re-introduced a duplicate."""
    with db_connection.cursor() as cur:
        n = _index_count_as_leftmost(cur, table, column)
    assert n == 1, f'{table}.{column}: expected exactly 1 leftmost index, found {n}'


# ---------------------------------------------------------------------------
# SCH-036 — pipeline_step_requirements PK is requirement_fk ALONE (stage-2
# gate ruling, req #3336 §9): a requirement exists on at most one step,
# structurally.
# ---------------------------------------------------------------------------

def test_step_requirements_primary_key_is_requirement_fk_alone(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SHOW KEYS FROM pipeline_step_requirements WHERE Key_name = 'PRIMARY'")
        pk_cols = [r['Column_name'] for r in cur.fetchall()]
    assert pk_cols == ['requirement_fk']
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipeline_step_requirements')
    assert cols['step_fk']['Null'] == 'NO'
    assert cols['step_fk']['Key'] != 'PRI'


def test_a_requirement_cannot_be_seated_on_two_steps(db_connection, p2_graph):
    """The structural proof: seating the SAME requirement on a second step is a
    1062 on the PRIMARY KEY, not a silently accepted second row — this is what
    'duplicate it if you need to run 2' (the user ruling) is enforcing against."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                    "VALUES (%s, %s)", (p2_graph['step_a'], p2_graph['requirement']))
    db_connection.commit()

    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("INSERT INTO pipeline_step_requirements (step_fk, requirement_fk) "
                        "VALUES (%s, %s)", (p2_graph['step_b'], p2_graph['requirement']))
    db_connection.rollback()
    assert exc.value.args[0] == 1062
