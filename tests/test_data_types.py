"""
Test data type definitions and schema correctness.

Verifies that DESCRIBE output for each table matches the expected schema.sql
definitions. Uses darwin_dev test database (profiles, domains, areas, tasks).
"""

import os
import re

import pytest


def test_profiles_columns(db_connection):
    """Verify profiles column definitions match schema.sql.

    Expected columns (post migration 026 + app_solar + migration 050):
    - id: VARCHAR(64), PRI, NOT NULL
    - name: VARCHAR(256), NOT NULL
    - email: VARCHAR(256), NOT NULL
    - timezone: VARCHAR(64), NULL
    - theme_mode: VARCHAR(8), NOT NULL, DEFAULT 'light'
    - app_tasks: TINYINT(1), NOT NULL, DEFAULT 1
    - app_maps: TINYINT(1), NOT NULL, DEFAULT 1
    - app_swarm: TINYINT(1), NOT NULL, DEFAULT 0
    - app_solar: TINYINT(1), NOT NULL, DEFAULT 0
    - app_swarm_validate: TINYINT(1), NOT NULL, DEFAULT 0  (req #2611, migration 050)
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE profiles")
        columns = {row['Field']: row for row in cur.fetchall()}

    # Verify all expected columns exist
    expected_fields = ['id', 'name', 'email', 'timezone', 'theme_mode',
                       'app_tasks', 'app_maps', 'app_swarm', 'app_solar',
                       'app_swarm_validate',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    # id: VARCHAR(64), PRI
    assert columns['id']['Type'] == 'varchar(64)'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'

    # name: VARCHAR(256), NOT NULL
    assert columns['name']['Type'] == 'varchar(256)'
    assert columns['name']['Null'] == 'NO'

    # email: VARCHAR(256), NOT NULL
    assert columns['email']['Type'] == 'varchar(256)'
    assert columns['email']['Null'] == 'NO'

    # timezone: VARCHAR(64), NULL
    assert columns['timezone']['Type'] == 'varchar(64)'
    assert columns['timezone']['Null'] == 'YES'

    # theme_mode: VARCHAR(8), NOT NULL, DEFAULT 'light'
    assert columns['theme_mode']['Type'] == 'varchar(8)'
    assert columns['theme_mode']['Null'] == 'NO'
    assert columns['theme_mode']['Default'] == 'light'

    # app_tasks: TINYINT(1), NOT NULL, DEFAULT 1
    assert 'tinyint' in columns['app_tasks']['Type']
    assert columns['app_tasks']['Null'] == 'NO'
    assert columns['app_tasks']['Default'] == '1'

    # app_maps: TINYINT(1), NOT NULL, DEFAULT 1
    assert 'tinyint' in columns['app_maps']['Type']
    assert columns['app_maps']['Null'] == 'NO'
    assert columns['app_maps']['Default'] == '1'

    # app_swarm: TINYINT(1), NOT NULL, DEFAULT 0
    assert 'tinyint' in columns['app_swarm']['Type']
    assert columns['app_swarm']['Null'] == 'NO'
    assert columns['app_swarm']['Default'] == '0'

    # app_solar: TINYINT(1), NOT NULL, DEFAULT 0
    assert 'tinyint' in columns['app_solar']['Type']
    assert columns['app_solar']['Null'] == 'NO'
    assert columns['app_solar']['Default'] == '0'

    # app_swarm_validate: TINYINT(1), NOT NULL, DEFAULT 0  (req #2611)
    assert 'tinyint' in columns['app_swarm_validate']['Type']
    assert columns['app_swarm_validate']['Null'] == 'NO'
    assert columns['app_swarm_validate']['Default'] == '0'

    # create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    # update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_domains_columns(db_connection):
    """Verify domains column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - domain_name: VARCHAR(32), NOT NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - closed: TINYINT, NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE domains")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'domain_name', 'creator_fk', 'closed', 'sort_order', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # domain_name: VARCHAR(32), NOT NULL
    assert columns['domain_name']['Type'] == 'varchar(32)'
    assert columns['domain_name']['Null'] == 'NO'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # closed: TINYINT, NOT NULL, DEFAULT 0
    assert columns['closed']['Type'] == 'tinyint'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    # sort_order: SMALLINT, NULL
    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    # create_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    # update_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_areas_columns(db_connection):
    """Verify areas column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - area_name: VARCHAR(32), NOT NULL
    - domain_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - closed: TINYINT, NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'priority'
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE areas")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'area_name', 'domain_fk', 'creator_fk', 'closed', 'sort_order',
        'sort_mode', 'create_ts', 'update_ts'
    ]
    assert set(columns.keys()) == set(expected_fields)

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # area_name: VARCHAR(32), NOT NULL
    assert columns['area_name']['Type'] == 'varchar(32)'
    assert columns['area_name']['Null'] == 'NO'

    # domain_fk: INT, NULL, MUL
    assert columns['domain_fk']['Type'] == 'int'
    assert columns['domain_fk']['Null'] == 'YES'
    assert columns['domain_fk']['Key'] == 'MUL'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # closed: TINYINT, NOT NULL, DEFAULT 0
    assert columns['closed']['Type'] == 'tinyint'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    # sort_order: SMALLINT, NULL
    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    # sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'priority'
    assert columns['sort_mode']['Type'] == 'varchar(8)'
    assert columns['sort_mode']['Null'] == 'NO'
    assert columns['sort_mode']['Default'] == 'priority'

    # create_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    # update_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'


def test_tasks_columns(db_connection):
    """Verify tasks column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - priority: TINYINT(1), NOT NULL (BOOLEAN is TINYINT(1) in MySQL)
    - done: TINYINT(1), NOT NULL
    - description: VARCHAR(1024), NOT NULL
    - area_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    - done_ts: TIMESTAMP, NULL
    - sort_order: SMALLINT, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE tasks")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'priority', 'done', 'description', 'area_fk', 'creator_fk',
        'create_ts', 'update_ts', 'done_ts', 'sort_order', 'recurring_task_fk'
    ]
    assert set(columns.keys()) == set(expected_fields)

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # priority: TINYINT(1), NOT NULL (MySQL BOOLEAN = TINYINT(1))
    assert 'tinyint' in columns['priority']['Type'].lower()
    assert columns['priority']['Null'] == 'NO'

    # done: TINYINT(1), NOT NULL
    assert 'tinyint' in columns['done']['Type'].lower()
    assert columns['done']['Null'] == 'NO'

    # description: VARCHAR(1024), NOT NULL
    assert columns['description']['Type'] == 'varchar(1024)'
    assert columns['description']['Null'] == 'NO'

    # area_fk: INT, NULL, MUL
    assert columns['area_fk']['Type'] == 'int'
    assert columns['area_fk']['Null'] == 'YES'
    assert columns['area_fk']['Key'] == 'MUL'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # create_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'

    # update_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'

    # done_ts: TIMESTAMP, NULL
    assert 'timestamp' in columns['done_ts']['Type']
    assert columns['done_ts']['Null'] == 'YES'

    # sort_order: SMALLINT, NULL
    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    # recurring_task_fk: INT, NULL, MUL
    assert columns['recurring_task_fk']['Type'] == 'int'
    assert columns['recurring_task_fk']['Null'] == 'YES'
    assert columns['recurring_task_fk']['Key'] == 'MUL'


def test_projects_columns(db_connection):
    """Verify projects column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - project_name: VARCHAR(128), NOT NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - sort_order: SMALLINT, NULL
    - closed: TINYINT(1), NOT NULL, DEFAULT 0
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE projects")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'project_name', 'creator_fk', 'sort_order', 'closed',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['project_name']['Type'] == 'varchar(128)'
    assert columns['project_name']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert 'tinyint' in columns['closed']['Type']
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_categories_columns(db_connection):
    """Verify categories column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - category_name: VARCHAR(128), NOT NULL
    - project_fk: INT, NOT NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - sort_order: SMALLINT, NULL
    - sort_mode: VARCHAR(8), NOT NULL, DEFAULT 'hand'
    - color: VARCHAR(9), NULL
    - closed: TINYINT(1), NOT NULL, DEFAULT 0
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE categories")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'category_name', 'project_fk', 'creator_fk',
                       'sort_order', 'sort_mode', 'color', 'closed', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['category_name']['Type'] == 'varchar(128)'
    assert columns['category_name']['Null'] == 'NO'

    assert columns['project_fk']['Type'] == 'int'
    assert columns['project_fk']['Null'] == 'NO'
    assert columns['project_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert columns['sort_mode']['Type'] == 'varchar(8)'
    assert columns['sort_mode']['Null'] == 'NO'
    assert columns['sort_mode']['Default'] == 'hand'

    assert columns['color']['Type'] == 'varchar(9)'
    assert columns['color']['Null'] == 'YES'

    assert 'tinyint' in columns['closed']['Type']
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'


def test_requirements_columns(db_connection):
    """Verify requirements column definitions match schema.sql.

    Expected columns (migration 046 re-adds sort_order; req #2417;
    migration 048 adds affected_repos; req #2583):
    - id: INT, PRI, AUTO_INCREMENT
    - title: VARCHAR(256), NOT NULL
    - description: TEXT, NULL
    - requirement_status: VARCHAR(16), NOT NULL, DEFAULT 'authoring'
    - started_at: TIMESTAMP, NULL
    - completed_at: TIMESTAMP, NULL
    - deferred_at: TIMESTAMP, NULL
    - project_fk: INT, NULL, MUL
    - category_fk: INT, NULL, MUL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    - coordination_type: VARCHAR(16), NOT NULL, DEFAULT 'implemented' (mandatory, req #2745)
    - ai_model: VARCHAR(16), NOT NULL, DEFAULT 'opus'  (req #2909 — haiku|sonnet|opus|fable)
    - sort_order: SMALLINT, NULL, DEFAULT NULL  (req #2417 — in-card hand sort)
    - affected_repos: VARCHAR(255), NULL, DEFAULT NULL  (req #2583 — per-requirement repo override)
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE requirements")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'title', 'description', 'requirement_status',
                       'started_at', 'completed_at', 'deferred_at', 'project_fk', 'category_fk',
                       'creator_fk', 'create_ts', 'update_ts',
                       'coordination_type']
    # Tolerate both pre- and post-migration-045 state (req #2405 dropped sort_order;
    # the migration may not have landed in this DB yet). Once 045 is applied
    # everywhere, this branch can be removed.
    if 'sort_order' in columns:
        expected_fields.append('sort_order')
    # Tolerate both pre- and post-migration-048 state (req #2583 added
    # affected_repos; the migration may not have landed in this DB yet).
    if 'affected_repos' in columns:
        expected_fields.append('affected_repos')
    # Tolerate both pre- and post-migration-062 state (req #2909 added ai_model).
    if 'ai_model' in columns:
        expected_fields.append('ai_model')
    # Tolerate both pre- and post-migration-063 state (req #2916 added effort).
    if 'effort' in columns:
        expected_fields.append('effort')
    # Tolerate both pre- and post-migration-066 state (req #2978 added machine_fk).
    if 'machine_fk' in columns:
        expected_fields.append('machine_fk')
    # `feature_fk` (req #3111, migration 076 — the story tier of Epic > Feature
    # > Story) was dropped at req #3355 (migration 20260811033413), so it is no
    # longer asserted here.
    # Req #3123, migration 20260731124830 — the CONTAINER flag. Asserted
    # unconditionally rather than tolerated: the migration lands in darwin_dev
    # and production together, so no live database legitimately lacks it.
    # See test_requirements_tracking_column below for the column's own shape.
    expected_fields.append('tracking')
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['title']['Type'] == 'varchar(256)'
    assert columns['title']['Null'] == 'NO'

    assert columns['description']['Type'] == 'text'
    assert columns['description']['Null'] == 'YES'

    assert columns['requirement_status']['Type'] == 'varchar(16)'
    assert columns['requirement_status']['Null'] == 'NO'
    assert columns['requirement_status']['Default'] == 'authoring'

    assert 'timestamp' in columns['deferred_at']['Type']
    assert columns['deferred_at']['Null'] == 'YES'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'YES'

    assert 'timestamp' in columns['completed_at']['Type']
    assert columns['completed_at']['Null'] == 'YES'

    assert columns['project_fk']['Type'] == 'int'
    assert columns['project_fk']['Null'] == 'YES'
    assert columns['project_fk']['Key'] == 'MUL'

    assert columns['category_fk']['Type'] == 'int'
    assert columns['category_fk']['Null'] == 'NO'  # req #2217 / migration 041
    assert columns['category_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['coordination_type']['Type'] == 'varchar(16)'
    assert columns['coordination_type']['Null'] == 'NO'   # mandatory autonomy (req #2745)
    assert columns['coordination_type']['Default'] == 'implemented'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'
    assert columns['sort_order']['Default'] is None

    if 'affected_repos' in columns:
        assert columns['affected_repos']['Type'] == 'varchar(255)'
        assert columns['affected_repos']['Null'] == 'YES'
        assert columns['affected_repos']['Default'] is None

    if 'ai_model' in columns:
        assert columns['ai_model']['Type'] == 'varchar(16)'
        assert columns['ai_model']['Null'] == 'NO'   # mandatory model (req #2909)
        # req #3007: NO column default — the caller must provide ai_model.
        assert columns['ai_model']['Default'] is None

    if 'effort' in columns:
        assert columns['effort']['Type'] == 'varchar(16)'
        assert columns['effort']['Null'] == 'NO'   # mandatory effort (req #2916)
        # req #3007: NO column default — the caller must provide effort.
        assert columns['effort']['Default'] is None

    # req #2978 machine_fk (migration 066) — nullable FK, no default. Unlike
    # coordination_type / ai_model / effort this one is deliberately NULLable:
    # NULL is the meaningful "Any machine" value, not a missing setting.
    if 'machine_fk' in columns:
        assert columns['machine_fk']['Type'] == 'int'
        assert columns['machine_fk']['Null'] == 'YES'
        assert columns['machine_fk']['Key'] == 'MUL'
        assert columns['machine_fk']['Default'] is None


# COVERS: SWM-022
def test_swarm_sessions_columns(db_connection):
    """Verify swarm_sessions column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - branch: VARCHAR(128), NULL
    - task_name: VARCHAR(128), NULL
    - source_type: VARCHAR(16), NULL
    - source_ref: VARCHAR(64), NULL
    - title: VARCHAR(256), NULL
    - pr_url: VARCHAR(512), NULL
    - swarm_status: VARCHAR(16), NOT NULL, DEFAULT 'starting'
    - ai_model: VARCHAR(16), NOT NULL, DEFAULT 'opus'          (req #2909)
    - worktree_path: VARCHAR(512), NULL
    - started_at: TIMESTAMP, NULL
    - completed_at: TIMESTAMP, NULL
    - last_transition_at: TIMESTAMP, NULL                      (req #2332)
    - starting_secs..legacy_secs: INT, NOT NULL, DEFAULT 0     (req #2332, 8 buckets)
    - instrumented: TINYINT, NOT NULL, DEFAULT 1               (req #2332)
    - pre_pause_status: VARCHAR(16), NULL                      (req #2332)
    - pipeline_fk: INT, NULL, MUL                             (req #3350, migration 20260809081441)
    - epic_fk: INT, NULL, MUL                                 (req #3350, migration 20260809081441)
    - phase_tokens: JSON, NULL                                 (req #2839, migration 060)
    - tokens_at_last_transition: JSON, NULL                    (req #2839, migration 060)
    - start_summary: TEXT, NULL
    - complete_summary: TEXT, NULL
    - telemetry: TEXT, NULL
    - plan: TEXT, NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_sessions")
        columns = {row['Field']: row for row in cur.fetchall()}

    phase_buckets = ['starting_secs', 'waiting_secs', 'planning_secs', 'implementing_secs',
                     'review_secs', 'completion_secs', 'paused_secs', 'legacy_secs']
    expected_fields = ['id', 'branch', 'task_name', 'source_type', 'source_ref',
                       'title', 'pr_url', 'swarm_status', 'worktree_path',
                       'started_at', 'completed_at',
                       'last_transition_at'] + phase_buckets + ['instrumented', 'pre_pause_status',
                       'phase_tokens', 'tokens_at_last_transition',
                       'start_summary', 'complete_summary', 'telemetry', 'plan',
                       'creator_fk', 'create_ts', 'update_ts']
    # Tolerate both pre- and post-migration-062 state (req #2909 added ai_model).
    if 'ai_model' in columns:
        expected_fields.append('ai_model')
    # Tolerate both pre- and post-migration-063 state (req #2916 added effort).
    if 'effort' in columns:
        expected_fields.append('effort')
    # Tolerate both pre- and post-migration-064 state (req #2943 added machine_fk).
    if 'machine_fk' in columns:
        expected_fields.append('machine_fk')
    # Req #3117, migration 077 — the two flat cost-rollup columns. Tolerated the
    # same way its predecessors are, so this file stays runnable against a
    # database that has not taken 077 yet (the dev-before-production window).
    for rollup in ('wall_secs_total', 'output_tokens_total'):
        if rollup in columns:
            expected_fields.append(rollup)
    # Req #3350, migration 20260809081441 — orchestration attribution.
    # Tolerated the same way, for the same dev-before-production window.
    # (Req #3186's 1.0 pair, `pipeline_fk`/`epic_fk`, was dropped at req #3356,
    # migration 20260812175325 — asserted ABSENT below rather than tolerated
    # here, because a tolerance clause cannot tell a dropped column from a
    # re-added one.)
    for attribution in ('pipeline_fk', 'epic_fk'):
        if attribution in columns:
            expected_fields.append(attribution)
    # Req #3455, migration 20260810013244 — WHICH TERMINAL WINDOW this session's
    # worker runs in. Tolerated the same way, for the same dev-before-production
    # window (this requirement is `implemented`, so production waits for the user).
    for terminal in ('terminal_window_id', 'terminal_number'):
        if terminal in columns:
            expected_fields.append(terminal)
    # Req #3202, migration 20260808235540 — the shared telemetry envelope.
    # Tolerated the same way, for the same dev-before-production window.
    for envelope in ('wall_ms', 'tokens_input', 'tokens_cache_write',
                      'tokens_cache_read', 'tokens_output',
                      'prompt_text', 'prompt_sha256', 'prompt_chars'):
        if envelope in columns:
            expected_fields.append(envelope)
    assert set(columns.keys()) == set(expected_fields)

    # req #3343 (SWM-022): step-addressed launch execution deliberately adds no
    # column anywhere — a step is derivable from a session's requirement via
    # the plan's own membership junction (design rule 11). The exact-set
    # assertion above already proves this structurally; this one names the
    # specific column a future change must not reintroduce.
    assert 'step_fk' not in columns

    # req #3356 — the FIRST-GENERATION `pipeline_fk`/`epic_fk` pair (req #3186)
    # is GONE, dropped at migration 20260812175325. It briefly meant these two
    # column names were absent entirely; migration 20260812184333, in the same
    # requirement's second half, renamed the surviving second-generation
    # attribution pair (until then `pipeline2_fk`/`epic2_fk`) INTO these same
    # freed names. So `pipeline_fk`/`epic_fk` exist again on this table today
    # — correctly — and asserting their absence would be testing an
    # intermediate state that no longer exists. What must stay true is the
    # SHAPE, checked below: unconditionally present now (not "if present",
    # since there is only one attribution pair left to be conditional about).
    assert 'pipeline_fk' in columns
    assert 'epic_fk' in columns

    # req #3350 attribution columns — NULLable INT FKs with no default. NULL is
    # meaningful: "this session belongs to no plan / no epic", which is a real
    # answer for ad-hoc work outside any pipeline, not a missing value.
    for attribution in ('pipeline_fk', 'epic_fk'):
        assert columns[attribution]['Type'] == 'int'
        assert columns[attribution]['Null'] == 'YES'
        assert columns[attribution]['Default'] is None
        assert columns[attribution]['Key'] == 'MUL'

    # req #3117 rollup columns (migration 077) — NULLable INTs with NO default.
    # The nullability is the contract, not an accident: NULL means "not computed
    # yet" (a session predating the backfill) and 0 means "computed, and zero"
    # (no instrumentation samples). A `NOT NULL DEFAULT 0` would erase the
    # distinction the backfill uses to know what work remains.
    for rollup in ('wall_secs_total', 'output_tokens_total'):
        if rollup in columns:
            assert columns[rollup]['Type'] == 'int'
            assert columns[rollup]['Null'] == 'YES'
            assert columns[rollup]['Default'] is None

    # req #3455 terminal identity (migration 20260810013244). Both NULLable with
    # NO default, and that is the contract: NULL means NOT RECORDED — a session
    # launched before this migration, or one whose best-effort launch-time write
    # did not land. A default of any kind would fabricate a window that does not
    # exist and hand the UI a link to nowhere.
    #
    # terminal_window_id is VARCHAR, not INT, even though iTerm2's handle is
    # numeric: Windows Terminal's handle is the window NAME (`swarm-N`), the two
    # backends share this one column, and a handle is never arithmetic.
    # terminal_number is INT and is DISPLAY ONLY — positional, stale the moment a
    # window closes. Neither carries a key: nothing looks a session up BY window.
    if 'terminal_window_id' in columns:
        assert columns['terminal_window_id']['Type'] == 'varchar(64)'
        assert columns['terminal_window_id']['Null'] == 'YES'
        assert columns['terminal_window_id']['Default'] is None
    if 'terminal_number' in columns:
        assert columns['terminal_number']['Type'] == 'int'
        assert columns['terminal_number']['Null'] == 'YES'
        assert columns['terminal_number']['Default'] is None

    # req #2943 machine_fk (migration 064) — nullable FK, no default.
    if 'machine_fk' in columns:
        assert columns['machine_fk']['Type'] == 'int'
        assert columns['machine_fk']['Null'] == 'YES'
        assert columns['machine_fk']['Key'] == 'MUL'

    # req #2839 token columns (migration 060)
    assert columns['phase_tokens']['Type'] == 'json'
    assert columns['phase_tokens']['Null'] == 'YES'
    assert columns['tokens_at_last_transition']['Type'] == 'json'
    assert columns['tokens_at_last_transition']['Null'] == 'YES'

    if 'ai_model' in columns:
        assert columns['ai_model']['Type'] == 'varchar(16)'
        assert columns['ai_model']['Null'] == 'NO'   # mandatory model (req #2909)
        assert columns['ai_model']['Default'] == 'opus'

    if 'effort' in columns:
        assert columns['effort']['Type'] == 'varchar(16)'
        assert columns['effort']['Null'] == 'NO'   # mandatory effort (req #2916)
        assert columns['effort']['Default'] == 'high'

    # req #2332 phase-accumulator columns
    for b in phase_buckets:
        assert columns[b]['Type'] == 'int' and columns[b]['Null'] == 'NO' and columns[b]['Default'] == '0'
    assert columns['last_transition_at']['Type'] == 'timestamp' and columns['last_transition_at']['Null'] == 'YES'
    assert columns['instrumented']['Type'].startswith('tinyint') and columns['instrumented']['Default'] == '1'
    assert columns['pre_pause_status']['Type'] == 'varchar(16)' and columns['pre_pause_status']['Null'] == 'YES'

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['branch']['Type'] == 'varchar(128)'
    assert columns['branch']['Null'] == 'YES'

    assert columns['task_name']['Type'] == 'varchar(128)'
    assert columns['task_name']['Null'] == 'YES'

    assert columns['source_type']['Type'] == 'varchar(16)'
    assert columns['source_type']['Null'] == 'YES'

    assert columns['source_ref']['Type'] == 'varchar(64)'
    assert columns['source_ref']['Null'] == 'YES'

    assert columns['title']['Type'] == 'varchar(256)'
    assert columns['title']['Null'] == 'YES'

    assert columns['pr_url']['Type'] == 'varchar(512)'
    assert columns['pr_url']['Null'] == 'YES'

    assert columns['swarm_status']['Type'] == 'varchar(16)'
    assert columns['swarm_status']['Null'] == 'NO'
    assert columns['swarm_status']['Default'] == 'starting'

    assert columns['worktree_path']['Type'] == 'varchar(512)'
    assert columns['worktree_path']['Null'] == 'YES'

    assert columns['start_summary']['Type'] == 'text'
    assert columns['start_summary']['Null'] == 'YES'

    assert columns['complete_summary']['Type'] == 'text'
    assert columns['complete_summary']['Null'] == 'YES'

    assert columns['telemetry']['Type'] == 'text'
    assert columns['telemetry']['Null'] == 'YES'

    assert columns['plan']['Type'] == 'text'
    assert columns['plan']['Null'] == 'YES'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'


def test_requirement_sessions_columns(db_connection):
    """Verify requirement_sessions column definitions match schema.sql.

    Expected columns:
    - requirement_fk: INT, PRI, NOT NULL
    - session_fk: INT, PRI, NOT NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE requirement_sessions")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['requirement_fk', 'session_fk']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['requirement_fk']['Type'] == 'int'
    assert columns['requirement_fk']['Null'] == 'NO'
    assert columns['requirement_fk']['Key'] == 'PRI'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'NO'
    assert columns['session_fk']['Key'] == 'PRI'


# COVERS: SWM-022
def test_swarm_starts_columns(db_connection):
    """Verify swarm_starts column definitions match migration 046.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - arguments: VARCHAR(512), NULL
    - autonomy_filter: VARCHAR(16), NULL
    - auto_start: TINYINT(1), NOT NULL, DEFAULT 0
    - session_count: INT, NOT NULL, DEFAULT 0
    - ai_model: VARCHAR(16), NOT NULL, DEFAULT 'opus' (req #2949)
    - effort: VARCHAR(16), NOT NULL, DEFAULT 'high' (req #2949)
    - tokens_input / tokens_cache_write / tokens_cache_read / tokens_output: INT, NULL
    - wall_seconds: INT, NULL
    - turn_count: INT, NULL
    - start_summary: TEXT, NULL
    - telemetry: TEXT, NULL
    - started_at: TIMESTAMP, NOT NULL, DEFAULT CURRENT_TIMESTAMP
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts / update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_starts")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'arguments', 'autonomy_filter',
                       'auto_start', 'session_count', 'ai_model', 'effort',
                       'tokens_input', 'tokens_cache_write', 'tokens_cache_read',
                       'tokens_output', 'wall_seconds', 'turn_count',
                       'start_summary', 'telemetry',
                       'started_at', 'creator_fk', 'create_ts', 'update_ts']
    # Tolerate both pre- and post-migration-064 state (req #2943 added machine_fk).
    if 'machine_fk' in columns:
        expected_fields.append('machine_fk')
    # Req #3202, migration 20260808235540 — the shared telemetry envelope's
    # wall-clock unit and prompt columns (the four tokens_* columns above
    # already matched the envelope's spelling and needed no change).
    # Tolerated the same way, for the same dev-before-production window.
    for envelope in ('wall_ms', 'prompt_text', 'prompt_sha256', 'prompt_chars'):
        if envelope in columns:
            expected_fields.append(envelope)
    assert set(columns.keys()) == set(expected_fields)

    # req #3343 (SWM-022): the one swarm_starts row per invocation is the
    # step-addressed launch unit's birth record via its `arguments` column
    # (holding the typed input verbatim) — no `step_fk` column, deliberately;
    # a step is derivable through session -> requirement -> step membership.
    assert 'step_fk' not in columns

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    # req #2943 machine_fk (migration 064) — nullable FK, no default.
    if 'machine_fk' in columns:
        assert columns['machine_fk']['Type'] == 'int'
        assert columns['machine_fk']['Null'] == 'YES'
        assert columns['machine_fk']['Key'] == 'MUL'

    assert columns['arguments']['Type'] == 'varchar(512)'
    assert columns['arguments']['Null'] == 'YES'

    assert columns['autonomy_filter']['Type'] == 'varchar(16)'
    assert columns['autonomy_filter']['Null'] == 'YES'

    assert columns['auto_start']['Type'] == 'tinyint(1)'
    assert columns['auto_start']['Null'] == 'NO'
    assert columns['auto_start']['Default'] == '0'

    assert columns['session_count']['Type'] == 'int'
    assert columns['session_count']['Null'] == 'NO'
    assert columns['session_count']['Default'] == '0'

    # req #2949 — normalized, queryable copy of the telemetry blob's model/effort.
    assert columns['ai_model']['Type'] == 'varchar(16)'
    assert columns['ai_model']['Null'] == 'NO'
    assert columns['ai_model']['Default'] == 'opus'

    assert columns['effort']['Type'] == 'varchar(16)'
    assert columns['effort']['Null'] == 'NO'
    assert columns['effort']['Default'] == 'high'

    # Token / timing / count columns are NULL until skill-finalize populates them.
    for col in ('tokens_input', 'tokens_cache_write', 'tokens_cache_read',
                'tokens_output', 'wall_seconds', 'turn_count'):
        assert columns[col]['Type'] == 'int', col
        assert columns[col]['Null'] == 'YES', col

    assert columns['start_summary']['Type'] == 'text'
    assert columns['start_summary']['Null'] == 'YES'

    assert columns['telemetry']['Type'] == 'text'
    assert columns['telemetry']['Null'] == 'YES'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'


def test_swarm_start_sessions_columns(db_connection):
    """Verify swarm_start_sessions junction table column definitions.

    Expected columns:
    - swarm_start_fk: INT, PRI, NOT NULL
    - session_fk: INT, PRI, NOT NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_start_sessions")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['swarm_start_fk', 'session_fk']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['swarm_start_fk']['Type'] == 'int'
    assert columns['swarm_start_fk']['Null'] == 'NO'
    assert columns['swarm_start_fk']['Key'] == 'PRI'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'NO'
    assert columns['session_fk']['Key'] == 'PRI'


def test_swarm_undos_columns(db_connection):
    """Verify swarm_undos column definitions match migration 053 (req #2719).

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - session_fk: INT, NULL, MUL (ON DELETE SET NULL)
    - swarm_start_fk_at_undo: INT, NULL, MUL (snapshot)
    - req_id_at_undo: INT, NULL, MUL (snapshot)
    - task_name: VARCHAR(255), NULL
    - branch: VARCHAR(255), NULL
    - coordination_type: VARCHAR(16), NULL
    - reason: TEXT, NOT NULL
    - undone_at: TIMESTAMP, NOT NULL, DEFAULT CURRENT_TIMESTAMP
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts / update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_undos")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'session_fk', 'swarm_start_fk_at_undo',
                       'req_id_at_undo', 'task_name', 'branch',
                       'coordination_type', 'reason',
                       'undone_at', 'creator_fk', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'YES'

    assert columns['swarm_start_fk_at_undo']['Type'] == 'int'
    assert columns['swarm_start_fk_at_undo']['Null'] == 'YES'

    assert columns['req_id_at_undo']['Type'] == 'int'
    assert columns['req_id_at_undo']['Null'] == 'YES'

    assert columns['task_name']['Type'] == 'varchar(255)'
    assert columns['task_name']['Null'] == 'YES'

    assert columns['branch']['Type'] == 'varchar(255)'
    assert columns['branch']['Null'] == 'YES'

    assert columns['coordination_type']['Type'] == 'varchar(16)'
    assert columns['coordination_type']['Null'] == 'YES'

    assert columns['reason']['Type'] == 'text'
    assert columns['reason']['Null'] == 'NO'

    assert 'timestamp' in columns['undone_at']['Type']
    assert columns['undone_at']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'


def test_swarm_completes_columns(db_connection):
    """Verify swarm_completes column definitions match migration 058 (req #2497).

    Close-out counterpart to swarm_starts. Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - skill_name: VARCHAR(64), NOT NULL
    - coordination_type: VARCHAR(16), NULL (NULL for primary-ai-swarm-complete)
    - status: VARCHAR(16), NOT NULL, DEFAULT 'in_progress'
    - session_count: INT, NOT NULL, DEFAULT 0
    - ai_model: VARCHAR(16), NOT NULL, DEFAULT 'opus' (req #2949)
    - effort: VARCHAR(16), NOT NULL, DEFAULT 'high' (req #2949)
    - tokens_input / tokens_cache_write / tokens_cache_read / tokens_output: INT, NULL
    - wall_seconds: INT, NULL
    - turn_count: INT, NULL
    - complete_summary: TEXT, NULL
    - telemetry: TEXT, NULL
    - started_at: TIMESTAMP, NOT NULL, DEFAULT CURRENT_TIMESTAMP
    - completed_at: TIMESTAMP, NULL (finalize timestamp)
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts / update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_completes")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'skill_name', 'coordination_type',
                       'status', 'session_count', 'ai_model', 'effort',
                       'tokens_input', 'tokens_cache_write', 'tokens_cache_read',
                       'tokens_output', 'wall_seconds', 'turn_count',
                       'complete_summary', 'telemetry',
                       'started_at', 'completed_at',
                       'creator_fk', 'create_ts', 'update_ts']
    # req #3202, migration 20260809002208 — WHERE the close-out ran, the
    # envelope's machine context. Tolerated the same way every other post-058
    # addition to this table is, so the file stays runnable against a database
    # that has not taken the migration yet. (Not part of req #3455; the
    # migration reached darwin_dev without this list being widened, so the
    # assertion below failed for a column nobody had declared.)
    if 'machine_fk' in columns:
        expected_fields.append('machine_fk')
    # Req #3202, migration 20260808235540 — the shared telemetry envelope's
    # wall-clock unit and prompt columns (the four tokens_* columns above
    # already matched the envelope's spelling and needed no change).
    # Tolerated the same way, for the same dev-before-production window.
    for envelope in ('wall_ms', 'prompt_text', 'prompt_sha256', 'prompt_chars'):
        if envelope in columns:
            expected_fields.append(envelope)
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    # req #3202 machine_fk — nullable FK, no default. NULL is a real answer: a
    # close-out whose machine identity did not resolve.
    if 'machine_fk' in columns:
        assert columns['machine_fk']['Type'] == 'int'
        assert columns['machine_fk']['Null'] == 'YES'
        assert columns['machine_fk']['Key'] == 'MUL'

    assert columns['skill_name']['Type'] == 'varchar(64)'
    assert columns['skill_name']['Null'] == 'NO'

    assert columns['coordination_type']['Type'] == 'varchar(16)'
    assert columns['coordination_type']['Null'] == 'YES'

    assert columns['status']['Type'] == 'varchar(16)'
    assert columns['status']['Null'] == 'NO'
    assert columns['status']['Default'] == 'in_progress'

    assert columns['session_count']['Type'] == 'int'
    assert columns['session_count']['Null'] == 'NO'
    assert columns['session_count']['Default'] == '0'

    # req #2949 — normalized, queryable copy of the telemetry blob's model/effort.
    assert columns['ai_model']['Type'] == 'varchar(16)'
    assert columns['ai_model']['Null'] == 'NO'
    assert columns['ai_model']['Default'] == 'opus'

    assert columns['effort']['Type'] == 'varchar(16)'
    assert columns['effort']['Null'] == 'NO'
    assert columns['effort']['Default'] == 'high'

    # Token / timing / count columns are NULL until the skill's finalize populates them.
    for col in ('tokens_input', 'tokens_cache_write', 'tokens_cache_read',
                'tokens_output', 'wall_seconds', 'turn_count'):
        assert columns[col]['Type'] == 'int', col
        assert columns[col]['Null'] == 'YES', col

    assert columns['complete_summary']['Type'] == 'text'
    assert columns['complete_summary']['Null'] == 'YES'

    assert columns['telemetry']['Type'] == 'text'
    assert columns['telemetry']['Null'] == 'YES'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'NO'

    assert 'timestamp' in columns['completed_at']['Type']
    assert columns['completed_at']['Null'] == 'YES'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'


def test_swarm_complete_sessions_columns(db_connection):
    """Verify swarm_complete_sessions junction table column definitions (req #2497).

    Expected columns:
    - swarm_complete_fk: INT, PRI, NOT NULL
    - session_fk: INT, PRI, NOT NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE swarm_complete_sessions")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['swarm_complete_fk', 'session_fk']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['swarm_complete_fk']['Type'] == 'int'
    assert columns['swarm_complete_fk']['Null'] == 'NO'
    assert columns['swarm_complete_fk']['Key'] == 'PRI'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'NO'
    assert columns['session_fk']['Key'] == 'PRI'


def test_dev_servers_columns(db_connection):
    """Verify dev_servers column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - port: SMALLINT, NOT NULL, UNI
    - pid: INT, NOT NULL
    - terminal_number: SMALLINT, NULL (req #2419)
    - workspace_path: VARCHAR(512), NOT NULL
    - session_fk: INT, NULL, MUL
    - machine_fk: INT, NULL, MUL (req #2943 — first column of uq_machine_port)
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - started_at: TIMESTAMP, NOT NULL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE dev_servers")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'port', 'pid', 'terminal_number', 'workspace_path',
                       'session_fk', 'machine_fk', 'creator_fk', 'started_at',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['port']['Type'] == 'smallint'
    assert columns['port']['Null'] == 'NO'
    # Req #2943: port is no longer globally UNIQUE — it is the SECOND column of
    # the composite uq_machine_port(machine_fk, port), so it reports no Key here
    # (only the leading column of an index shows in DESCRIBE).
    assert columns['port']['Key'] == ''

    assert columns['terminal_number']['Type'] == 'smallint'
    assert columns['terminal_number']['Null'] == 'YES'

    assert columns['pid']['Type'] == 'int'
    assert columns['pid']['Null'] == 'NO'

    assert columns['workspace_path']['Type'] == 'varchar(512)'
    assert columns['workspace_path']['Null'] == 'NO'

    assert columns['session_fk']['Type'] == 'int'
    assert columns['session_fk']['Null'] == 'YES'
    assert columns['session_fk']['Key'] == 'MUL'

    # Req #2943 — machine_fk: nullable FK, leading column of uq_machine_port.
    assert columns['machine_fk']['Type'] == 'int'
    assert columns['machine_fk']['Null'] == 'YES'
    assert columns['machine_fk']['Key'] == 'MUL'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'NO'


def test_priority_card_order_columns(db_connection):
    """Verify priority_card_order column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - domain_id: INT, NOT NULL, MUL (part of UNIQUE)
    - task_id: INT, NOT NULL
    - sort_order: SMALLINT, NOT NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE priority_card_order")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'domain_id', 'task_id', 'sort_order']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['domain_id']['Type'] == 'int'
    assert columns['domain_id']['Null'] == 'NO'
    assert columns['domain_id']['Key'] == 'MUL'

    assert columns['task_id']['Type'] == 'int'
    assert columns['task_id']['Null'] == 'NO'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'NO'


def test_recurring_tasks_columns(db_connection):
    """Verify recurring_tasks column definitions match schema.sql.

    Expected columns (migration 017):
    - id: INT, PRI, AUTO_INCREMENT
    - description: VARCHAR(1024), NOT NULL
    - recurrence: VARCHAR(16), NOT NULL
    - anchor_date: DATE, NOT NULL
    - area_fk: INT, NOT NULL, MUL
    - priority: TINYINT(1), NOT NULL, DEFAULT 0
    - accumulate: TINYINT(1), NOT NULL, DEFAULT 0
    - insert_position: VARCHAR(8), NOT NULL, DEFAULT 'bottom'
    - active: TINYINT(1), NOT NULL, DEFAULT 1
    - last_generated: DATE, NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE recurring_tasks")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'description', 'recurrence', 'anchor_date', 'area_fk',
        'priority', 'accumulate', 'insert_position', 'active',
        'last_generated', 'creator_fk', 'create_ts', 'update_ts'
    ]
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    # id: INT, PRI, AUTO_INCREMENT
    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Null'] == 'NO'
    assert columns['id']['Extra'] == 'auto_increment'

    # description: VARCHAR(1024), NOT NULL
    assert columns['description']['Type'] == 'varchar(1024)'
    assert columns['description']['Null'] == 'NO'

    # recurrence: VARCHAR(16), NOT NULL
    assert columns['recurrence']['Type'] == 'varchar(16)'
    assert columns['recurrence']['Null'] == 'NO'

    # anchor_date: DATE, NOT NULL
    assert columns['anchor_date']['Type'] == 'date'
    assert columns['anchor_date']['Null'] == 'NO'

    # area_fk: INT, NOT NULL, MUL
    assert columns['area_fk']['Type'] == 'int'
    assert columns['area_fk']['Null'] == 'NO'
    assert columns['area_fk']['Key'] == 'MUL'

    # priority: TINYINT(1), NOT NULL, DEFAULT 0
    assert 'tinyint' in columns['priority']['Type'].lower()
    assert columns['priority']['Null'] == 'NO'
    assert columns['priority']['Default'] == '0'

    # accumulate: TINYINT(1), NOT NULL, DEFAULT 0
    assert 'tinyint' in columns['accumulate']['Type'].lower()
    assert columns['accumulate']['Null'] == 'NO'
    assert columns['accumulate']['Default'] == '0'

    # insert_position: VARCHAR(8), NOT NULL, DEFAULT 'bottom'
    assert columns['insert_position']['Type'] == 'varchar(8)'
    assert columns['insert_position']['Null'] == 'NO'
    assert columns['insert_position']['Default'] == 'bottom'

    # active: TINYINT(1), NOT NULL, DEFAULT 1
    assert 'tinyint' in columns['active']['Type'].lower()
    assert columns['active']['Null'] == 'NO'
    assert columns['active']['Default'] == '1'

    # last_generated: DATE, NULL
    assert columns['last_generated']['Type'] == 'date'
    assert columns['last_generated']['Null'] == 'YES'

    # creator_fk: VARCHAR(64), NOT NULL, MUL
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    # create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Null'] == 'YES'
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    # update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Null'] == 'YES'
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_map_routes_columns(db_connection):
    """Verify map_routes column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - route_id: INT, NOT NULL
    - name: VARCHAR(256), NOT NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL, DEFAULT CURRENT_TIMESTAMP
    - update_ts: TIMESTAMP, NULL, ON UPDATE CURRENT_TIMESTAMP
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE map_routes")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'route_id', 'name', 'creator_fk', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['route_id']['Type'] == 'bigint'
    assert columns['route_id']['Null'] == 'NO'

    assert columns['name']['Type'] == 'varchar(256)'
    assert columns['name']['Null'] == 'NO'

    # creator_fk is part of UNIQUE KEY uq_creator_route, so Key may show MUL or UNI
    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'

    assert 'timestamp' in columns['create_ts']['Type']
    assert columns['create_ts']['Default'] == 'CURRENT_TIMESTAMP'

    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_map_runs_columns(db_connection):
    """Verify map_runs column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - run_id: INT, NOT NULL
    - map_route_fk: INT, NULL, MUL
    - activity_id: INT, NOT NULL
    - activity_name: VARCHAR(16), NOT NULL
    - start_time: DATETIME, NOT NULL
    - run_time_sec: INT, NOT NULL
    - stopped_time_sec: INT, NOT NULL, DEFAULT 0
    - distance_mi: DECIMAL(6,1), NOT NULL
    - ascent_ft: INT, NULL
    - descent_ft: INT, NULL
    - calories: INT, NULL
    - max_speed_mph: DECIMAL(5,1), NULL
    - avg_speed_mph: DECIMAL(5,2), NULL
    - notes: TEXT, NULL
    - source: VARCHAR(32), NOT NULL, DEFAULT 'cyclemeter'
    - creator_fk: VARCHAR(64), NOT NULL, MUL
    - create_ts: TIMESTAMP, NULL
    - update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE map_runs")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = [
        'id', 'run_id', 'map_route_fk', 'activity_id', 'activity_name',
        'start_time', 'run_time_sec', 'stopped_time_sec', 'distance_mi',
        'ascent_ft', 'descent_ft', 'calories', 'max_speed_mph', 'avg_speed_mph',
        'notes', 'source', 'creator_fk', 'create_ts', 'update_ts'
    ]
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['run_id']['Type'] == 'bigint'
    assert columns['run_id']['Null'] == 'NO'

    assert columns['map_route_fk']['Type'] == 'int'
    assert columns['map_route_fk']['Null'] == 'YES'
    assert columns['map_route_fk']['Key'] == 'MUL'

    assert columns['activity_id']['Type'] == 'int'
    assert columns['activity_id']['Null'] == 'NO'

    assert columns['activity_name']['Type'] == 'varchar(16)'
    assert columns['activity_name']['Null'] == 'NO'

    assert columns['start_time']['Type'] == 'datetime'
    assert columns['start_time']['Null'] == 'NO'

    assert columns['run_time_sec']['Type'] == 'int'
    assert columns['run_time_sec']['Null'] == 'NO'

    assert columns['stopped_time_sec']['Type'] == 'int'
    assert columns['stopped_time_sec']['Null'] == 'NO'
    assert columns['stopped_time_sec']['Default'] == '0'

    assert columns['distance_mi']['Type'] == 'decimal(6,1)'
    assert columns['distance_mi']['Null'] == 'NO'

    assert columns['ascent_ft']['Type'] == 'int'
    assert columns['ascent_ft']['Null'] == 'YES'

    assert columns['descent_ft']['Type'] == 'int'
    assert columns['descent_ft']['Null'] == 'YES'

    assert columns['calories']['Type'] == 'int'
    assert columns['calories']['Null'] == 'YES'

    assert columns['max_speed_mph']['Type'] == 'decimal(5,1)'
    assert columns['max_speed_mph']['Null'] == 'YES'

    assert columns['avg_speed_mph']['Type'] == 'decimal(5,2)'
    assert columns['avg_speed_mph']['Null'] == 'YES'

    assert columns['notes']['Type'] == 'text'
    assert columns['notes']['Null'] == 'YES'

    assert columns['source']['Type'] == 'varchar(32)'
    assert columns['source']['Null'] == 'NO'
    assert columns['source']['Default'] == 'cyclemeter'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'


def test_map_coordinates_columns(db_connection):
    """Verify map_coordinates column definitions match schema.sql.

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - map_run_fk: INT, NOT NULL, MUL
    - seq: INT, NOT NULL
    - latitude: DECIMAL(10,7), NOT NULL
    - longitude: DECIMAL(10,7), NOT NULL
    - altitude: DECIMAL(7,1), NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE map_coordinates")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'map_run_fk', 'seq', 'latitude', 'longitude', 'altitude']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['map_run_fk']['Type'] == 'int'
    assert columns['map_run_fk']['Null'] == 'NO'
    assert columns['map_run_fk']['Key'] == 'MUL'

    assert columns['seq']['Type'] == 'int'
    assert columns['seq']['Null'] == 'NO'

    assert columns['latitude']['Type'] == 'decimal(10,7)'
    assert columns['latitude']['Null'] == 'NO'

    assert columns['longitude']['Type'] == 'decimal(10,7)'
    assert columns['longitude']['Null'] == 'NO'

    assert columns['altitude']['Type'] == 'decimal(7,1)'
    assert columns['altitude']['Null'] == 'YES'


def test_map_coordinates_composite_index(db_connection):
    """migration 20260803164904 (req #3166): (map_run_fk, seq), and ONLY that.

    `DESCRIBE` cannot tell these two apart — `map_run_fk` reads `Key='MUL'`
    under the old single-column index and under the composite alike, so the
    column test above passes either way. Nothing else in this suite loads
    `scripts/recreate_darwin_dev.sql`, which is the file a darwin_dev rebuild
    actually runs, so a stale copy of it would silently restore the pre-#3166
    index with every test still green. This is the assertion that notices.

    Asserted as EXACTLY two keys because the migration REPLACES rather than
    adds: leaving `idx_map_coordinates_run` in place would be a redundant
    B-tree maintained on every row of a bulk import (~600 per run).
    """
    with db_connection.cursor() as cur:
        cur.execute("SHOW INDEX FROM map_coordinates")
        rows = cur.fetchall()

    by_key = {}
    for row in rows:
        by_key.setdefault(row['Key_name'], {})[row['Seq_in_index']] = row['Column_name']

    assert 'idx_map_coordinates_run_seq' in by_key, \
        'idx_map_coordinates_run_seq missing — migration 20260803164904 not applied'
    composite = by_key['idx_map_coordinates_run_seq']
    assert [composite[i] for i in sorted(composite)] == ['map_run_fk', 'seq'], \
        'map_run_fk must lead: it is the FK prefix AND the filter column'

    assert 'idx_map_coordinates_run' not in by_key, \
        'the single-column index is redundant under the composite and must be dropped'
    assert set(by_key) == {'PRIMARY', 'idx_map_coordinates_run_seq'}, \
        f'unexpected indexes on map_coordinates: {sorted(by_key)}'


def test_map_views_columns(db_connection):
    """Verify map_views column definitions match schema.sql."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE map_views")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'name', 'criteria', 'sort_order',
                       'creator_fk', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['name']['Type'] == 'varchar(10)'
    assert columns['name']['Null'] == 'NO'

    assert columns['criteria']['Type'] == 'json'
    assert columns['criteria']['Null'] == 'NO'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert 'timestamp' in columns['create_ts']['Type']
    assert 'timestamp' in columns['update_ts']['Type']


def test_map_partners_columns(db_connection):
    """Verify map_partners column definitions match schema.sql."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE map_partners")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'name', 'creator_fk', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['name']['Type'] == 'varchar(64)'
    assert columns['name']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'

    assert 'timestamp' in columns['create_ts']['Type']
    assert 'timestamp' in columns['update_ts']['Type']
    assert columns['update_ts']['Extra'] == 'on update CURRENT_TIMESTAMP'


def test_map_run_partners_columns(db_connection):
    """Verify map_run_partners column definitions match schema.sql."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE map_run_partners")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'map_run_fk', 'map_partner_fk', 'create_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['map_run_fk']['Type'] == 'int'
    assert columns['map_run_fk']['Null'] == 'NO'
    assert columns['map_run_fk']['Key'] == 'MUL'

    assert columns['map_partner_fk']['Type'] == 'int'
    assert columns['map_partner_fk']['Null'] == 'NO'
    assert columns['map_partner_fk']['Key'] == 'MUL'

    assert 'timestamp' in columns['create_ts']['Type']


def test_test_cases_columns(db_connection):
    """Verify test_cases column definitions match schema.sql (migration 042)."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE test_cases")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'title', 'preconditions', 'steps', 'expected',
                       'test_type', 'tags', 'category_fk', 'creator_fk',
                       'closed', 'sort_order', 'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['title']['Type'] == 'varchar(256)'
    assert columns['title']['Null'] == 'NO'

    assert columns['preconditions']['Type'] == 'text'
    assert columns['preconditions']['Null'] == 'YES'  # optional (smoke tests may have none)

    assert columns['steps']['Type'] == 'text'
    assert columns['steps']['Null'] == 'NO'

    assert columns['expected']['Type'] == 'text'
    assert columns['expected']['Null'] == 'NO'

    assert columns['test_type']['Type'] == 'varchar(16)'
    assert columns['test_type']['Null'] == 'NO'
    assert columns['test_type']['Default'] == 'manual'

    assert columns['tags']['Type'] == 'varchar(512)'
    assert columns['tags']['Null'] == 'YES'

    assert columns['category_fk']['Type'] == 'int'
    assert columns['category_fk']['Null'] == 'NO'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'

    assert 'tinyint' in columns['closed']['Type']
    assert columns['closed']['Default'] == '0'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'


# COVERS: SCH-031, SCH-034
def test_requirement_test_cases_columns(db_connection):
    """req #3352 — requirement_test_cases junction (migration 20260809002149),
    composite PK, no id. Its predecessor, feature_test_cases, was dropped at
    req #3355 (migration 20260811033413) — this is now the only test-case
    junction."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE requirement_test_cases")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['requirement_fk', 'test_case_fk']
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    # Both FKs are primary key parts (composite PK)
    assert columns['requirement_fk']['Type'] == 'int'
    assert columns['requirement_fk']['Null'] == 'NO'
    assert columns['requirement_fk']['Key'] == 'PRI'

    assert columns['test_case_fk']['Type'] == 'int'
    assert columns['test_case_fk']['Null'] == 'NO'
    # MySQL reports non-leading composite PK columns as 'MUL'
    assert columns['test_case_fk']['Key'] in ('PRI', 'MUL')

    # feature_test_cases is gone — req #3355 dropped it in the same migration
    # that this test's own requirement's precondition (a) verified every one
    # of its rows had a requirement_test_cases equivalent.
    with db_connection.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'feature_test_cases'")
        assert cur.fetchone() is None, \
            "feature_test_cases must be dropped by req #3355"


# COVERS: ERA-008
def test_requirement_test_cases_carries_the_pre_drop_migration(db_connection):
    """req #3355 precondition (a) — verified 2026-08-11 by direct PRODUCTION
    query before the drop (the durable proof; this test cannot re-run that
    query, `feature_test_cases` no longer exists to compare against): all 28
    production `feature_test_cases` rows had a `requirement_test_cases` row
    sharing the same `test_case_fk`, spread across four requirements
    (3158:9, 3159:7, 3163:7, 3174:5) that darwin_dev's own migration carried
    identically at measurement time.

    This test regression-locks darwin_dev's copy of that outcome — but
    darwin_dev is rebuilt from `recreate_darwin_dev.sql` (schema only, no
    data) with some regularity, and nothing under `DarwinSQL/scripts/`
    re-seeds this junction afterward. A CLEAN reset — all four requirements
    at zero — is that expected, harmless case and is SKIPPED rather than
    failed. A PARTIAL count (some but not all rows present, or a nonzero
    count short of what was measured) is never expected from a clean reset
    and fails loudly: that shape means the migrated data was damaged, not
    that darwin_dev was rebuilt."""
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT requirement_fk, COUNT(*) AS c FROM requirement_test_cases "
            "WHERE requirement_fk IN (3158, 3159, 3163, 3174) "
            "GROUP BY requirement_fk")
        counts = {row['requirement_fk']: row['c'] for row in cur.fetchall()}
    expected = {3158: 9, 3159: 7, 3163: 7, 3174: 5}
    if not counts:
        pytest.skip('requirement_test_cases carries none of the four measured '
                    'requirements — darwin_dev was likely reset from '
                    'recreate_darwin_dev.sql (schema only, no data) since this '
                    'junction was last backfilled; nothing to regression-lock')
    for rid, want in expected.items():
        assert counts.get(rid, 0) >= want, (
            f'requirement #{rid} carries {counts.get(rid, 0)} requirement_test_cases '
            f'rows, expected at least {want} — the pre-drop migration may have lost data')


def test_test_plans_columns(db_connection):
    """Verify test_plans column definitions match schema.sql (migration 043)."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE test_plans")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'title', 'description', 'category_fk',
                       'creator_fk', 'closed', 'sort_order',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Extra'] == 'auto_increment'
    assert columns['title']['Type'] == 'varchar(256)'
    assert columns['title']['Null'] == 'NO'
    assert columns['description']['Type'] == 'text'
    assert columns['description']['Null'] == 'YES'  # nullable (distinct from features.description)
    assert columns['category_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'
    assert columns['sort_order']['Null'] == 'YES'


def test_test_plan_cases_columns(db_connection):
    """Verify test_plan_cases junction (migration 043) — composite PK + sort_order."""
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE test_plan_cases")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['test_plan_fk', 'test_case_fk', 'sort_order']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['test_plan_fk']['Null'] == 'NO'
    assert columns['test_plan_fk']['Key'] == 'PRI'

    assert columns['test_case_fk']['Null'] == 'NO'
    assert columns['test_case_fk']['Key'] in ('PRI', 'MUL')

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'


def test_test_runs_columns(db_connection):
    """Verify test_runs column definitions match schema.sql (migration 044).

    Execution table — has started_at/completed_at, NO closed, NO sort_order.
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE test_runs")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'test_plan_fk', 'run_status', 'started_at',
                       'completed_at', 'notes', 'creator_fk',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    assert 'closed' not in columns, "test_runs is an execution table; must NOT have a closed column"
    assert 'sort_order' not in columns, "test_runs is chronological by started_at"

    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['test_plan_fk']['Type'] == 'int'
    assert columns['test_plan_fk']['Null'] == 'NO'

    assert columns['run_status']['Type'] == 'varchar(16)'
    assert columns['run_status']['Null'] == 'NO'
    assert columns['run_status']['Default'] == 'in_progress'

    assert 'timestamp' in columns['started_at']['Type']
    assert columns['started_at']['Null'] == 'NO'
    assert columns['started_at']['Default'] == 'CURRENT_TIMESTAMP'

    assert 'timestamp' in columns['completed_at']['Type']
    assert columns['completed_at']['Null'] == 'YES'

    assert columns['notes']['Type'] == 'text'
    assert columns['notes']['Null'] == 'YES'

    assert columns['creator_fk']['Null'] == 'NO'


def test_test_results_columns(db_connection):
    """Verify test_results column definitions match schema.sql (migration 044).

    Execution table — has executed_at, NO closed, NO sort_order. UNIQUE (run, case).
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE test_results")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'test_run_fk', 'test_case_fk', 'result_status',
                       'actual', 'notes', 'executed_at', 'creator_fk',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields), \
        f"Unexpected columns: {set(columns.keys()) - set(expected_fields)}"

    assert 'closed' not in columns, "test_results is an execution table"
    assert 'sort_order' not in columns

    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['test_run_fk']['Type'] == 'int'
    assert columns['test_run_fk']['Null'] == 'NO'

    assert columns['test_case_fk']['Type'] == 'int'
    assert columns['test_case_fk']['Null'] == 'NO'

    assert columns['result_status']['Type'] == 'varchar(16)'
    assert columns['result_status']['Null'] == 'NO'
    assert columns['result_status']['Default'] == 'not_run'

    assert columns['actual']['Type'] == 'text'
    assert columns['actual']['Null'] == 'YES'

    assert 'timestamp' in columns['executed_at']['Type']
    assert columns['executed_at']['Null'] == 'YES'  # populated when recorded

    # Verify UNIQUE constraint uq_run_case
    with db_connection.cursor() as cur:
        cur.execute("SHOW INDEX FROM test_results WHERE Key_name = 'uq_run_case'")
        rows = cur.fetchall()
    columns_in_unique = {r['Column_name'] for r in rows}
    assert columns_in_unique == {'test_run_fk', 'test_case_fk'}, \
        f"uq_run_case UNIQUE should cover (test_run_fk, test_case_fk), got {columns_in_unique}"


def test_customers_columns(db_connection):
    """Verify customers column definitions match migration 049 (req #2604).

    Expected columns:
    - id: INT, PRI, AUTO_INCREMENT
    - customer_name: VARCHAR(256), NOT NULL
    - description: TEXT, NULL
    - creator_fk: VARCHAR(64), NOT NULL, MUL (FK to profiles)
    - closed: TINYINT(1), NOT NULL, DEFAULT 0
    - sort_order: SMALLINT, NULL
    - create_ts / update_ts: TIMESTAMP, NULL
    """
    with db_connection.cursor() as cur:
        cur.execute("DESCRIBE customers")
        columns = {row['Field']: row for row in cur.fetchall()}

    expected_fields = ['id', 'customer_name', 'description',
                       'creator_fk', 'closed', 'sort_order',
                       'create_ts', 'update_ts']
    assert set(columns.keys()) == set(expected_fields)

    assert columns['id']['Type'] == 'int'
    assert columns['id']['Key'] == 'PRI'
    assert columns['id']['Extra'] == 'auto_increment'

    assert columns['customer_name']['Type'] == 'varchar(256)'
    assert columns['customer_name']['Null'] == 'NO'

    assert columns['description']['Type'] == 'text'
    assert columns['description']['Null'] == 'YES'

    assert columns['creator_fk']['Type'] == 'varchar(64)'
    assert columns['creator_fk']['Null'] == 'NO'
    assert columns['creator_fk']['Key'] == 'MUL'

    assert columns['closed']['Type'] == 'tinyint(1)'
    assert columns['closed']['Null'] == 'NO'
    assert columns['closed']['Default'] == '0'

    assert columns['sort_order']['Type'] == 'smallint'
    assert columns['sort_order']['Null'] == 'YES'


# COVERS: SCH-018
def test_table_count(db_connection):
    """Verify darwin_dev database contains the expected tables."""
    with db_connection.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = {row['Tables_in_darwin_dev'] for row in cur.fetchall()}

    expected_tables = {
        'profiles', 'domains', 'areas', 'recurring_tasks', 'tasks',
        'projects', 'categories', 'requirements', 'requirement_sessions',
        'swarm_sessions', 'dev_servers', 'priority_card_order',
        'map_routes', 'map_runs', 'map_coordinates', 'map_views',
        'map_partners', 'map_run_partners',
        'user_integrations',  # Migration 036
        # Req #2380 — Swarm Features & Test Cases registry. `features` and
        # `feature_test_cases` dropped at req #3355 (migration 20260811033413).
        'test_cases',
        'test_plans', 'test_plan_cases',
        'test_runs', 'test_results',
        # Req #2422 — swarm-start data type
        'swarm_starts', 'swarm_start_sessions',
        # Req #2604 — Customer Release
        'customers',
        # Req #2606 — Build Visualizer data model
        'build_projects', 'branches', 'builds', 'customer_releases',
        # Req #2633 — Acceptance Test data type (build-viz; darwin_dev only)
        'acceptance_tests', 'branch_acceptance_tests',
        # Req #2719 — swarm-undo data type
        'swarm_undos',
        # Req #2497 — swarm-complete data type
        'swarm_completes', 'swarm_complete_sessions',
        # Req #2943 — machine registry
        'machines',
        # Req #2997 — agents registry (ownership of architecture documents)
        'agents', 'instructions', 'agent_instructions',
        'architecture_documents', 'agent_documents',
        # Req #3031 — agent context telemetry (run header + per-agent rows)
        'agent_telemetry_runs', 'agent_telemetry_rows',
        # Req #3096 — per-document actual-token rows (child of agent_telemetry_rows)
        'agent_telemetry_row_docs',
        # Req #3111's five 1.0 orchestration tables — `epics`, `pipelines`,
        # `pipeline_steps`, `pipeline_step_requirements`, `pipeline_step_deps`
        # — were dropped at req #3356 (migration 20260812175325). The
        # `pipeline2_*` five below are the surviving plan layer.
        # Req #3224 — the durable, SHARED orchestration reservation (migration
        # 20260801150404). One row per RESERVED SCOPE, so the single-orchestrator
        # guarantee crosses a machine boundary instead of living in /tmp.
        'orchestration_claims',
        # Req #3337 — Pipeline 2.0 plan layer (migration 20260808115509).
        # Containment chain Pipeline -> Epic -> Step -> Requirement.
        'pipelines', 'epics', 'pipeline_steps',
        'pipeline_step_requirements', 'pipeline_step_deps',
        # Req #3352 — Pipeline 2.0 Feature retirement: test cases re-home onto
        # Requirement (migration 20260809002149). The sole test-case junction
        # since req #3355 dropped feature_test_cases.
        'requirement_test_cases',
    }
    assert expected_tables == tables, \
        f"Unexpected tables: {tables - expected_tables}, missing: {expected_tables - tables}"

    # The set above is REVIEWED, not derived — a human decides what belongs in
    # darwin_dev, which is why it is written out. But it must agree with
    # `schema.sql`, the file a fresh database is built from, and hand-editing
    # two lists is how they drift. This cross-check re-derives the schema's own
    # table set and fails on any disagreement, so the count is never carried by
    # hand from one artifact to the other (req #3356).
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'schema.sql')
    with open(schema_path) as handle:
        schema_tables = set(re.findall(
            r'^CREATE TABLE (?:IF NOT EXISTS )?`?(\w+)`?', handle.read(), re.M))
    assert schema_tables == expected_tables, (
        f"schema.sql and the reviewed set disagree — "
        f"only in schema.sql: {sorted(schema_tables - expected_tables)}, "
        f"only in the reviewed set: {sorted(expected_tables - schema_tables)}")


# ============================================================================
# Req #2606 — Build Visualizer data model column tests
# ============================================================================

def _columns(cur, table):
    cur.execute(f"DESCRIBE {table}")
    return {row['Field']: row for row in cur.fetchall()}


def test_build_projects_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'build_projects')
    assert cols['title']['Null'] == 'NO'
    assert cols['title']['Type'] == 'varchar(256)'
    assert cols['description']['Null'] == 'YES'
    assert cols['project_status']['Null'] == 'NO'
    assert cols['project_status']['Default'] == 'draft'
    assert cols['trunk_branch_fk']['Null'] == 'YES'
    assert cols['creator_fk']['Null'] == 'NO'
    # Req #2606: no `closed` column on any new build-feature table.
    assert 'closed' not in cols
    # Req #2723: build_projects no longer carries a category_fk.
    assert 'category_fk' not in cols


def test_branches_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'branches')
    assert cols['project_fk']['Null'] == 'NO'
    assert cols['branch_type']['Null'] == 'NO'
    assert cols['name']['Null'] == 'YES'
    assert cols['major']['Null'] == 'NO'
    assert cols['minor']['Null'] == 'NO'
    assert cols['parent_build_fk']['Null'] == 'YES'
    assert cols['creator_fk']['Null'] == 'NO'
    # Req #2648: external_id holds the iframe slug ('main', 'release-1', etc.)
    # so the SqlBackedStorageAdapter can round-trip the in-memory model.
    assert cols['external_id']['Null'] == 'YES'
    assert 'varchar(64)' in cols['external_id']['Type'].lower()
    # Req #2606: parent_branch_fk REMOVED (derived via builds[parent_build_fk]).
    assert 'parent_branch_fk' not in cols
    # Req #2606: segment_* columns REMOVED (each branch carries M.m directly).
    assert 'segment_major' not in cols
    assert 'segment_minor' not in cols
    assert 'segment_initial_build_number' not in cols
    assert 'closed' not in cols
    # Req #2633: single per-branch Acceptance Test status (pass|fail, default pass).
    assert cols['acceptance_test_status']['Null'] == 'YES'
    assert 'varchar(16)' in cols['acceptance_test_status']['Type'].lower()
    assert cols['acceptance_test_status']['Default'] == 'pass'


def test_acceptance_tests_columns(db_connection):
    """Req #2633: acceptance_tests catalog (build-viz CATALOG shape, mirrors
    customers: closed + sort_order, NO category_fk). Adds acceptance_test_status
    (pass|fail default pass) + expected_wall_mins."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'acceptance_tests')
    expected = {'id', 'title', 'description', 'acceptance_test_status',
                'expected_wall_mins', 'closed', 'sort_order', 'creator_fk',
                'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected
    assert cols['id']['Extra'] == 'auto_increment'
    assert cols['title']['Type'] == 'varchar(256)'
    assert cols['title']['Null'] == 'NO'
    assert cols['description']['Null'] == 'YES'
    assert 'varchar(16)' in cols['acceptance_test_status']['Type'].lower()
    assert cols['acceptance_test_status']['Null'] == 'NO'
    assert cols['acceptance_test_status']['Default'] == 'pass'
    assert cols['expected_wall_mins']['Type'] == 'int'
    assert cols['expected_wall_mins']['Null'] == 'YES'
    assert cols['closed']['Type'] == 'tinyint(1)'
    assert cols['closed']['Default'] == '0'
    assert cols['sort_order']['Type'] == 'smallint'
    assert cols['creator_fk']['Null'] == 'NO'
    # Build-viz catalog convention: no category_fk.
    assert 'category_fk' not in cols


def test_branch_acceptance_tests_columns(db_connection):
    """Req #2633: branch_acceptance_tests junction — composite PK, sort_order for
    per-branch label stacking, no surrogate id / creator / timestamps."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'branch_acceptance_tests')
    assert set(cols.keys()) == {'branch_fk', 'acceptance_test_fk', 'sort_order'}
    assert cols['branch_fk']['Key'] == 'PRI'
    assert cols['acceptance_test_fk']['Key'] == 'PRI'
    assert cols['sort_order']['Type'] == 'smallint'
    assert 'id' not in cols
    assert 'creator_fk' not in cols


def test_machines_columns(db_connection):
    """Req #2943: machines registry — content-table baseline (id/title/description/
    closed/sort_order/creator_fk/timestamps) PLUS the auto-detected identity
    columns. No category_fk (infrastructure entity). hostname is UNIQUE (the
    auto-match key). platform/arch NOT NULL; os_version/hw_model/last_seen_at NULL.
    max_live_sessions (req #3390): per-machine swarm concurrency ceiling,
    NOT NULL DEFAULT 20 — the DDL default is the only literal anywhere in the
    system (both live machines are pinned explicitly by hostname)."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'machines')
    expected = {'id', 'title', 'description', 'hostname', 'platform', 'arch',
                'os_version', 'hw_model', 'last_seen_at', 'max_live_sessions',
                'closed', 'sort_order', 'creator_fk', 'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected

    assert cols['id']['Type'] == 'int'
    assert cols['id']['Key'] == 'PRI'
    assert cols['id']['Extra'] == 'auto_increment'

    assert cols['title']['Type'] == 'varchar(256)'
    assert cols['title']['Null'] == 'NO'

    assert cols['description']['Type'] == 'text'
    assert cols['description']['Null'] == 'YES'

    # hostname is the auto-match key — NOT NULL + UNIQUE.
    assert cols['hostname']['Type'] == 'varchar(128)'
    assert cols['hostname']['Null'] == 'NO'
    assert cols['hostname']['Key'] == 'UNI'

    assert cols['platform']['Type'] == 'varchar(16)'
    assert cols['platform']['Null'] == 'NO'
    assert cols['arch']['Type'] == 'varchar(16)'
    assert cols['arch']['Null'] == 'NO'

    # Auto best-effort identity facts — nullable.
    assert cols['os_version']['Type'] == 'varchar(64)'
    assert cols['os_version']['Null'] == 'YES'
    assert cols['hw_model']['Type'] == 'varchar(64)'
    assert cols['hw_model']['Null'] == 'YES'
    assert 'timestamp' in cols['last_seen_at']['Type']
    assert cols['last_seen_at']['Null'] == 'YES'

    # Per-machine swarm concurrency ceiling (req #3390) — NOT NULL DEFAULT,
    # never nullable-means-unlimited (that would be fail-open where #3344's
    # admission control is fail-closed).
    assert cols['max_live_sessions']['Type'] == 'smallint'
    assert cols['max_live_sessions']['Null'] == 'NO'
    assert cols['max_live_sessions']['Default'] == '20'

    # Content-table baseline soft-delete + hand-sort.
    assert cols['closed']['Type'] == 'tinyint(1)'
    assert cols['closed']['Null'] == 'NO'
    assert cols['closed']['Default'] == '0'
    assert cols['sort_order']['Type'] == 'smallint'
    assert cols['sort_order']['Null'] == 'YES'

    assert cols['creator_fk']['Type'] == 'varchar(64)'
    assert cols['creator_fk']['Null'] == 'NO'
    assert cols['creator_fk']['Key'] == 'MUL'

    # Infrastructure entity — deliberately no category_fk.
    assert 'category_fk' not in cols


def test_builds_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'builds')
    assert cols['branch_fk']['Null'] == 'NO'
    assert cols['position']['Null'] == 'NO'
    assert cols['build_number']['Null'] == 'NO'        # B — stored, computed once
    assert cols['branch_number']['Null'] == 'NO'        # b — stored, 0 for trunk
    assert cols['branch_number']['Default'] == '0'
    # Req #2720: per-build M.m — stamped at creation, no look-back to branch.
    assert cols['major']['Null'] == 'NO'
    assert cols['major']['Default'] == '0'
    assert 'int' in cols['major']['Type'].lower()
    assert cols['minor']['Null'] == 'NO'
    assert cols['minor']['Default'] == '0'
    assert 'int' in cols['minor']['Type'].lower()
    assert cols['approved_for_release']['Null'] == 'NO'
    assert cols['approved_for_release']['Default'] == '0'
    assert cols['dot_color']['Null'] == 'YES'
    assert cols['creator_fk']['Null'] == 'NO'
    # Req #2648: external_id holds the iframe slug ('m1', 'r1c', 'sr3', etc.).
    assert cols['external_id']['Null'] == 'YES'
    assert 'varchar(64)' in cols['external_id']['Type'].lower()
    # Req #2606: no `closed` column; auto-numbered (no `title`).
    assert 'closed' not in cols
    assert 'title' not in cols


def test_customer_releases_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'customer_releases')
    assert cols['customer_fk']['Null'] == 'NO'
    assert cols['build_fk']['Null'] == 'NO'
    assert cols['release_notes']['Null'] == 'YES'
    assert cols['creator_fk']['Null'] == 'NO'
    assert 'closed' not in cols


# ============================================================================
# Req #2997 — Agents registry column tests
#
# Agent .md files are thin charter stubs; their durable knowledge lives in these
# five tables and is read at boot via darwin://agents/<Agent Name>.
# ============================================================================

def test_agents_columns(db_connection):
    """agents: narrow and FIXED by design (req #2997) — the user does not
    anticipate many new agent-level fields, so there is no JSON column, no
    key-value attribute table, and no spare fields. All growth pressure lands in
    instruction/document ROWS instead.

    No category_fk (infrastructure entity, like machines). name AND file_name are
    both UNIQUE so either resolves an agent unambiguously."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'agents')
    expected = {'id', 'name', 'file_name', 'overview', 'ai_model', 'effort',
                'location', 'closed', 'sort_order', 'creator_fk',
                'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected
    assert 'category_fk' not in cols

    assert cols['id']['Type'] == 'int'
    assert cols['id']['Key'] == 'PRI'
    assert cols['id']['Extra'] == 'auto_increment'

    # The MCP lookup key — matches the charter stub's H1.
    assert cols['name']['Type'] == 'varchar(128)'
    assert cols['name']['Null'] == 'NO'
    assert cols['name']['Key'] == 'UNI'

    assert cols['file_name']['Type'] == 'varchar(128)'
    assert cols['file_name']['Null'] == 'NO'
    assert cols['file_name']['Key'] == 'UNI'

    # Short delegation trigger, mirrored into stub frontmatter `description`.
    assert cols['overview']['Type'] == 'text'
    assert cols['overview']['Null'] == 'YES'

    # ai_model is VARCHAR, not an enum: it holds a RESOLVED model id
    # ('opus[1m]'), which changes with every model release. effort uses Darwin's
    # stable low|medium|high|xhigh|ultracode vocabulary.
    assert cols['ai_model']['Type'] == 'varchar(32)'
    assert cols['ai_model']['Null'] == 'NO'
    assert cols['ai_model']['Default'] == 'opus[1m]'
    assert cols['effort']['Type'] == 'varchar(16)'
    assert cols['effort']['Null'] == 'NO'
    assert cols['effort']['Default'] == 'high'

    assert cols['location']['Type'] == 'varchar(512)'
    assert cols['location']['Null'] == 'YES'

    assert cols['closed']['Type'] == 'tinyint(1)'
    assert cols['closed']['Null'] == 'NO'
    assert cols['closed']['Default'] == '0'
    assert cols['sort_order']['Type'] == 'smallint'
    assert cols['creator_fk']['Type'] == 'varchar(64)'
    assert cols['creator_fk']['Null'] == 'NO'
    assert cols['creator_fk']['Key'] == 'MUL'


def test_instructions_columns(db_connection):
    """instructions: reusable named blocks of BINDING text (req #2997). Its own
    data type precisely so ONE row can bind many agents — the common curating
    duty is a single row referenced by every architect.

    NO sort_order: migration 072 (req #3063) dropped the catalog-order column
    after measuring it byte-identical to agent_instructions.sort_order on all 78
    live rows and driving nothing once the browse-sort control shipped. The
    junction column — the BOOT LOAD ORDER — is asserted separately below and is
    the only instruction ordering left in the schema."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'instructions')
    expected = {'id', 'name', 'content', 'closed', 'creator_fk',
                'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected
    assert 'sort_order' not in cols

    assert cols['id']['Key'] == 'PRI'
    # name is the idempotent-seed key.
    assert cols['name']['Type'] == 'varchar(256)'
    assert cols['name']['Null'] == 'NO'
    assert cols['name']['Key'] == 'UNI'
    assert cols['content']['Type'] == 'text'
    assert cols['content']['Null'] == 'NO'
    assert cols['closed']['Default'] == '0'
    assert cols['creator_fk']['Null'] == 'NO'


def test_agent_instructions_columns(db_connection):
    """agent_instructions: plain junction (req #2997). Composite PK; its
    sort_order is the boot load order — and since migration 072 dropped
    instructions.sort_order, it is the ONLY instruction ordering in the schema.

    The ABSENCE of an `id` column is load-bearing, not incidental (req #3049).
    Lambda-Rest's PUT requires `id`, so the Darwin UI cannot update a link: a
    load-order change is a DELETE + re-POST, and every insert must use an array
    body because the single-object POST path re-reads `WHERE id = ...` and fails
    after committing. Adding an `id` here would silently invalidate that whole
    strategy, so assert it explicitly rather than leaving it implied by the
    column set.

    sort_order STAYS NULLABLE under migration 073 (req #3075). The new
    uq_agent_instructions_slot key constrains NUMBERED slots only; NULL means "no
    slot claimed" and MySQL UNIQUE permits many NULLs per agent. Making the column
    NOT NULL would invent a slot for a link that deliberately has none and would
    break link_agent_instruction's COALESCE contract (req #3049).
    """
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'agent_instructions')
    assert 'id' not in cols, \
        'agent_instructions must have no id column — see Darwin/src/Agents/actions/instructionsApi.js'
    assert set(cols.keys()) == {'agent_fk', 'instruction_fk', 'sort_order'}
    assert cols['agent_fk']['Null'] == 'NO'
    assert cols['agent_fk']['Key'] == 'PRI'
    assert cols['instruction_fk']['Null'] == 'NO'
    assert cols['instruction_fk']['Key'] == 'PRI'
    assert cols['sort_order']['Type'] == 'smallint'
    assert cols['sort_order']['Null'] == 'YES'
    # DESCRIBE reports Key only for the LEADING column of an index, and
    # uq_agent_instructions_slot leads on agent_fk (already 'PRI') — so
    # sort_order's Key stays blank even with the new key in place. The key
    # itself is asserted by SHOW INDEX in the next test, which is the reliable
    # place to look for it.
    assert cols['sort_order']['Key'] == ''


def test_agent_instructions_slot_key_exists(db_connection):
    """migration 073 (req #3075): the per-agent load-slot uniqueness guard.

    Asserted as an index shape rather than only as behaviour because the KEY is
    the whole deliverable — the behavioural half lives in test_constraints.py.
    """
    with db_connection.cursor() as cur:
        cur.execute("SHOW INDEX FROM agent_instructions "
                    "WHERE Key_name = 'uq_agent_instructions_slot'")
        rows = sorted(cur.fetchall(), key=lambda r: r['Seq_in_index'])

    assert rows, 'uq_agent_instructions_slot is missing — migration 073 not applied'
    assert [r['Column_name'] for r in rows] == ['agent_fk', 'sort_order'], \
        'agent_fk must lead: the invariant is per-agent, not global'
    assert all(r['Non_unique'] == 0 for r in rows), 'the key must be UNIQUE'


def test_architecture_documents_columns(db_connection):
    """architecture_documents: THE ONE registry of documents (req #2997).
    agent_documents is a junction of RELATIONSHIPS, not a second document list.

    `location` is the repo-relative path an agent Reads at boot; `url` is the
    clickable form for the Phase 2 UI. Both nullable — a document may be
    registered before either is settled."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'architecture_documents')
    expected = {'id', 'name', 'doc_type', 'location', 'url', 'closed',
                'sort_order', 'creator_fk', 'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected

    assert cols['id']['Key'] == 'PRI'
    assert cols['name']['Type'] == 'varchar(256)'
    assert cols['name']['Null'] == 'NO'
    assert cols['name']['Key'] == 'UNI'
    assert cols['doc_type']['Type'] == 'varchar(16)'
    assert cols['doc_type']['Null'] == 'NO'
    assert cols['doc_type']['Default'] == 'markdown'
    assert cols['location']['Type'] == 'varchar(512)'
    assert cols['location']['Null'] == 'YES'
    assert cols['url']['Type'] == 'varchar(1024)'
    assert cols['url']['Null'] == 'YES'
    assert cols['closed']['Default'] == '0'


def test_agent_documents_columns(db_connection):
    """agent_documents: the many-to-many relationship rows (req #2997).

    owned_document_fk is the mechanism behind 'at most one owned agent per
    document': a VIRTUAL generated column equal to document_fk only on an 'owned'
    row (NULL otherwise), carrying a UNIQUE key. MySQL has no partial index, and
    NULLs are distinct in a UNIQUE key — so unlimited non-owned links coexist
    while a second 'owned' claim raises IntegrityError.

    principles_agent_fk (req #3129) is the same machinery pointed the OTHER WAY:
    one 'owned' link per DOCUMENT, one 'principles' link per AGENT. It is keyed
    on agent_fk, not document_fk — the assertion below is what catches that
    inversion, because both columns are INT/VIRTUAL/UNIQUE and are otherwise
    indistinguishable from a DESCRIBE."""
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'agent_documents')
    expected = {'agent_fk', 'document_fk', 'relationship', 'notes',
                'sort_order', 'owned_document_fk', 'principles_agent_fk'}
    assert set(cols.keys()) == expected

    assert cols['agent_fk']['Null'] == 'NO'
    assert cols['agent_fk']['Key'] == 'PRI'
    assert cols['document_fk']['Null'] == 'NO'
    assert cols['document_fk']['Key'] == 'PRI'
    assert cols['relationship']['Type'] == \
        "set('principles','owned','curated','autoload','referenced')"
    assert cols['relationship']['Null'] == 'NO'
    assert cols['relationship']['Default'] == 'referenced'
    assert cols['notes']['Type'] == 'varchar(512)'
    assert cols['notes']['Null'] == 'YES'

    # The ownership-uniqueness machinery: VIRTUAL (computed on read, no row
    # storage) and UNIQUE.
    assert 'VIRTUAL GENERATED' in cols['owned_document_fk']['Extra'].upper()
    assert cols['owned_document_fk']['Key'] == 'UNI'

    # req #3129: same machinery, opposite key column.
    assert 'VIRTUAL GENERATED' in cols['principles_agent_fk']['Extra'].upper()
    assert cols['principles_agent_fk']['Key'] == 'UNI'


def test_agent_documents_principles_is_keyed_per_agent(db_connection):
    """req #3129 — the generated-column EXPRESSION, not just its shape.

    A DESCRIBE cannot tell principles_agent_fk from owned_document_fk: both are
    INT, VIRTUAL and UNIQUE. Only the expression distinguishes 'one per agent'
    from 'one per document', and getting it backwards would let one agent hold
    many principles documents while forbidding two agents from each having their
    own. Assert the expression text directly."""
    with db_connection.cursor() as cur:
        cur.execute("""
            SELECT COLUMN_NAME, GENERATION_EXPRESSION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'agent_documents'
              AND GENERATION_EXPRESSION <> ''
        """)
        # DictCursor — rows are dicts, not tuples.
        exprs = {r['COLUMN_NAME']: r['GENERATION_EXPRESSION']
                 for r in cur.fetchall()}

    assert set(exprs) == {'owned_document_fk', 'principles_agent_fk'}
    owned = exprs['owned_document_fk'].replace('`', '').replace(' ', '')
    principles = exprs['principles_agent_fk'].replace('`', '').replace(' ', '')

    assert 'owned' in owned and 'document_fk' in owned
    assert 'principles' in principles
    # The whole point: keyed on agent_fk, and NOT on document_fk.
    assert 'agent_fk' in principles
    assert 'document_fk' not in principles


# ============================================================================
# Req #3031 — Agent context telemetry column tests (migration 069)
# ============================================================================

def test_agent_telemetry_runs_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'agent_telemetry_runs')
    expected = {'id', 'captured_at', 'label', 'agent_count', 'harness_version',
                'source_note', 'ai_model', 'effort', 'machine_fk',
                'creator_fk', 'create_ts', 'update_ts'}
    # Req #3202, migration 20260808235540 — the shared telemetry envelope.
    # Tolerated the same way every other table above handles the same
    # dev-before-production window.
    for envelope in ('wall_ms', 'tokens_input', 'tokens_cache_write',
                      'tokens_cache_read', 'tokens_output',
                      'prompt_text', 'prompt_sha256', 'prompt_chars'):
        if envelope in cols:
            expected.add(envelope)
    assert set(cols.keys()) == expected
    assert cols['id']['Key'] == 'PRI'
    assert cols['captured_at']['Null'] == 'NO'
    assert cols['label']['Type'] == 'varchar(256)'
    assert cols['label']['Null'] == 'NO'
    assert cols['agent_count']['Null'] == 'NO'
    assert cols['agent_count']['Default'] == '0'
    assert cols['harness_version']['Type'] == 'varchar(64)'
    assert cols['harness_version']['Null'] == 'YES'
    assert cols['source_note']['Type'] == 'text'
    assert cols['source_note']['Null'] == 'YES'
    # req #3098, migration 075 — fixed default for both backfill and future rows.
    assert cols['ai_model']['Type'] == 'varchar(16)'
    assert cols['ai_model']['Null'] == 'NO'
    assert cols['ai_model']['Default'] == 'opus'
    assert cols['effort']['Type'] == 'varchar(16)'
    assert cols['effort']['Null'] == 'NO'
    assert cols['effort']['Default'] == 'high'
    assert cols['machine_fk']['Null'] == 'YES'
    assert cols['machine_fk']['Key'] == 'MUL'          # indexed FK
    assert cols['creator_fk']['Null'] == 'NO'
    # Log/infra table — no title/status/closed/category_fk/sort_order on the header.
    assert 'title' not in cols
    assert 'closed' not in cols
    assert 'category_fk' not in cols


def test_agent_telemetry_rows_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'agent_telemetry_rows')
    expected = {'id', 'run_fk', 'agent_name', 'role', 'session_kind',
                'boot_time_ms', 'cc_base_tokens',
                'system_prompt_tokens', 'system_tools_tokens', 'mcp_tools_tokens',
                'skills_tokens', 'custom_agents_tokens',
                # req #3472, migration 20260813092839 — the DEFERRED halves of two of
                # those categories under cc-2.1.226+
                'system_tools_deferred_tokens', 'mcp_tools_deferred_tokens',
                'claude_md_tokens',
                'charter_stub_tokens', 'boot_payload_tokens', 'autoload_tokens',
                'docs_loaded', 'docs_expected', 'start_work_context_tokens',
                'footnote', 'sort_order', 'creator_fk', 'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected
    assert cols['id']['Key'] == 'PRI'
    assert cols['run_fk']['Null'] == 'NO'
    assert cols['run_fk']['Key'] == 'MUL'          # indexed FK
    assert cols['agent_name']['Type'] == 'varchar(128)'
    assert cols['agent_name']['Null'] == 'NO'
    assert cols['role']['Type'] == 'varchar(16)'
    assert cols['role']['Null'] == 'NO'
    assert cols['role']['Default'] == 'architect'
    assert cols['session_kind']['Null'] == 'NO'
    assert cols['session_kind']['Default'] == 'subagent'
    # ACTUAL-token columns are nullable (phase may be n/a — PrimaryAI, Code Reviewer).
    for c in ('boot_time_ms', 'cc_base_tokens', 'claude_md_tokens',
              'charter_stub_tokens', 'boot_payload_tokens', 'autoload_tokens',
              'docs_loaded', 'docs_expected', 'start_work_context_tokens',
              # ground-truth CC-base breakdown (req #3095, migration 074) — nullable,
              # a row's breakdown may not have been captured
              'system_prompt_tokens', 'system_tools_tokens', 'mcp_tools_tokens',
              'skills_tokens', 'custom_agents_tokens',
              # req #3472 — deferred halves; nullable for a SECOND reason beyond
              # "not captured": NULL is also how a pre-deferral capture (and a
              # harness that defers nothing) is told apart from a post-deferral one,
              # so a DEFAULT 0 here would erase exactly the distinction it exists for
              'system_tools_deferred_tokens', 'mcp_tools_deferred_tokens'):
        assert cols[c]['Null'] == 'YES', c
        assert cols[c]['Type'] in ('int', 'int(11)'), (c, cols[c]['Type'])
        assert cols[c]['Default'] is None, c
    assert cols['footnote']['Type'] == 'varchar(512)'
    assert cols['footnote']['Null'] == 'YES'
    assert cols['creator_fk']['Null'] == 'NO'


# ============================================================================
# Req #3096 — Per-document actual-token rows (migration 074)
# ============================================================================

def test_agent_telemetry_row_docs_columns(db_connection):
    with db_connection.cursor() as cur:
        cols = _columns(cur, 'agent_telemetry_row_docs')
    expected = {'id', 'row_fk', 'doc_path', 'actual_tokens', 'sort_order',
                'creator_fk', 'create_ts', 'update_ts'}
    assert set(cols.keys()) == expected
    assert cols['id']['Key'] == 'PRI'
    assert cols['row_fk']['Null'] == 'NO'
    assert cols['row_fk']['Key'] == 'MUL'          # indexed FK
    assert cols['doc_path']['Type'] == 'varchar(512)'
    assert cols['doc_path']['Null'] == 'NO'
    # actual_tokens is NOT NULL — unlike the parent row's phase-nullable token
    # columns, a doc row only exists once it has been measured.
    assert cols['actual_tokens']['Null'] == 'NO'
    assert cols['actual_tokens']['Type'] in ('int', 'int(11)')
    assert cols['sort_order']['Type'] == 'smallint'
    assert cols['sort_order']['Null'] == 'YES'
    assert cols['creator_fk']['Null'] == 'NO'
    # Log/infra table like its parent — no title/status/closed/category_fk.
    assert 'title' not in cols
    assert 'closed' not in cols
    assert 'category_fk' not in cols


# ============================================================================
# Req #3111 — Swarm Orchestration 1.0 schema foundation (migration 076): GONE
#
# `epics`, `pipelines`, `pipeline_steps`, `pipeline_step_requirements` and
# `pipeline_step_deps` each had a DESCRIBE test here, plus the two that pinned
# `epics.epic_status` as SUPPRESSION rather than lifecycle and the dep table's
# UNIQUE key. Req #3356 (migration 20260812175325) dropped all five tables and
# the whole section went with them.
#
# The 2.0 successors' shape — including the ABSENT columns, which are the
# load-bearing half (no state column, no seq column, no pipeline reference on a
# step) — is asserted in `tests/test_pipeline2_behaviours.py`.
# ============================================================================
