-- Recreate darwin_dev test/dev tables from scratch
-- Uses production-identical table names (same DDL as schema.sql)
-- Idempotent: safe to run repeatedly to reset darwin_dev to canonical state
-- All 52 tables in FK-dependency order
--
-- ============================================================================
-- THIS FILE DROPS 52 TABLES. (req #3196; count corrected to include
-- requirement_test_cases, req #3378 — it was missing from this file since
-- req #3352 created it; req #3355 dropped the Feature-era catalog table and
-- its test-case junction, migration 20260811033413; req #3356 dropped the
-- 1.0 plan layer — `initiatives`, `pipelines`, `initiatives`,
-- `epic_requirements`, `epic_deps` — migration
-- 20260812175325. Verify via `grep -c '^CREATE TABLE'` on this file)
-- ============================================================================
-- It opened with `USE darwin_dev;`, which LOOKED like protection and was not:
-- a `USE` is a statement the caller's loader may strip, reorder or never reach,
-- so the only thing standing between this file and production was that nobody
-- had typed the wrong database name yet. The two declarations below are the
-- protection, and they are checked BEFORE a connection is opened:
--
--   `darwin:targets` omits `darwin`, which is an ABSOLUTE production ban —
--   no flag in DarwinSQL/scripts/db_guard.py overrides it.
--
--   `darwin:destructive` requires --destructive on the command line, so the
--   reset can never be a careless invocation:
--
--     python3 DarwinSQL/scripts/load_sql.py \
--       DarwinSQL/scripts/recreate_darwin_dev.sql darwin_dev --destructive
--
-- darwin:targets = darwin_dev
-- darwin:destructive

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS requirement_debug_captures,
    engine_inputs, engine_outcomes, engine_decision_records,
    engine_heartbeats, engine_states,
    orchestration_claims,
    initiative_deps, epic_deps, epic_requirements, epics,
    initiatives, pipelines,
    agent_telemetry_row_docs, agent_telemetry_rows, agent_telemetry_runs,
    customer_releases, builds, branches, build_projects,
    customers,
    agent_documents, agent_instructions,
    architecture_documents, instructions, agents,
    test_results, test_runs, test_plan_cases, test_plans,
    requirement_test_cases, test_cases,
    user_integrations,
    map_run_partners, map_partners,
    map_views, map_coordinates, map_runs, map_routes,
    priority_card_order, dev_servers,
    swarm_undos,
    branch_acceptance_tests, acceptance_tests,
    swarm_complete_sessions, swarm_completes,
    swarm_start_sessions, swarm_starts,
    requirement_sessions,
    requirements, swarm_sessions, machines, categories, projects,
    tasks, recurring_tasks, areas, domains, profiles;
SET FOREIGN_KEY_CHECKS = 1;

-- Core domain model

CREATE TABLE profiles (
    id              VARCHAR(64)     NOT NULL PRIMARY KEY,
    name            VARCHAR(256)    NOT NULL,
    email           VARCHAR(256)    NOT NULL,
    timezone        VARCHAR(64)     NULL,
    theme_mode      VARCHAR(8)      NOT NULL DEFAULT 'light',
    app_tasks       TINYINT(1)      NOT NULL DEFAULT 1,
    app_maps        TINYINT(1)      NOT NULL DEFAULT 1,
    app_swarm       TINYINT(1)      NOT NULL DEFAULT 0,
    app_solar       TINYINT(1)      NOT NULL DEFAULT 0,
    app_swarm_validate TINYINT(1)   NOT NULL DEFAULT 0,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE domains (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    domain_name     VARCHAR(32)     NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT         NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE areas (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    area_name       VARCHAR(32)     NOT NULL,
    domain_fk       INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT         NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    sort_mode       VARCHAR(8)      NOT NULL DEFAULT 'priority',
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (domain_fk)
        REFERENCES domains (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE recurring_tasks (
    id               INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    description      VARCHAR(1024)   NOT NULL,
    recurrence       VARCHAR(16)     NOT NULL,
    anchor_date      DATE            NOT NULL,
    area_fk          INT             NOT NULL,
    priority         TINYINT(1)      NOT NULL DEFAULT 0,
    accumulate       TINYINT(1)      NOT NULL DEFAULT 0,
    insert_position  VARCHAR(8)      NOT NULL DEFAULT 'bottom',
    active           TINYINT(1)      NOT NULL DEFAULT 1,
    last_generated   DATE            NULL,
    creator_fk       VARCHAR(64)     NOT NULL,
    create_ts        TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts        TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (area_fk)
        REFERENCES areas (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE tasks (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    priority        BOOLEAN         NOT NULL,
    done            BOOLEAN         NOT NULL,
    description     VARCHAR(1024)   NOT NULL,
    area_fk         INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    done_ts         TIMESTAMP       NULL,
    sort_order      SMALLINT        NULL,
    recurring_task_fk INT           NULL,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (area_fk)
        REFERENCES areas (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (recurring_task_fk)
        REFERENCES recurring_tasks (id)
        ON DELETE SET NULL
);

-- Roadmap / requirement tracking

CREATE TABLE projects (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    project_name    VARCHAR(128)    NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    sort_order      SMALLINT        NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE categories (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    category_name   VARCHAR(128)    NOT NULL,
    project_fk      INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    sort_order      SMALLINT        NULL,
    sort_mode       VARCHAR(8)      NOT NULL DEFAULT 'hand',
    color           VARCHAR(9)      NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_fk)
        REFERENCES projects (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Machine registry (req #2943) — created before the execution tables that
-- reference it via machine_fk.
CREATE TABLE machines (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(256) NOT NULL,
    description  TEXT         NULL,
    hostname     VARCHAR(128) NOT NULL,
    platform     VARCHAR(16)  NOT NULL,           -- darwin | wsl | linux
    arch         VARCHAR(16)  NOT NULL,           -- arm64 | x86_64
    os_version   VARCHAR(64)  NULL,
    hw_model     VARCHAR(64)  NULL,
    last_seen_at TIMESTAMP    NULL,
    max_live_sessions SMALLINT NOT NULL DEFAULT 20,
    closed       TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order   SMALLINT     NULL,
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_machines_hostname (hostname),
    CONSTRAINT fk_machines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- The 1.0 agile hierarchy (`initiatives`, req #3111 migration 076) was created here,
-- above `requirements`. It was dropped whole at req #3356, migration
-- 20260812175325, with the rest of the 1.0 plan layer; 2.0's own initiative table is
-- `initiatives`, further down, and is contained by its pipeline rather than
-- standing above `requirements`. (The middle organizing tier that once sat
-- between Initiative and Story, and the requirement column that pointed into it,
-- had already gone at req #3355, migration 20260811033413.)

CREATE TABLE requirements (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    requirement_status VARCHAR(16)  NOT NULL DEFAULT 'swarm_ready',
                                            -- authoring | approved | swarm_ready | development | met | deferred | wontfix
    started_at      TIMESTAMP       NULL,
    completed_at    TIMESTAMP       NULL,
    deferred_at     TIMESTAMP       NULL,
    project_fk      INT             NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    coordination_type VARCHAR(16)   NOT NULL DEFAULT 'implemented',
                                            -- discuss | planned | implemented | deployed (mandatory, req #2745; default: implemented)
    ai_model        VARCHAR(16)     NOT NULL DEFAULT 'opus',
                                            -- haiku | sonnet | opus | fable (req #2909; DEFAULT 'opus' since req #3434,
                                            -- migration 20260814132630, reversing req #3007 — an omitted NOT NULL
                                            -- VARCHAR with no DEFAULT stores '' under non-strict sql_mode)
    effort          VARCHAR(16)     NOT NULL DEFAULT 'high',
                                            -- low | medium | high | xhigh | ultracode (req #2916; DEFAULT 'high' since
                                            -- req #3434, migration 20260814132630 — same reversal, same reasoning)
    sort_order      SMALLINT        NULL DEFAULT NULL,
                                            -- in-card hand-sort position (req #2417); NULL = unranked, falls to id-order
    affected_repos  VARCHAR(255)    NULL DEFAULT NULL,
                                            -- comma-separated sub-repo override (req #2583); NULL = use category default
    machine_fk      INT             NULL DEFAULT NULL,
                                            -- machine pin (req #2978, migration 066); NULL = "Any" machine may run it
    tracking        TINYINT(1)      NOT NULL DEFAULT 0,
                                            -- CONTAINER, not work (req #3123): 1 = holds a plan/initiative rather than
                                            -- being work inside it, so it is excluded from a pipeline epic's
                                            -- gating set (design rule 1) and its /swarm-start args (rule 8)
    FOREIGN KEY (project_fk)
        REFERENCES projects (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_requirements_category
        FOREIGN KEY (category_fk)
        REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_requirements_machine
        FOREIGN KEY (machine_fk)
        REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Swarm session management

-- FK checks relaxed across this one CREATE: `swarm_sessions` forward-references
-- `pipelines`, which this script does not declare until much further
-- down (req #3350). Mirrors the identical relaxation in schema.sql, which this file
-- must stay column-for-column identical to (see memory/database.md § parity gate).
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE swarm_sessions (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    branch          VARCHAR(128)    NULL,
    task_name       VARCHAR(128)    NULL,
    source_type     VARCHAR(16)     NULL,
    source_ref      VARCHAR(64)     NULL,
    title           VARCHAR(256)    NULL,
    pr_url          VARCHAR(512)    NULL,
    swarm_status    VARCHAR(16)     NOT NULL DEFAULT 'starting',
    ai_model        VARCHAR(16)     NOT NULL DEFAULT 'opus',
                                            -- haiku | sonnet | opus | fable (req #2909; captured at launch, default: opus)
    effort          VARCHAR(16)     NOT NULL DEFAULT 'high',
                                            -- low | medium | high | xhigh | ultracode (req #2916; captured at launch, default: xhigh)
    worktree_path   VARCHAR(512)    NULL,
    machine_fk      INT             NULL,          -- req #2943
    -- Terminal window identity (req #3455, migration 20260810013244).
    terminal_window_id VARCHAR(64)  NULL DEFAULT NULL,
    terminal_number INT             NULL DEFAULT NULL,
    -- 2.0 orchestration attribution (req #3350, migration 20260809081441):
    -- WHICH PLAN / WHICH INITIATIVE this session was advancing. Stamped once at
    -- requirement-link time; NULL = work outside any plan. (The 1.0 pair,
    -- `pipeline_fk`/`initiative_fk`, req #3186, was archived and dropped at
    -- req #3356, migration 20260812175325.)
    pipeline_fk     INT             NULL DEFAULT NULL,
    initiative_fk         INT             NULL DEFAULT NULL,
    started_at      TIMESTAMP       NULL,
    completed_at    TIMESTAMP       NULL,
    -- Phase accumulators (req #2332, migration 059)
    last_transition_at TIMESTAMP    NULL,
    starting_secs   INT             NOT NULL DEFAULT 0,
    waiting_secs    INT             NOT NULL DEFAULT 0,
    planning_secs   INT             NOT NULL DEFAULT 0,
    implementing_secs INT           NOT NULL DEFAULT 0,
    review_secs     INT             NOT NULL DEFAULT 0,
    completion_secs INT             NOT NULL DEFAULT 0,
    paused_secs     INT             NOT NULL DEFAULT 0,
    legacy_secs     INT             NOT NULL DEFAULT 0,
    instrumented    TINYINT         NOT NULL DEFAULT 1,
    pre_pause_status VARCHAR(16)    NULL,
    -- Per-phase TOKEN consumption (req #2839, migration 060). Parallel to the
    -- *_secs timing buckets: on each swarm_status change db.py diffs the supplied
    -- cumulative token count against tokens_at_last_transition and accrues the
    -- per-type delta into the bucket for the phase being left.
    phase_tokens    JSON            NULL,
    tokens_at_last_transition JSON  NULL,
    -- Cost rollup (req #3117, migration 077) — flat sums of the *_secs buckets
    -- and phase_tokens[*].output, readable from a projected list read.
    wall_secs_total INT             NULL,
    output_tokens_total INT         NULL,
    -- Shared telemetry envelope (req #3202, migration 20260808235540).
    wall_ms         BIGINT          NULL,
    tokens_input    INT             NULL,
    tokens_cache_write INT          NULL,
    tokens_cache_read INT           NULL,
    tokens_output   INT             NULL,
    prompt_text     TEXT            NULL,
    prompt_sha256   CHAR(64)        NULL,
    prompt_chars    INT             NULL,
    start_summary   TEXT            NULL,
    complete_summary TEXT           NULL,
    telemetry       TEXT            NULL,
    plan            TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_swarm_sessions_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_swarm_sessions_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_swarm_sessions_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE requirement_sessions (
    requirement_fk  INT             NOT NULL,
    session_fk      INT             NOT NULL,
    PRIMARY KEY (requirement_fk, session_fk),
    FOREIGN KEY (requirement_fk)
        REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (session_fk)
        REFERENCES swarm_sessions (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE swarm_starts (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    arguments           VARCHAR(512)    NULL,
    autonomy_filter     VARCHAR(16)     NULL,
    auto_start          TINYINT(1)      NOT NULL DEFAULT 0,
    session_count       INT             NOT NULL DEFAULT 0,
    ai_model            VARCHAR(16)     NOT NULL DEFAULT 'opus',  -- req #2949
    effort              VARCHAR(16)     NOT NULL DEFAULT 'high',  -- req #2949
    machine_fk          INT             NULL,          -- req #2943
    tokens_input        INT             NULL,
    tokens_cache_write  INT             NULL,
    tokens_cache_read   INT             NULL,
    tokens_output       INT             NULL,
    wall_seconds        INT             NULL,
    -- Shared telemetry envelope (req #3202, migration 20260808235540).
    wall_ms             BIGINT          NULL,
    turn_count          INT             NULL,
    prompt_text         TEXT            NULL,
    prompt_sha256       CHAR(64)        NULL,
    prompt_chars        INT             NULL,
    start_summary       TEXT            NULL,
    telemetry           TEXT            NULL,
    started_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_fk          VARCHAR(64)     NOT NULL,
    create_ts           TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts           TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_swarm_starts_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_swarm_starts_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE swarm_start_sessions (
    swarm_start_fk  INT             NOT NULL,
    session_fk      INT             NOT NULL,
    PRIMARY KEY (swarm_start_fk, session_fk),
    -- ON DELETE RESTRICT (not CASCADE — req #3382, migration 20260814170847):
    -- a swarm_start with linked sessions must not silently lose that history
    -- when the parent row is deleted through a path that skips the
    -- application-level guard in delete_swarm_start.
    CONSTRAINT fk_sss_swarm_start
        FOREIGN KEY (swarm_start_fk) REFERENCES swarm_starts (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_sss_session
        FOREIGN KEY (session_fk) REFERENCES swarm_sessions (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE swarm_completes (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    skill_name          VARCHAR(64)     NOT NULL,
    coordination_type   VARCHAR(16)     NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'in_progress',
    session_count       INT             NOT NULL DEFAULT 0,
    ai_model            VARCHAR(16)     NOT NULL DEFAULT 'opus',  -- req #2949
    effort              VARCHAR(16)     NOT NULL DEFAULT 'high',  -- req #2949
    -- req #3202, migration 20260809002208 — which machine ran the closeout.
    machine_fk          INT             NULL,
    tokens_input        INT             NULL,
    tokens_cache_write  INT             NULL,
    tokens_cache_read   INT             NULL,
    tokens_output       INT             NULL,
    wall_seconds        INT             NULL,
    -- Shared telemetry envelope (req #3202, migration 20260808235540).
    wall_ms             BIGINT          NULL,
    turn_count          INT             NULL,
    prompt_text         TEXT            NULL,
    prompt_sha256       CHAR(64)        NULL,
    prompt_chars        INT             NULL,
    complete_summary    TEXT            NULL,
    telemetry           TEXT            NULL,
    started_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP       NULL,
    creator_fk          VARCHAR(64)     NOT NULL,
    create_ts           TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts           TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_swarm_completes_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_swarm_completes_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE swarm_complete_sessions (
    swarm_complete_fk   INT             NOT NULL,
    session_fk          INT             NOT NULL,
    PRIMARY KEY (swarm_complete_fk, session_fk),
    CONSTRAINT fk_scs_swarm_complete
        FOREIGN KEY (swarm_complete_fk) REFERENCES swarm_completes (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_scs_session
        FOREIGN KEY (session_fk) REFERENCES swarm_sessions (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE swarm_undos (
    id                       INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    session_fk               INT             NULL,
    swarm_start_fk_at_undo   INT             NULL,
    req_id_at_undo           INT             NULL,
    task_name                VARCHAR(255)    NULL,
    branch                   VARCHAR(255)    NULL,
    coordination_type        VARCHAR(16)     NULL,
    reason                   TEXT            NOT NULL,
    undone_at                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_fk               VARCHAR(64)     NOT NULL,
    create_ts                TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts                TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_swarm_undos_session
        FOREIGN KEY (session_fk) REFERENCES swarm_sessions (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_swarm_undos_swarm_start
        FOREIGN KEY (swarm_start_fk_at_undo) REFERENCES swarm_starts (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_swarm_undos_req
        FOREIGN KEY (req_id_at_undo) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_swarm_undos_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    KEY ix_swarm_undos_swarm_start_fk_at_undo (swarm_start_fk_at_undo),
    KEY ix_swarm_undos_undone_at (undone_at)
);

-- Dev server port coordination

CREATE TABLE dev_servers (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    port            SMALLINT        NOT NULL,
    pid             INT             NOT NULL,
    terminal_number SMALLINT        NULL,
    workspace_path  VARCHAR(512)    NOT NULL,
    session_fk      INT             NULL,
    machine_fk      INT             NULL,          -- req #2943
    creator_fk      VARCHAR(64)     NOT NULL,
    started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    -- req #2943: per-machine port uniqueness (ports are machine-local)
    UNIQUE KEY uq_machine_port (machine_fk, port),
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (session_fk)
        REFERENCES swarm_sessions (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_dev_servers_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- Priority card hand-sort order

CREATE TABLE priority_card_order (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    domain_id       INT             NOT NULL,
    task_id         INT             NOT NULL,
    sort_order      SMALLINT        NOT NULL,
    UNIQUE KEY uq_domain_task (domain_id, task_id)
);

-- Maps — Cyclemeter ride/hike data

CREATE TABLE map_routes (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    route_id        BIGINT          NOT NULL,
    name            VARCHAR(256)    NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_creator_route (creator_fk, route_id),
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE map_runs (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    run_id          BIGINT          NOT NULL,
    map_route_fk    INT             NULL,
    activity_id     INT             NOT NULL,
    activity_name   VARCHAR(16)     NOT NULL,
    start_time      DATETIME        NOT NULL,
    run_time_sec    INT             NOT NULL,
    stopped_time_sec INT            NOT NULL DEFAULT 0,
    distance_mi     DECIMAL(6,1)    NOT NULL,
    ascent_ft       INT             NULL,
    descent_ft      INT             NULL,
    calories        INT             NULL,
    max_speed_mph   DECIMAL(5,1)    NULL,
    avg_speed_mph   DECIMAL(5,2)    NULL,
    notes           TEXT            NULL,
    source          VARCHAR(32)     NOT NULL DEFAULT 'cyclemeter',
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_creator_run (creator_fk, run_id),
    FOREIGN KEY (map_route_fk)
        REFERENCES map_routes (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE map_coordinates (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    map_run_fk      INT             NOT NULL,
    seq             INT             NOT NULL,
    latitude        DECIMAL(10,7)   NOT NULL,
    longitude       DECIMAL(10,7)   NOT NULL,
    altitude        DECIMAL(7,1)    NULL,
    FOREIGN KEY (map_run_fk)
        REFERENCES map_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    -- req #3166: composite, REPLACING the old idx_map_coordinates_run.
    -- `map_run_fk` is the leftmost prefix, so it still satisfies the FK.
    INDEX idx_map_coordinates_run_seq (map_run_fk, seq)
);

CREATE TABLE map_views (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(10)     NOT NULL,
    criteria        JSON            NOT NULL,
    sort_order      SMALLINT        NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE map_partners (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(64)     NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_creator_partner (creator_fk, name),
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE map_run_partners (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    map_run_fk      INT             NOT NULL,
    map_partner_fk  INT             NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_run_partner (map_run_fk, map_partner_fk),
    FOREIGN KEY (map_run_fk)
        REFERENCES map_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (map_partner_fk)
        REFERENCES map_partners (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Third-party integrations (migration 036) — OAuth tokens for external services

CREATE TABLE user_integrations (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    creator_fk      VARCHAR(36)     NOT NULL,
    provider        VARCHAR(50)     NOT NULL,
    access_token    TEXT            NOT NULL,
    refresh_token   TEXT            NOT NULL,
    expires_at      INT             NOT NULL,
    athlete_data    JSON            NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_creator_provider (creator_fk, provider)
);

-- Swarm Test Cases registry (req #2380). The Feature-era catalog table
-- (created here until req #3355 dropped it, migration 20260811033413) used
-- to force this section above `requirements`; test_cases has no such
-- dependency of its own.

CREATE TABLE test_cases (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    preconditions   TEXT            NULL,
    steps           TEXT            NOT NULL,
    expected        TEXT            NOT NULL,
    test_type       VARCHAR(16)     NOT NULL DEFAULT 'manual',
    tags            VARCHAR(512)    NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_cases_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_cases_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- requirement_test_cases (req #3352, migration 20260809002149) — Pipeline 2.0
-- re-homes test cases from Feature onto Requirement: a test case asserts a
-- deliverable and Requirement, not Feature, is the level that organizes
-- deliverables. Its predecessor junction was dropped at req #3355, migration
-- 20260811033413.
CREATE TABLE requirement_test_cases (
    requirement_fk  INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    PRIMARY KEY (requirement_fk, test_case_fk),
    CONSTRAINT fk_rtc_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_rtc_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- requirement_debug_captures (req #3815, migration 20261023103433) — the
-- Requirement Filer Bug button's debug capture, one row per requirement. A side
-- table because the bundle (7.5-44.4 KB measured, ~254 K chars at the caps)
-- outgrows requirements.description and must never ride into a list read; it is
-- read one row at a time by requirement id (darwin://requirement-debug/{id}).
CREATE TABLE requirement_debug_captures (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    requirement_fk  INT          NOT NULL,               -- the requirement the Bug button filed
    bundle          MEDIUMTEXT   NOT NULL,               -- the capture JSON, uncompressed
    bundle_bytes    INT          NOT NULL DEFAULT 0,     -- its length, as the browser serialized it
    creator_fk      VARCHAR(64)  NOT NULL,
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_requirement_debug_captures_req (requirement_fk),
    CONSTRAINT fk_rdc_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_rdc_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_plans (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_plans_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_plans_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_plan_cases (
    test_plan_fk    INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    sort_order      SMALLINT        NULL,
    PRIMARY KEY (test_plan_fk, test_case_fk),
    CONSTRAINT fk_tpc_plan
        FOREIGN KEY (test_plan_fk) REFERENCES test_plans (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_tpc_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_runs (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    test_plan_fk    INT             NOT NULL,
    run_status      VARCHAR(16)     NOT NULL DEFAULT 'in_progress',
    started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP       NULL,
    notes           TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_runs_plan
        FOREIGN KEY (test_plan_fk) REFERENCES test_plans (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_runs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE test_results (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    test_run_fk     INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    result_status   VARCHAR(16)     NOT NULL DEFAULT 'not_run',
    actual          TEXT            NULL,
    notes           TEXT            NULL,
    executed_at     TIMESTAMP       NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_test_results_run
        FOREIGN KEY (test_run_fk) REFERENCES test_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_test_results_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_test_results_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_run_case UNIQUE KEY (test_run_fk, test_case_fk)
);

-- Req #2604: customers — recipients of build releases.
CREATE TABLE customers (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    customer_name   VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_customers_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================================================================
-- Req #2606: Build Visualizer data model. Trunk is identified by
-- build_projects.trunk_branch_fk (a project links to its trunk branch).
-- No parent_branch_fk on branches: a branch originates from a Build via
-- parent_build_fk; the parent BRANCH is builds[parent_build_fk].branch_fk.
-- No segment columns: branches carry M.m; builds carry the computed-once
-- M.m.B.b values. No `closed` soft-delete columns. Two circular FKs
-- (branches.parent_build_fk <-> builds.branch_fk;
-- build_projects.trunk_branch_fk <-> branches.project_fk) require FK checks
-- disabled for this block (the top-of-file SET ...=1 re-enabled them after the
-- DROP), so wrap the build tables in their own FOREIGN_KEY_CHECKS=0 guard —
-- mirrors schema.sql's build-section guard. In migration 050 they're deferred ALTERs.
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE build_projects (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    project_status  VARCHAR(16)     NOT NULL DEFAULT 'draft', -- draft|active|archived
    trunk_branch_fk INT             NULL, -- FK declared at bottom (circular: -> branches)
    sort_order      SMALLINT        NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_build_projects_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_build_projects_trunk_branch
        FOREIGN KEY (trunk_branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE branches (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    project_fk          INT             NOT NULL,
    branch_type         VARCHAR(32)     NOT NULL,
    name                TEXT            NULL,
    major               INT             NOT NULL,
    minor               INT             NOT NULL,
    parent_build_fk     INT             NULL,
    side                VARCHAR(16)     NULL,
    row_order           INT             NULL,
    label_end           VARCHAR(128)    NULL,
    sort_order          SMALLINT        NULL,
    external_id         VARCHAR(64)     NULL,
    acceptance_test_status VARCHAR(16)  NULL DEFAULT 'pass', -- single per-branch AT pass|fail — req #2633 / migration 061
    branched_at         DATETIME        NULL,     -- req #3515
    creator_fk          VARCHAR(64)     NOT NULL,
    create_ts           TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts           TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_branches_project_external (project_fk, external_id),
    CONSTRAINT fk_branches_project
        FOREIGN KEY (project_fk) REFERENCES build_projects (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_branches_parent_build
        FOREIGN KEY (parent_build_fk) REFERENCES builds (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_branches_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE builds (
    id                      INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    branch_fk               INT             NOT NULL,
    position                SMALLINT        NOT NULL,
    build_number            INT             NOT NULL,
    branch_number           INT             NOT NULL DEFAULT 0,
    major                   INT             NOT NULL DEFAULT 0,
    minor                   INT             NOT NULL DEFAULT 0,
    dot_color               VARCHAR(32)     NULL,
    approved_for_release    TINYINT(1)      NOT NULL DEFAULT 0,
    external_id             VARCHAR(64)     NULL,
    built_at                DATETIME        NULL,        -- req #3515
    creator_fk              VARCHAR(64)     NOT NULL,
    create_ts               TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts               TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_builds_branch_external (branch_fk, external_id),
    CONSTRAINT fk_builds_branch
        FOREIGN KEY (branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_builds_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_builds_branch_position UNIQUE KEY (branch_fk, position)
);

CREATE TABLE customer_releases (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    customer_fk     INT             NOT NULL,
    build_fk        INT             NOT NULL,
    release_notes   TEXT            NULL,
    released_at     DATETIME        NULL,     -- req #3515
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer_releases_customer
        FOREIGN KEY (customer_fk) REFERENCES customers (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_customer_releases_build
        FOREIGN KEY (build_fk) REFERENCES builds (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_customer_releases_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_customer_releases_customer_build UNIQUE KEY (customer_fk, build_fk)
);

-- Req #2633: Acceptance Tests (AT). Catalog + branch junction (migration 061).
CREATE TABLE acceptance_tests (
    id                      INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title                   VARCHAR(256)    NOT NULL,
    description             TEXT            NULL,
    acceptance_test_status  VARCHAR(16)     NOT NULL DEFAULT 'pass',  -- pass|fail
    expected_wall_mins      INT             NULL,                     -- user-set expected wall clock, minutes
    closed                  TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order              SMALLINT        NULL,
    creator_fk              VARCHAR(64)     NOT NULL,
    create_ts               TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts               TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_acceptance_tests_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE branch_acceptance_tests (
    branch_fk           INT         NOT NULL,
    acceptance_test_fk  INT         NOT NULL,
    sort_order          SMALLINT    NULL,
    PRIMARY KEY (branch_fk, acceptance_test_fk),
    CONSTRAINT fk_bat_branch
        FOREIGN KEY (branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_bat_acceptance_test
        FOREIGN KEY (acceptance_test_fk) REFERENCES acceptance_tests (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

SET FOREIGN_KEY_CHECKS = 1;

-- Agents registry (req #2997, migration 067). Production tables, mirrored here
-- so a rebuilt darwin_dev matches schema.sql column-for-column.
CREATE TABLE agents (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(128) NOT NULL,
    file_name   VARCHAR(128) NOT NULL,
    overview    TEXT         NULL,
    ai_model    VARCHAR(32)  NOT NULL DEFAULT 'opus[1m]',
    effort      VARCHAR(16)  NOT NULL DEFAULT 'high',
    location    VARCHAR(512) NULL,
    closed      TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order  SMALLINT     NULL,
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_agents_name (name),
    UNIQUE KEY uq_agents_file_name (file_name),
    CONSTRAINT fk_agents_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE instructions (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(256) NOT NULL,
    content     TEXT         NOT NULL,
    closed      TINYINT(1)   NOT NULL DEFAULT 0,
    -- NO sort_order (migration 072) — see schema.sql.
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_instructions_name (name),
    CONSTRAINT fk_instructions_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE agent_instructions (
    agent_fk        INT      NOT NULL,
    instruction_fk  INT      NOT NULL,
    sort_order      SMALLINT NULL,       -- boot load order
    PRIMARY KEY (agent_fk, instruction_fk),
    -- req #3075, migration 073: one agent may not load two instructions at the
    -- same NUMBERED slot. NULL claims no slot, and MySQL UNIQUE permits many
    -- NULLs — that is the intended scope, not a gap.
    UNIQUE KEY uq_agent_instructions_slot (agent_fk, sort_order),
    CONSTRAINT fk_ai_agent
        FOREIGN KEY (agent_fk) REFERENCES agents (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ai_instruction
        FOREIGN KEY (instruction_fk) REFERENCES instructions (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE architecture_documents (
    id          INT           NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(256)  NOT NULL,
    doc_type    VARCHAR(16)   NOT NULL DEFAULT 'markdown',
    location    VARCHAR(512)  NULL,
    url         VARCHAR(1024) NULL,
    closed      TINYINT(1)    NOT NULL DEFAULT 0,
    sort_order  SMALLINT      NULL,
    creator_fk  VARCHAR(64)   NOT NULL,
    create_ts   TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP     NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_architecture_documents_name (name),
    CONSTRAINT fk_architecture_documents_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE agent_documents (
    agent_fk           INT          NOT NULL,
    document_fk        INT          NOT NULL,
    relationship       SET('principles','owned','curated','autoload','referenced') NOT NULL DEFAULT 'referenced',
    notes              VARCHAR(512) NULL,
    sort_order         SMALLINT     NULL,
    owned_document_fk  INT          AS (IF(FIND_IN_SET('owned', relationship) > 0, document_fk, NULL)) VIRTUAL,
    -- req #3129: mirror image of the owner rule -- one 'owned' per DOCUMENT,
    -- one 'principles' per AGENT. The key column differs on purpose.
    principles_agent_fk INT         AS (IF(FIND_IN_SET('principles', relationship) > 0, agent_fk, NULL)) VIRTUAL,
    PRIMARY KEY (agent_fk, document_fk),
    UNIQUE KEY uq_agent_documents_owner (owned_document_fk),
    UNIQUE KEY uq_agent_documents_principles (principles_agent_fk),
    CONSTRAINT fk_ad_agent
        FOREIGN KEY (agent_fk) REFERENCES agents (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ad_document
        FOREIGN KEY (document_fk) REFERENCES architecture_documents (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Agent Context Telemetry (req #3031, migration 069) — run header + N per-agent
-- rows (parent/child, run is the container -> CASCADE). ACTUAL-token captures.
CREATE TABLE agent_telemetry_runs (
    id               INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    captured_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    label            VARCHAR(256) NOT NULL,
    agent_count      INT          NOT NULL DEFAULT 0,
    harness_version  VARCHAR(64)  NULL,
    source_note      TEXT         NULL,
    ai_model         VARCHAR(16)  NOT NULL DEFAULT 'opus',
    effort           VARCHAR(16)  NOT NULL DEFAULT 'high',
    -- Shared telemetry envelope (req #3202, migration 20260808235540).
    wall_ms          BIGINT       NULL,
    tokens_input     INT          NULL,
    tokens_cache_write INT        NULL,
    tokens_cache_read INT         NULL,
    tokens_output    INT          NULL,
    prompt_text      TEXT         NULL,
    prompt_sha256    CHAR(64)     NULL,
    prompt_chars     INT          NULL,
    machine_fk       INT          NULL,
    creator_fk       VARCHAR(64)  NOT NULL,
    create_ts        TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts        TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_runs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_agent_telemetry_runs_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_agent_telemetry_runs_captured_at ON agent_telemetry_runs (captured_at);

CREATE TABLE agent_telemetry_rows (
    id                          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    run_fk                      INT          NOT NULL,
    agent_name                  VARCHAR(128) NOT NULL,
    role                        VARCHAR(16)  NOT NULL DEFAULT 'architect',
    session_kind                VARCHAR(16)  NOT NULL DEFAULT 'subagent',
    boot_time_ms                INT          NULL,
    cc_base_tokens              INT          NULL,
    system_prompt_tokens        INT          NULL,   -- harness instructions (req #3095, migration 074)
    system_tools_tokens         INT          NULL,   -- built-in tool schemas (req #3095, migration 074)
    mcp_tools_tokens            INT          NULL,   -- MCP tools/resources listing (req #3095, migration 074)
    skills_tokens               INT          NULL,   -- available-skills listing (req #3095, migration 074)
    custom_agents_tokens        INT          NULL,   -- other-custom-agent listing (req #3095, migration 074)
    system_tools_deferred_tokens INT         NULL,   -- deferred built-in tool schemas (req #3472, migration 20260813)
    mcp_tools_deferred_tokens   INT          NULL,   -- deferred MCP tool schemas (req #3472, migration 20260813)
    claude_md_tokens            INT          NULL,
    charter_stub_tokens         INT          NULL,
    boot_payload_tokens         INT          NULL,
    autoload_tokens             INT          NULL,
    docs_loaded                 INT          NULL,
    docs_expected               INT          NULL,
    start_work_context_tokens   INT          NULL,
    footnote                    VARCHAR(512) NULL,
    sort_order                  SMALLINT     NULL,
    creator_fk                  VARCHAR(64)  NOT NULL,
    create_ts                   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts                   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_rows_run
        FOREIGN KEY (run_fk) REFERENCES agent_telemetry_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_agent_telemetry_rows_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_agent_telemetry_rows_run_fk ON agent_telemetry_rows (run_fk);

-- Per-document actual-token breakdown (req #3096, migration 074) — child of
-- agent_telemetry_rows only, row_fk CASCADEs.
CREATE TABLE agent_telemetry_row_docs (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    row_fk          INT          NOT NULL,
    doc_path        VARCHAR(512) NOT NULL,
    actual_tokens   INT          NOT NULL,
    sort_order      SMALLINT     NULL,
    creator_fk      VARCHAR(64)  NOT NULL,
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_row_docs_row
        FOREIGN KEY (row_fk) REFERENCES agent_telemetry_rows (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_agent_telemetry_row_docs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_agent_telemetry_row_docs_row_fk ON agent_telemetry_row_docs (row_fk);

-- ============================================================================
-- Swarm Orchestration 1.0 (req #3111, migration 076) — DROPPED
-- ============================================================================
-- The first-generation `pipelines`, `epics`,
-- `epic_requirements`, `epic_deps` and `initiatives` were
-- declared here, along with the 1.0 attribution columns on `swarm_sessions`
-- and `orchestration_claims`. All were dropped whole at req #3356
-- (migration 20260812175325); the five tables below are the surviving
-- second-generation plan layer, renamed into these freed plain names in
-- the same requirement's second half (migration 20260812184333). They
-- carry the design rules the first generation expressed (no state column,
-- no seq column, dependencies as rows).

-- ---------------------------------------------------------------------------
-- FIVE tables standing BESIDE the 1.0 five, not replacing them. Both eras run
-- at once until 1.0 is eradicated, and requirements are NOT doubled: one
-- `requirements` table carries two plan layers above it, because duplicating a
-- requirement row would split its sessions, history and identity across two ids
-- for the same work.
--
-- CONTAINMENT IS IN THE DDL, NOT IN CONVENTION. An initiative belongs to exactly one
-- pipeline and an epic to exactly one initiative, both NOT NULL. That single change is
-- what removes the session-attribution tie-break, gives initiative pause a scope key,
-- makes reservation scoping a containment question rather than an inferred one,
-- and turns display order into a tree walk.
--
-- Containment STOPS at Requirement: an epic ORGANIZES requirements and does not
-- own them, so membership is an edge table. Three levels of ownership, one of
-- membership — the one asymmetry in the chain, and deliberate.

CREATE TABLE pipelines (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256) NOT NULL,
    description     TEXT         NULL,                     -- the goal; PURPOSE only (design rule 11)
    pipeline_status VARCHAR(16)  NOT NULL DEFAULT 'draft', -- draft|active|paused|completed|aborted
    locked          TINYINT(1)   NOT NULL DEFAULT 0,      -- req #3649: 1 = a relic in time; freezes
                                                          -- the plan, its initiatives and epics (gateway-
                                                          -- enforced, Lambda-Rest/plan_lock.py)
    closed          TINYINT(1)   NOT NULL DEFAULT 0,      -- req #3804: 1 = closed (hidden; launch-suppressed)
    sort_order      INT          NULL DEFAULT NULL,        -- req #3804: hand-sorted card position, asc
    machine_fk      INT          NULL DEFAULT NULL,        -- NULL = any machine
    creator_fk      VARCHAR(64)  NOT NULL,
    started_at      TIMESTAMP    NULL,                     -- derived from the status transition
    completed_at    TIMESTAMP    NULL,                     -- ditto; never passed by a caller
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pipelines_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pipelines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- `pipeline_fk` NOT NULL is the containment. An initiative cannot float free and
-- cannot be reached from a second plan, which is what makes `initiative_status` a
-- scoped pause rather than a global one: 1.0's initiative pause has no scope key, so
-- pausing an initiative pauses it in every plan holding it.
--
-- `category_fk` is DISPLAY ONLY and gates nothing. An initiative owns its epics; it
-- does not govern their attributes, and the work of one initiative routinely spans
-- several categories. It must not be read by orchestration, launch, repo
-- resolution or any eligibility predicate — the category that matters is the one
-- on the requirement, which the requirement already carries.
--
-- `sort_order` IS LOAD-BEARING HERE, unlike in 1.0. A dependency edge may not
-- cross an initiative, so initiative order is the ONLY way to sequence one initiative after
-- another. NULLABLE, no default (stage-2 gate ruling, req #3336, supersedes
-- this record's original NOT NULL DEFAULT 0): NULL = derived order (started
-- initiatives by start date earliest-first, unstarted after in creation order); a
-- non-NULL value is manual placement and wins over the derivation.
CREATE TABLE initiatives (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk INT          NOT NULL,                     -- CONTAINMENT
    title       VARCHAR(256) NOT NULL,
    description TEXT         NULL,                         -- PURPOSE only (design rule 11)
    initiative_status VARCHAR(16)  NOT NULL DEFAULT 'active',    -- active|paused; SUPPRESSION, not lifecycle
    locked      TINYINT(1)   NOT NULL DEFAULT 0,           -- req #3649: freezes this initiative and its epics
    category_fk INT          NOT NULL,                     -- DISPLAY ONLY; gates nothing
    sort_order  SMALLINT     NULL,                         -- NULL=derived order; value=manual, wins
    closed      TINYINT(1)   NOT NULL DEFAULT 0,           -- finished; distinct from paused
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_initiatives_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_initiatives_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_initiatives_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_initiatives_pipeline_fk ON initiatives (pipeline_fk);

-- NO `pipeline_fk`. An epic's pipeline is its initiative's, and § 6 shows the composed
-- read costs one FEWER gateway read without it, not one more — so storing both
-- would buy nothing and cost the invariant that they agree.
--
-- `initiative_fk` NOT NULL also deletes a derivation. In 1.0 an epic's initiative is reached
-- by walking from its requirements through the now-dropped Feature tier's own
-- initiative link, and an epic with no requirements INHERITS the label from a
-- dependency: 17 of the 188 live epics
-- do exactly that. Here the initiative is stored, so `label_inherited` and the whole
-- inheritance walk stop existing.
--
-- `not_before` is the time gate, as a column. 1.0 holds it as a ROW in the
-- dependency table, which forces that table to carry two condition kinds and
-- forces every derivation to branch on which kind a row is. One instant per epic
-- is the same capability with one fewer shape: several time gates on one epic is
-- not a lost capability, because the latest instant always wins and is therefore
-- one value. ZERO of the 175 live dependency rows is a time gate, so this is
-- kept for its stated future use — organising around token windows — and not
-- because anything depends on it today.
--
-- An epic has NO STATE and no completion stamp (req #3750; its dead
-- `completed_at` was dropped by req #3752, migration 20261022024615). It holds
-- requirements and carries orchestration controls — `run`, `checkpoint`,
-- `locked`, `not_before` and its dependency edges; every orchestration question
-- is asked of the requirements it holds.
CREATE TABLE epics (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,  -- STABLE: never renumbered/reused
    initiative_fk      INT          NOT NULL,                     -- CONTAINMENT; the pipeline is derived
    title        VARCHAR(256) NOT NULL,
    run          VARCHAR(8)   NOT NULL DEFAULT 'auto',      -- auto|manual
    checkpoint   TINYINT(1)   NOT NULL DEFAULT 1
        COMMENT 'req #3649/#3750: 1 = holds every downstream epic while it holds open work; 0 = launch priority only',
    locked       TINYINT(1)   NOT NULL DEFAULT 0,           -- req #3649: freezes this epic
    not_before   TIMESTAMP    NULL,                         -- the time gate, one instant per epic
    notes        TEXT         NULL,                         -- evidence / findings / dispositions
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_epics_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_epics_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_epics_initiative_fk ON epics (initiative_fk);

-- Membership, not ownership. CASCADE on both sides, the junction default.
-- `epic_fk` because the links are the epic's own data; `requirement_fk` since
-- req #3706 (migration 20261021060108), which reversed the original RESTRICT:
-- deleting a requirement is the user's intent and its seat goes with it,
-- exactly as `unlink_epic_requirement` would remove it. The epic survives. A
-- LOCKED plan is still protected — the gateway refuses (423) deleting a
-- requirement seated on an effectively locked epic (Lambda-Rest plan_lock.py).
--
-- Points at the SHARED `requirements` table, not at a doubled copy. Held here
-- rather than as a column on `requirements` because during the parallel era that
-- column would have to be doubled on the core table for the whole migration,
-- which is the mess the parallel-table scheme exists to avoid.
--
-- PRIMARY KEY (requirement_fk) ALONE — stage-2 gate ruling, req #3336, supersedes
-- this record's original composite PK: ONE EPIC PER REQUIREMENT, structural (a
-- requirement must not run twice; duplicate it if it needs to run 2). `epic_fk`
-- stays NOT NULL beside it. No `ix_p2_psr_requirement_fk`: the PK already serves
-- lookup by `requirement_fk`, and the `fk_er_epic` FK auto-index covers
-- lookup by `epic_fk` for the composed read.
CREATE TABLE epic_requirements (
    epic_fk        INT NOT NULL,
    requirement_fk INT NOT NULL PRIMARY KEY,
    CONSTRAINT fk_er_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_er_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ONE ROW = ONE EDGE, and nothing else. The time gate left this table for a
-- column on the epic, so `dep_epic_fk` is NOT NULL and the row has exactly one
-- meaning — no condition-kind discriminator, no derivation branching on which
-- kind a row is.
--
-- THAT NOT NULL IS WHAT MAKES THE UNIQUE KEY TOTAL. 1.0 declares a
-- byte-identical `UNIQUE (epic_fk, dep_epic_fk)` that does NOT prevent
-- duplicates, because `dep_epic_fk` is nullable there and MySQL treats NULLs in
-- a UNIQUE index as DISTINCT — so 1.0 can hold two time-gate rows on one epic
-- with no constraint objecting. (Same NULL semantics that force
-- `orchestration_claims.initiative_key` to exist.) Nothing exploits it today: 0 of the
-- 175 live rows is a time gate.
--
-- The surrogate `id` is RETAINED deliberately, not by inertia. `delete(table,
-- ids=[...])` is the REST client's one-round-trip bulk primitive and the only one
-- with gateway-level cross-tenant test coverage; it targets `id`. ONE live code
-- path uses it on the 1.0 dep table -- `delete_pipeline`, which deletes a whole
-- plan's edges at once and is exactly the case a per-row delete would punish.
-- (The other two dep deletes use the `where`-dict form and need no `id`.)
-- Dropping the column would buy nothing the composite UNIQUE key does not
-- already give.
--
-- `dep_epic_fk` RESTRICT is design rule 4's teeth: an epic something else gates
-- on cannot be deleted or merged away.
--
-- AN EDGE MAY NOT CROSS AN INITIATIVE, and the schema cannot say so — the constraint
-- is between two rows' parents. Enforced in the service layer, the same place
-- the cycle check and the cross-pipeline check already live.
CREATE TABLE epic_deps (
    id          INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    epic_fk     INT NOT NULL,
    dep_epic_fk INT NOT NULL,                              -- NOT NULL: the time gate is an epic column now
    UNIQUE KEY uq_epic_deps (epic_fk, dep_epic_fk),
    CONSTRAINT fk_ed_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ed_dep_epic
        FOREIGN KEY (dep_epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_ed_dep_epic_fk ON epic_deps (dep_epic_fk);

-- Initiative-to-initiative dependencies (req #3823, migration 20261024111150).
-- ONE ROW = ONE EDGE: `initiative_fk` waits for ALL of `dep_initiative_fk` —
-- no epic under it launches while any epic under the dependency holds open
-- work. A GATE, unlike an `epic_deps` edge (a launch priority since req
-- #3597); the hold is DERIVED on every read (Lambda-Rest pipeline2_derive.py),
-- never stored. `initiative_fk` CASCADE (an initiative's own edges are its
-- data); `dep_initiative_fk` RESTRICT (design rule 4, as on `epic_deps`: an
-- initiative something waits on cannot be deleted until the edge is removed).
-- Same plan, no self-edge, no cycle on the combined initiative + epic graph:
-- rules between two rows' parents, enforced at the gateway
-- (Lambda-Rest initiative_deps_guard.py).
CREATE TABLE initiative_deps (
    id                INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    initiative_fk     INT NOT NULL,                         -- the initiative that waits
    dep_initiative_fk INT NOT NULL,                         -- the initiative it waits for
    UNIQUE KEY uq_initiative_deps (initiative_fk, dep_initiative_fk),
    CONSTRAINT fk_id_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_id_dep_initiative
        FOREIGN KEY (dep_initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_id_dep_initiative_fk ON initiative_deps (dep_initiative_fk);

-- Orchestration reservations (req #3224, migration 20260801150404).
--
-- ADDED BY req #3196, not by #3224: this table reached schema.sql and both live
-- databases but never this file, so a rebuilt darwin_dev came back 12 columns
-- short and every orchestration reservation failed against a table that did not
-- exist. The drift went unseen because the § Schema-of-Record Parity gate that
-- would have caught it could not RUN — both schema.sql and this file were
-- unloadable through load_sql.py until #3196 fixed the statement splitter.
--
-- It served BOTH ERAS from req #3369 (migration 20260809024954) until req #3356
-- (migration 20260812175325) dropped the 1.0 half — `pipeline_fk`, `initiative_fk`,
-- the generated `initiative_key`, `uq_orchestration_claims_scope`, both 1.0 FKs and
-- `ix_orchestration_claims_initiative_fk` — leaving the 2.0 scope pair alone. See
-- schema.sql for the full rationale. Placed here, after the plan layer, because
-- it carries a live FK into it.

CREATE TABLE orchestration_claims (
    id            INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk   INT          NULL DEFAULT NULL,       -- scope; NULL only if initiative_fk names it
    initiative_fk       INT          NULL DEFAULT NULL,       -- NULL = whole-plan scope
    initiative_key      INT          AS (COALESCE(initiative_fk, 0)) VIRTUAL, -- carries uq_..._scope
    machine_fk    INT          NULL DEFAULT NULL,       -- WHERE it runs
    machine_key   INT          AS (COALESCE(machine_fk, 0)) VIRTUAL, -- req #3678, carries uq_..._scope
    terminal_pid  INT          NULL DEFAULT NULL,       -- the Claude Code CLI process
    engine_pid    INT          NULL DEFAULT NULL,       -- DIAGNOSTIC ONLY, never liveness
    polls         INT          NOT NULL DEFAULT 0,      -- the heartbeat payload
    claimed_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_fk    VARCHAR(64)  NOT NULL,
    create_ts     TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts     TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,  -- THE liveness clock
    UNIQUE KEY uq_orchestration_claims_scope (pipeline_fk, initiative_key, machine_key),
    CONSTRAINT fk_oc_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_oc_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_oc_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_oc_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_orchestration_claims_initiative_fk ON orchestration_claims (initiative_fk);

-- ---------------------------------------------------------------------------
-- Orchestration Engine 2 data contract (req #3756, migration 20261022073056).
-- The rows the engine publishes and the UI reads (memory/engine-rules.md R2,
-- R4, R5, R6, R7, R8, R12). Each table has exactly one writer:
--   engine_states            desired on/off (the UI) + actual state (the supervisor)
--   engine_heartbeats        location + health (the engine); beat_at is the DB clock,
--                            separate so a desired-state flip can never stamp a beat
--   engine_decision_records  one per cycle per scope; the record JSON + input hashes
--   engine_outcomes          the executor's pending/landed/failed per admitted item —
--                            outside the record, whose id is the hash of its body
--   engine_inputs            decide() inputs stored once by content hash
-- Retention: darwin-mcp services/engine2.py `retention_plan`, constants in
-- scripts/swarm/engine2/contracts/storage.json.
-- ---------------------------------------------------------------------------

CREATE TABLE engine_states (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk     INT          NOT NULL,                -- scope: the plan
    initiative_fk         INT          NULL DEFAULT NULL,       -- scope: NULL = whole plan
    initiative_key        INT          AS (COALESCE(initiative_fk, 0)) VIRTUAL, -- carries uq_engine_states_scope
    machine_fk      INT          NOT NULL,                -- desired state is per scope PER MACHINE (R6)
    desired_state   VARCHAR(8)   NOT NULL DEFAULT 'off',  -- on | off — the UI's switch
    desired_reason  VARCHAR(32)  NULL DEFAULT NULL,       -- user | drained | ...
    desired_at      TIMESTAMP    NULL DEFAULT NULL,
    actual_state    VARCHAR(16)  NOT NULL DEFAULT 'stopped', -- stopped | starting | running | stopping | crashed
    actual_detail   VARCHAR(255) NULL DEFAULT NULL,
    actual_at       TIMESTAMP    NULL DEFAULT NULL,
    creator_fk      VARCHAR(64)  NOT NULL,
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_engine_states_scope (pipeline_fk, initiative_key, machine_fk),
    CONSTRAINT fk_es_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_es_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_es_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_es_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_engine_states_initiative_fk ON engine_states (initiative_fk);

CREATE TABLE engine_heartbeats (
    id               INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    engine_state_fk  INT          NOT NULL,               -- one heartbeat row per engine state
    claim_fk         INT          NULL DEFAULT NULL,      -- R7: the claim it holds; NULL once released
    terminal_pid     INT          NULL DEFAULT NULL,      -- R7
    engine_pid       INT          NULL DEFAULT NULL,      -- R7
    role             VARCHAR(16)  NULL DEFAULT NULL,      -- R7: lead | subscriber | refused
    beats            INT          NOT NULL DEFAULT 0,     -- the heartbeat payload; MUST change every beat
    health           JSON         NULL,                   -- R4: heartbeat.schema.json `health`
    creator_fk       VARCHAR(64)  NOT NULL,
    create_ts        TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    beat_at          TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP, -- THE liveness clock (DB time)
    UNIQUE KEY uq_engine_heartbeats_state (engine_state_fk),
    CONSTRAINT fk_eh_state
        FOREIGN KEY (engine_state_fk) REFERENCES engine_states (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_eh_claim
        FOREIGN KEY (claim_fk) REFERENCES orchestration_claims (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_eh_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE engine_decision_records (
    id                 INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    record_hash        CHAR(71)     NOT NULL,             -- the record's own id: 'sha256:' + 64 hex
    prior_hash         CHAR(71)     NULL DEFAULT NULL,    -- the record's prior_id
    pipeline_fk        INT          NOT NULL,             -- location.scope.pipeline_id
    initiative_fk            INT          NULL DEFAULT NULL,    -- location.scope.initiative_id
    machine_fk         INT          NULL DEFAULT NULL,    -- location.machine_fk
    claim_id           INT          NULL DEFAULT NULL,    -- location.claim_id — history, deliberately no FK
    seq                INT          NOT NULL,             -- cycle.seq
    cycle_at           DATETIME     NULL DEFAULT NULL,    -- cycle.now, UTC
    verdict            VARCHAR(32)  NOT NULL,             -- cycle.verdict: OK or the ENGINE_HOLD verdict
    admitted_count     SMALLINT     NOT NULL DEFAULT 0,   -- queue items coded ADMITTED
    queue_count        SMALLINT     NOT NULL DEFAULT 0,
    cut                SMALLINT     NOT NULL DEFAULT 0,
    plan_payload_hash  CHAR(71)     NOT NULL,             -- inputs.* — R12
    capacity_hash      CHAR(71)     NOT NULL,
    claims_hash        CHAR(71)     NOT NULL,
    clock_hash         CHAR(71)     NOT NULL,
    prior_record_hash  CHAR(71)     NULL DEFAULT NULL,
    record             JSON         NOT NULL,             -- the whole record, decision_record.schema.json
    record_bytes       INT          NOT NULL DEFAULT 0,   -- canonical serialisation size, for the cost check
    creator_fk         VARCHAR(64)  NOT NULL,
    create_ts          TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_engine_decision_records_hash (creator_fk, record_hash),
    KEY ix_engine_decision_records_scope (pipeline_fk, initiative_fk, machine_fk, id),
    CONSTRAINT fk_edr_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_edr_initiative
        FOREIGN KEY (initiative_fk) REFERENCES initiatives (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_edr_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_edr_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_engine_decision_records_initiative_fk ON engine_decision_records (initiative_fk);
CREATE INDEX ix_engine_decision_records_machine_fk ON engine_decision_records (machine_fk);

CREATE TABLE engine_outcomes (
    id              INT           NOT NULL PRIMARY KEY AUTO_INCREMENT,
    record_fk       INT           NOT NULL,               -- the record that ADMITTED it
    requirement_fk  INT           NOT NULL,
    epic_fk         INT           NULL DEFAULT NULL,
    outcome_state   VARCHAR(16)   NOT NULL DEFAULT 'pending', -- pending | landed | failed
    session_ids     JSON          NULL,                   -- landed: the swarm_sessions ids
    reason          VARCHAR(512)  NULL DEFAULT NULL,      -- failed: why
    creator_fk      VARCHAR(64)   NOT NULL,
    create_ts       TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP     NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_engine_outcomes_item (record_fk, requirement_fk),
    CONSTRAINT fk_eo_record
        FOREIGN KEY (record_fk) REFERENCES engine_decision_records (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_eo_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_eo_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_eo_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_engine_outcomes_requirement_fk ON engine_outcomes (requirement_fk);

CREATE TABLE engine_inputs (
    id            INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    content_hash  CHAR(71)     NOT NULL,                  -- 'sha256:' + hex of the canonical body
    input_kind    VARCHAR(16)  NOT NULL,                  -- plan_payload | capacity | claims | clock | prior_record (first writer's)
    body          JSON         NOT NULL,
    body_bytes    INT          NOT NULL DEFAULT 0,
    creator_fk    VARCHAR(64)  NOT NULL,
    create_ts     TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_engine_inputs_hash (creator_fk, content_hash),
    CONSTRAINT fk_ei_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
