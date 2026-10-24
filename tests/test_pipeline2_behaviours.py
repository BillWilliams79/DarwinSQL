"""Pipeline 2.0 plan-layer schema behaviours (req #3337).

# COVERS: SCH-001, SCH-002, SCH-003, SCH-004, SCH-005, SCH-006, SCH-007,
# COVERS: SCH-008, SCH-010, SCH-011, SCH-012, SCH-030, SCH-036, SCH-040

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
# Fixture graph: project -> category -> pipelines -> initiatives
# -> epics, plus one requirement to link/gate with.
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
        cur.execute("INSERT INTO initiatives (pipeline_fk, title, category_fk, "
                    "creator_fk) VALUES (%s, %s, %s, %s)",
                    (ids['pipeline'], f'p2-initiative-{uuid.uuid4().hex[:8]}',
                     ids['category'], test_creator_fk))
        ids['initiative'] = cur.lastrowid
        cur.execute("INSERT INTO epics (initiative_fk, title, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (ids['initiative'], f'p2-epic-a-{uuid.uuid4().hex[:8]}', test_creator_fk))
        ids['epic_a'] = cur.lastrowid
        cur.execute("INSERT INTO epics (initiative_fk, title, creator_fk) "
                    "VALUES (%s, %s, %s)",
                    (ids['initiative'], f'p2-epic-b-{uuid.uuid4().hex[:8]}', test_creator_fk))
        ids['epic_b'] = cur.lastrowid
    db_connection.commit()

    yield ids

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM initiative_deps WHERE initiative_fk IN "
                    "(SELECT id FROM initiatives WHERE creator_fk = %s) "
                    "OR dep_initiative_fk IN "
                    "(SELECT id FROM initiatives WHERE creator_fk = %s)",
                    (test_creator_fk, test_creator_fk))
        cur.execute("DELETE FROM epic_deps WHERE epic_fk IN "
                    "(SELECT id FROM epics WHERE creator_fk = %s) "
                    "OR dep_epic_fk IN "
                    "(SELECT id FROM epics WHERE creator_fk = %s)",
                    (test_creator_fk, test_creator_fk))
        cur.execute("DELETE FROM epic_requirements WHERE epic_fk IN "
                    "(SELECT id FROM epics WHERE creator_fk = %s) "
                    "OR requirement_fk IN "
                    "(SELECT id FROM requirements WHERE creator_fk = %s)",
                    (test_creator_fk, test_creator_fk))
        cur.execute("DELETE FROM epics WHERE creator_fk = %s", (test_creator_fk,))
        cur.execute("DELETE FROM initiatives WHERE creator_fk = %s", (test_creator_fk,))
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

def test_initiative_belongs_to_exactly_one_pipeline(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'initiatives')
    assert cols['pipeline_fk']['Null'] == 'NO'


def test_epic_belongs_to_exactly_one_initiative(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epics')
    assert cols['initiative_fk']['Null'] == 'NO'


def test_epic_carries_no_pipeline_reference(db_connection):
    """An epic's pipeline is reached through its initiative — zero extra reads (§ 6)."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epics')
    assert 'pipeline_fk' not in cols


# ---------------------------------------------------------------------------
# SCH-004 — no epic table carries a state column
# ---------------------------------------------------------------------------

# Parametrized over both eras until req #3356 (migration 20260812175325)
# dropped `epics`; the design rule it carried forward is 2.0's now.
@pytest.mark.parametrize('table', ['epics'])
def test_no_epic_table_carries_a_state_column(db_connection, table):
    with db_connection.cursor() as cur:
        cols = _columns(cur, table)
    assert 'state' not in cols and 'status' not in cols
    # req #3752 dropped the last of it: an epic has no completion stamp either.
    assert 'completed_at' not in cols


# ---------------------------------------------------------------------------
# SCH-005 — dep_epic_fk NOT NULL makes uq_p2_epic_deps a TOTAL unique key
# ---------------------------------------------------------------------------

def test_epic_deps_columns_have_no_time_gate(db_connection):
    """SCH-006: the time gate is epics.not_before, not a dep row."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epic_deps')
    assert set(cols.keys()) == {'id', 'epic_fk', 'dep_epic_fk'}
    with db_connection.cursor() as cur:
        epic_cols = _columns(cur, 'epics')
    assert 'not_before' in epic_cols
    assert epic_cols['not_before']['Null'] == 'YES'


def test_dep_epic_fk_is_not_null(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epic_deps')
    assert cols['dep_epic_fk']['Null'] == 'NO'


def test_duplicate_epic_dependency_edge_is_refused(db_connection, p2_graph):
    """The UNIQUE key is TOTAL (unlike 1.0's, where a nullable dep_epic_fk lets
    MySQL treat two NULLs as distinct): a second identical edge is a 1062, not
    a silently accepted duplicate."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO epic_deps (epic_fk, dep_epic_fk) "
                    "VALUES (%s, %s)", (p2_graph['epic_a'], p2_graph['epic_b']))
    db_connection.commit()

    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("INSERT INTO epic_deps (epic_fk, dep_epic_fk) "
                        "VALUES (%s, %s)", (p2_graph['epic_a'], p2_graph['epic_b']))
    db_connection.rollback()
    assert exc.value.args[0] == 1062


# ---------------------------------------------------------------------------
# SCH-007 — epic_requirements CASCADEs on both sides: deleting a
# epic drops its links, deleting a requirement drops its seat (req #3706
# reversed the requirement side's original RESTRICT)
# ---------------------------------------------------------------------------

def test_epic_requirements_fk_actions_cascade_both_sides(db_connection):
    with db_connection.cursor() as cur:
        epic_update, epic_delete = _referential_action(cur, 'fk_er_epic')
        req_update, req_delete = _referential_action(cur, 'fk_er_requirement')
    assert (epic_update, epic_delete) == ('CASCADE', 'CASCADE')
    assert (req_update, req_delete) == ('CASCADE', 'CASCADE')


def test_deleting_a_seated_requirement_drops_its_seat_and_spares_the_epic(
        db_connection, p2_graph):
    # req #3706 — the user-reported defect: a seated requirement could not be
    # deleted (1451). It now deletes, its seat goes, the epic stays.
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO epic_requirements (epic_fk, requirement_fk) "
                    "VALUES (%s, %s)", (p2_graph['epic_a'], p2_graph['requirement']))
        cur.execute("DELETE FROM requirements WHERE id = %s", (p2_graph['requirement'],))
        cur.execute("SELECT COUNT(*) AS n FROM epic_requirements "
                    "WHERE requirement_fk = %s", (p2_graph['requirement'],))
        seats = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM epics WHERE id = %s",
                    (p2_graph['epic_a'],))
        epics = cur.fetchone()['n']
    db_connection.commit()
    assert seats == 0
    assert epics == 1


# ---------------------------------------------------------------------------
# SCH-008 — sort_order is NULLABLE, no default (stage-2 gate ruling, #3336)
# ---------------------------------------------------------------------------

def test_initiatives_sort_order_is_nullable_with_no_default(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'initiatives')
    assert cols['sort_order']['Null'] == 'YES'
    assert cols['sort_order']['Default'] is None


# ---------------------------------------------------------------------------
# SCH-010 — initiative_status (suppression) and closed (completion) are distinct
# ---------------------------------------------------------------------------

def test_initiative_status_and_closed_are_independent_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'initiatives')
    assert cols['initiative_status']['Default'] == 'active'
    assert cols['closed']['Default'] == '0'


# ---------------------------------------------------------------------------
# SCH-011 — pipeline_status keeps draft as the birth value
# ---------------------------------------------------------------------------

def test_pipeline_status_default_is_draft(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'pipelines')
    assert cols['pipeline_status']['Default'] == 'draft'


# ---------------------------------------------------------------------------
# SCH-040 — req #3649: every epic is born a CHECKPOINT, nothing is born LOCKED
# ---------------------------------------------------------------------------

def test_checkpoint_defaults_on_and_locked_defaults_off(db_connection):
    with db_connection.cursor() as cur:
        epics = _columns(cur, 'epics')
        initiatives = _columns(cur, 'initiatives')
        pipelines = _columns(cur, 'pipelines')
    assert epics['checkpoint']['Default'] == '1'
    assert epics['checkpoint']['Null'] == 'NO'
    for cols in (epics, initiatives, pipelines):
        assert cols['locked']['Default'] == '0'
        assert cols['locked']['Null'] == 'NO'


# ---------------------------------------------------------------------------
# SCH-012 — deleting a pipeline cascades initiatives -> epics -> both edge tables,
# and can never delete a requirement
# ---------------------------------------------------------------------------

def test_deleting_a_pipeline_cascades_and_spares_the_requirement(db_connection, p2_graph):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO epic_requirements (epic_fk, requirement_fk) "
                    "VALUES (%s, %s)", (p2_graph['epic_a'], p2_graph['requirement']))
        cur.execute("INSERT INTO epic_deps (epic_fk, dep_epic_fk) "
                    "VALUES (%s, %s)", (p2_graph['epic_a'], p2_graph['epic_b']))
    db_connection.commit()

    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM pipelines WHERE id = %s", (p2_graph['pipeline'],))
    db_connection.commit()

    with db_connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM initiatives WHERE id = %s",
                    (p2_graph['initiative'],))
        assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM epics WHERE id IN (%s, %s)",
                    (p2_graph['epic_a'], p2_graph['epic_b']))
        assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM epic_requirements "
                    "WHERE epic_fk = %s", (p2_graph['epic_a'],))
        assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM epic_deps WHERE epic_fk = %s",
                    (p2_graph['epic_a'],))
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
    ('initiatives', 'pipeline_fk'),
    ('epics', 'initiative_fk'),
    ('epic_deps', 'dep_epic_fk'),
    # Not a CREATE INDEX line — the gate-delta PRIMARY KEY (requirement_fk)
    # alone already serves this lookup, which is why ix_p2_psr_requirement_fk
    # does not exist. A future migration re-adding it alongside the PK would
    # be the fourth duplicate the record's § 3.1 measurement excluded.
    ('epic_requirements', 'requirement_fk'),
])
def test_explicit_index_is_not_duplicated_by_the_fk_auto_index(db_connection, table, column):
    """Measured 2026-08-08 against darwin_dev after the migration 20260808115509
    apply: each of these four columns carries exactly ONE index with it as the
    leftmost column — mirroring 1.0's identical measured behaviour on
    epics/epic_deps/epic_requirements. A second entry
    here would mean a future migration re-introduced a duplicate."""
    with db_connection.cursor() as cur:
        n = _index_count_as_leftmost(cur, table, column)
    assert n == 1, f'{table}.{column}: expected exactly 1 leftmost index, found {n}'


# ---------------------------------------------------------------------------
# SCH-036 — epic_requirements PK is requirement_fk ALONE (stage-2
# gate ruling, req #3336 §9): a requirement exists on at most one epic,
# structurally.
# ---------------------------------------------------------------------------

def test_epic_requirements_primary_key_is_requirement_fk_alone(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("SHOW KEYS FROM epic_requirements WHERE Key_name = 'PRIMARY'")
        pk_cols = [r['Column_name'] for r in cur.fetchall()]
    assert pk_cols == ['requirement_fk']
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'epic_requirements')
    assert cols['epic_fk']['Null'] == 'NO'
    assert cols['epic_fk']['Key'] != 'PRI'


def test_a_requirement_cannot_be_seated_on_two_epics(db_connection, p2_graph):
    """The structural proof: seating the SAME requirement on a second epic is a
    1062 on the PRIMARY KEY, not a silently accepted second row — this is what
    'duplicate it if you need to run 2' (the user ruling) is enforcing against."""
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO epic_requirements (epic_fk, requirement_fk) "
                    "VALUES (%s, %s)", (p2_graph['epic_a'], p2_graph['requirement']))
    db_connection.commit()

    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("INSERT INTO epic_requirements (epic_fk, requirement_fk) "
                        "VALUES (%s, %s)", (p2_graph['epic_b'], p2_graph['requirement']))
    db_connection.rollback()
    assert exc.value.args[0] == 1062


# ---------------------------------------------------------------------------
# req #3823 — initiative_deps: one row = one edge, CASCADE on the waiting side,
# RESTRICT on the side waited for (design rule 4, as on epic_deps)
# ---------------------------------------------------------------------------

def _second_initiative(db_connection, p2_graph, test_creator_fk):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO initiatives (pipeline_fk, title, category_fk, "
                    "creator_fk) VALUES (%s, %s, %s, %s)",
                    (p2_graph['pipeline'], f'p2-initiative-b-{uuid.uuid4().hex[:8]}',
                     p2_graph['category'], test_creator_fk))
        initiative_b = cur.lastrowid
        cur.execute("INSERT INTO initiative_deps (initiative_fk, dep_initiative_fk) "
                    "VALUES (%s, %s)", (initiative_b, p2_graph['initiative']))
    db_connection.commit()
    return initiative_b


def test_initiative_deps_referential_actions(db_connection):
    with db_connection.cursor() as cur:
        assert _referential_action(cur, 'fk_id_initiative') == ('CASCADE', 'CASCADE')
        assert _referential_action(cur, 'fk_id_dep_initiative') == ('CASCADE', 'RESTRICT')
        cols = _columns(cur, 'initiative_deps')
    assert cols['initiative_fk']['Null'] == 'NO'
    assert cols['dep_initiative_fk']['Null'] == 'NO'


def test_initiative_deps_unique_edge(db_connection, p2_graph, test_creator_fk):
    initiative_b = _second_initiative(db_connection, p2_graph, test_creator_fk)
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("INSERT INTO initiative_deps (initiative_fk, dep_initiative_fk) "
                        "VALUES (%s, %s)", (initiative_b, p2_graph['initiative']))
    db_connection.rollback()
    assert exc.value.args[0] == 1062


def test_an_initiative_waited_on_cannot_be_deleted(db_connection, p2_graph, test_creator_fk):
    _second_initiative(db_connection, p2_graph, test_creator_fk)
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("DELETE FROM initiatives WHERE id = %s", (p2_graph['initiative'],))
    db_connection.rollback()
    assert exc.value.args[0] == 1451


def test_deleting_the_waiting_initiative_takes_its_edges(db_connection, p2_graph, test_creator_fk):
    initiative_b = _second_initiative(db_connection, p2_graph, test_creator_fk)
    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM initiatives WHERE id = %s", (initiative_b,))
    db_connection.commit()
    with db_connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM initiative_deps WHERE initiative_fk = %s",
                    (initiative_b,))
        assert cur.fetchone()['n'] == 0


def test_pipeline_delete_needs_its_initiative_edges_cleared_first(
        db_connection, p2_graph, test_creator_fk):
    """MEASURED: InnoDB's cascade from `pipelines` does NOT clear an edge whose
    both ends it is deleting — the RESTRICT side refuses (1451), exactly as
    `epic_deps` does. So every pipeline delete clears `initiative_deps` first
    (darwin-mcp `delete_pipeline`, the browser's `deletePipeline`)."""
    _second_initiative(db_connection, p2_graph, test_creator_fk)
    with pytest.raises(pymysql.err.IntegrityError) as exc:
        with db_connection.cursor() as cur:
            cur.execute("DELETE FROM pipelines WHERE id = %s", (p2_graph['pipeline'],))
    db_connection.rollback()
    assert exc.value.args[0] == 1451
    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM initiative_deps WHERE initiative_fk IN "
                    "(SELECT id FROM initiatives WHERE pipeline_fk = %s)",
                    (p2_graph['pipeline'],))
        cur.execute("DELETE FROM pipelines WHERE id = %s", (p2_graph['pipeline'],))
    db_connection.commit()
