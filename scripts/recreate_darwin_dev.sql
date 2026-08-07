-- Recreate darwin_dev test/dev tables from scratch
-- Uses production-identical table names (same DDL as schema.sql)
-- Idempotent: safe to run repeatedly to reset darwin_dev to canonical state
-- All 52 tables in FK-dependency order
--
-- ============================================================================
-- THIS FILE DROPS 52 TABLES. (req #3196)
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
DROP TABLE IF EXISTS orchestration_claims,
    pipeline_step_deps, pipeline_step_requirements, pipeline_steps, pipelines,
    agent_telemetry_row_docs, agent_telemetry_rows, agent_telemetry_runs,
    customer_releases, builds, branches, build_projects,
    customers,
    agent_documents, agent_instructions,
    architecture_documents, instructions, agents,
    test_results, test_runs, test_plan_cases, test_plans,
    feature_test_cases, test_cases, features, epics,
    user_integrations,
    map_run_partners, map_partners,
    map_views, map_coordinates, map_runs, map_routes,
    priority_card_order, dev_servers,
    swarm_undos,
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

-- Agile hierarchy: Epic > Feature > Story(requirement) (req #3111, migration 076).
-- `epics` and `features` are created here, above `requirements`, so that
-- requirements.feature_fk resolves — the same reason `machines` sits above the
-- execution tables. The rest of the validation family stays in the "Swarm Features
-- & Test Cases registry" section below.
CREATE TABLE epics (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(256) NOT NULL,
    description  TEXT         NULL,
    epic_status  VARCHAR(16)  NOT NULL DEFAULT 'active',  -- active|paused (req #3223,
                                            -- migration 20260801125029). SUPPRESSION, not
                                            -- lifecycle — see schema.sql for the full note.
    category_fk  INT          NOT NULL,
    creator_fk   VARCHAR(64)  NOT NULL,
    closed       TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order   SMALLINT     NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_epics_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_epics_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE features (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NOT NULL,
    feature_status  VARCHAR(16)     NOT NULL DEFAULT 'draft',   -- draft|active|deprecated
    epic_fk         INT             NULL DEFAULT NULL,
                                            -- parent epic (req #3111, migration 076); NULL = unfiled
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_features_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_features_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_features_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE requirements (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    requirement_status VARCHAR(16)  NOT NULL DEFAULT 'authoring',
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
    ai_model        VARCHAR(16)     NOT NULL,
                                            -- haiku | sonnet | opus | fable (req #2909; NO column default — caller must provide, req #3007)
    effort          VARCHAR(16)     NOT NULL,
                                            -- low | medium | high | xhigh | ultracode (req #2916; NO column default — caller must provide, req #3007)
    sort_order      SMALLINT        NULL DEFAULT NULL,
                                            -- in-card hand-sort position (req #2417); NULL = unranked, falls to id-order
    affected_repos  VARCHAR(255)    NULL DEFAULT NULL,
                                            -- comma-separated sub-repo override (req #2583); NULL = use category default
    machine_fk      INT             NULL DEFAULT NULL,
                                            -- machine pin (req #2978, migration 066); NULL = "Any" machine may run it
    feature_fk      INT             NULL DEFAULT NULL,
                                            -- parent feature (req #3111, migration 076); NULL = unfiled
    tracking        TINYINT(1)      NOT NULL DEFAULT 0,
                                            -- CONTAINER, not work (req #3123): 1 = holds a plan/epic rather than
                                            -- being work inside it, so it is excluded from a pipeline step's
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
    CONSTRAINT fk_requirements_feature
        FOREIGN KEY (feature_fk)
        REFERENCES features (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Swarm session management

-- FK checks relaxed across this one CREATE: `swarm_sessions` forward-references
-- `pipelines`, which this script does not declare until much further down
-- (req #3186). Mirrors the identical relaxation in schema.sql, which this file
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
    -- Orchestration attribution (req #3186, migration 20260801020944): WHICH
    -- PIPELINE / WHICH EPIC this session was advancing. Stamped once at
    -- requirement-link time; NULL = work outside any plan.
    pipeline_fk     INT             NULL DEFAULT NULL,
    epic_fk         INT             NULL DEFAULT NULL,
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
    CONSTRAINT fk_swarm_sessions_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
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
    turn_count          INT             NULL,
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
    CONSTRAINT fk_sss_swarm_start
        FOREIGN KEY (swarm_start_fk) REFERENCES swarm_starts (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
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
    tokens_input        INT             NULL,
    tokens_cache_write  INT             NULL,
    tokens_cache_read   INT             NULL,
    tokens_output       INT             NULL,
    wall_seconds        INT             NULL,
    turn_count          INT             NULL,
    complete_summary    TEXT            NULL,
    telemetry           TEXT            NULL,
    started_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP       NULL,
    creator_fk          VARCHAR(64)     NOT NULL,
    create_ts           TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts           TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_swarm_completes_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
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

-- Swarm Features & Test Cases registry (req #2380)
-- NOTE: `features` is created ABOVE, next to `epics` — requirements.feature_fk
-- (req #3111, migration 076) forced it above `requirements`.

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

CREATE TABLE feature_test_cases (
    feature_fk      INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    PRIMARY KEY (feature_fk, test_case_fk),
    CONSTRAINT fk_ftc_feature
        FOREIGN KEY (feature_fk) REFERENCES features (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ftc_case
        FOREIGN KEY (test_case_fk) REFERENCES test_cases (id)
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
-- Swarm Orchestration — pipelines as data (req #3111, migration 076)
-- ============================================================================
-- A durable multi-requirement execution plan held as data. pipeline_steps
-- deliberately has NO state column (derived from linked requirements — design
-- rule 1), NO seq column (order computed at render — rule 3), and NO epic/feature
-- column (labels attach at the requirement — rule 10). Dependencies are rows,
-- never prose (rule 4).
CREATE TABLE pipelines (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256) NOT NULL,
    description     TEXT         NULL,                     -- the goal
    pipeline_status VARCHAR(16)  NOT NULL DEFAULT 'draft', -- draft|active|paused|completed|aborted
    machine_fk      INT          NULL DEFAULT NULL,
    creator_fk      VARCHAR(64)  NOT NULL,
    started_at      TIMESTAMP    NULL,
    completed_at    TIMESTAMP    NULL,
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pipelines_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pipelines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE pipeline_steps (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,  -- STABLE: never renumbered/reused
    pipeline_fk  INT          NOT NULL,
    title        VARCHAR(256) NOT NULL,
    run          VARCHAR(8)   NOT NULL DEFAULT 'auto',              -- auto|manual
    notes        TEXT         NULL,                                 -- evidence / findings / dispositions
    completed_at TIMESTAMP    NULL,                                 -- manual stamp ONLY for zero-requirement steps
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pipeline_steps_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_pipeline_steps_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_pipeline_steps_pipeline_fk ON pipeline_steps (pipeline_fk);

CREATE TABLE pipeline_step_requirements (
    step_fk        INT NOT NULL,
    requirement_fk INT NOT NULL,
    PRIMARY KEY (step_fk, requirement_fk),
    CONSTRAINT fk_psr_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_psr_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_psr_requirement_fk ON pipeline_step_requirements (requirement_fk);

CREATE TABLE pipeline_step_deps (
    id          INT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    step_fk     INT       NOT NULL,
    dep_step_fk INT       NULL,          -- gate on another step
    time_at     TIMESTAMP NULL,          -- gate on wall clock
    UNIQUE KEY uq_pipeline_step_deps (step_fk, dep_step_fk),
    CONSTRAINT fk_psd_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_psd_dep_step
        FOREIGN KEY (dep_step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_psd_dep_step_fk ON pipeline_step_deps (dep_step_fk);

-- Orchestration reservations (req #3224, migration 20260801150404).
--
-- ADDED BY req #3196, not by #3224: this table reached schema.sql and both live
-- databases but never this file, so a rebuilt darwin_dev came back 12 columns
-- short and every orchestration reservation failed against a table that did not
-- exist. The drift went unseen because the § Schema-of-Record Parity gate that
-- would have caught it could not RUN — both schema.sql and this file were
-- unloadable through load_sql.py until #3196 fixed the statement splitter.

CREATE TABLE orchestration_claims (
    id            INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk   INT          NOT NULL,                -- the plan this claim covers
    epic_fk       INT          NULL DEFAULT NULL,       -- NULL = whole-plan scope
    epic_key      INT          AS (COALESCE(epic_fk, 0)) VIRTUAL,  -- carries the UNIQUE key
    machine_fk    INT          NULL DEFAULT NULL,       -- WHERE it runs
    terminal_pid  INT          NULL DEFAULT NULL,       -- the Claude Code CLI process
    engine_pid    INT          NULL DEFAULT NULL,       -- DIAGNOSTIC ONLY, never liveness
    polls         INT          NOT NULL DEFAULT 0,      -- the heartbeat payload
    claimed_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_fk    VARCHAR(64)  NOT NULL,
    create_ts     TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts     TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,  -- THE liveness clock
    UNIQUE KEY uq_orchestration_claims_scope (pipeline_fk, epic_key),
    CONSTRAINT fk_oc_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_oc_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_oc_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_oc_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_orchestration_claims_epic_fk ON orchestration_claims (epic_fk);
