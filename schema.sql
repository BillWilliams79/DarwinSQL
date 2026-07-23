-- Darwin Database Schema — Current State
-- Database: darwin
-- This file reflects the final state of all 44 tables after all migrations.
-- It can be run against a fresh MySQL instance to create the complete schema.
-- Table order respects FK dependencies.

CREATE DATABASE IF NOT EXISTS darwin;
USE darwin;

-- ============================================================================
-- Core domain model: profiles → domains → areas → tasks
-- ============================================================================

CREATE TABLE IF NOT EXISTS profiles (
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

CREATE TABLE IF NOT EXISTS domains (
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

CREATE TABLE IF NOT EXISTS areas (
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

CREATE TABLE IF NOT EXISTS recurring_tasks (
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

CREATE TABLE IF NOT EXISTS tasks (
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

-- ============================================================================
-- Roadmap / requirement tracking (darwin-mcp)
-- ============================================================================

CREATE TABLE IF NOT EXISTS projects (
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

CREATE TABLE IF NOT EXISTS categories (
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

-- ============================================================================
-- Machine registry (req #2943)
-- ============================================================================
-- Content table: which machine (Mac mini / WSL box / …) ran a swarm_session,
-- swarm_start, or dev_server claim. Auto-registered on first swarm activity by
-- scripts/swarm/machine-identity.sh (matched by UNIQUE hostname). Defined BEFORE
-- the execution tables so their machine_fk FKs resolve on a fresh schema run.
-- No category_fk — infrastructure entity, not categorized.
CREATE TABLE IF NOT EXISTS machines (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(256) NOT NULL,           -- friendly name; auto-registration seeds it with hostname
    description  TEXT         NULL,
    hostname     VARCHAR(128) NOT NULL,           -- auto-detected; the auto-match key; UNIQUE
    platform     VARCHAR(16)  NOT NULL,           -- darwin | wsl | linux
    arch         VARCHAR(16)  NOT NULL,           -- arm64 | x86_64
    os_version   VARCHAR(64)  NULL,               -- sw_vers (macOS) / os-release PRETTY_NAME (Linux/WSL)
    hw_model     VARCHAR(64)  NULL,               -- sysctl hw.model (macOS) / best-effort WSL; NULL when unavailable
    last_seen_at TIMESTAMP    NULL,               -- auto-updated on each identity resolution
    closed       TINYINT(1)   NOT NULL DEFAULT 0, -- retire a machine
    sort_order   SMALLINT     NULL,
    creator_fk   VARCHAR(64)  NOT NULL,
    create_ts    TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts    TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_machines_hostname (hostname),
    CONSTRAINT fk_machines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS requirements (
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
                                            -- haiku | sonnet | opus | fable (req #2909; NO column default — caller must provide, req #3007; pre-#2909 rows assumed opus)
    effort          VARCHAR(16)     NOT NULL,
                                            -- low | medium | high | xhigh | ultracode (req #2916; NO column default — caller must provide, req #3007; pre-#2916 rows assumed high)
    sort_order      SMALLINT        NULL DEFAULT NULL,
                                            -- in-card hand-sort position (req #2417); NULL = unranked, falls to id-order
    affected_repos  VARCHAR(255)    NULL DEFAULT NULL,
                                            -- comma-separated sub-repo override (req #2583); NULL = use category default
    machine_fk      INT             NULL DEFAULT NULL,
                                            -- machine pin (req #2978, migration 066); NULL = "Any" machine may run it
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

-- ============================================================================
-- Swarm session management
-- ============================================================================

CREATE TABLE IF NOT EXISTS swarm_sessions (
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
                                            -- low | medium | high | xhigh | ultracode (req #2916; captured at launch, default bumped to high, req #3007)
    worktree_path   VARCHAR(512)    NULL,
    machine_fk      INT             NULL,          -- req #2943; which machine ran this session
    started_at      TIMESTAMP       NULL,
    completed_at    TIMESTAMP       NULL,
    -- Phase accumulators (req #2332). On each swarm_status change db.py adds
    -- NOW()-last_transition_at to the bucket for the phase being left.
    last_transition_at TIMESTAMP    NULL,
    starting_secs   INT             NOT NULL DEFAULT 0,
    waiting_secs    INT             NOT NULL DEFAULT 0,
    planning_secs   INT             NOT NULL DEFAULT 0,
    implementing_secs INT           NOT NULL DEFAULT 0,
    review_secs     INT             NOT NULL DEFAULT 0,
    completion_secs INT             NOT NULL DEFAULT 0,
    paused_secs     INT             NOT NULL DEFAULT 0,
    legacy_secs     INT             NOT NULL DEFAULT 0,  -- pre-instrumentation lump (instrumented=0)
    instrumented    TINYINT         NOT NULL DEFAULT 1,
    pre_pause_status VARCHAR(16)    NULL,                -- status before entering 'paused' (resume-restore)
    -- Per-phase TOKEN consumption (req #2839, migration 060). Parallel to the
    -- *_secs timing buckets: on each swarm_status change db.py diffs the supplied
    -- cumulative token count against tokens_at_last_transition and accrues the
    -- per-type delta into the bucket for the phase being left.
    --   phase_tokens: { "<phase>": {input,cache_write,cache_read,output}, ... }
    --     (phase keys mirror the *_secs set: starting/waiting/planning/
    --      implementing/review/completion/paused). NULL = no token instrumentation.
    --   tokens_at_last_transition: { input,cache_write,cache_read,output } baseline.
    phase_tokens    JSON            NULL,
    tokens_at_last_transition JSON  NULL,
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
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS requirement_sessions (
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

-- swarm_starts: one row per /swarm-start invocation. Execution table — no
-- closed flag, no sort_order (chronological by started_at), no category_fk
-- (a launch can span categories), no title (arguments string is the label).
-- Token / wall / turn / summary / telemetry columns are NULL until skill-finalize
-- captures them at end-of-run; populated via update_swarm_start.
-- ai_model/effort (req #2949, migration 065): normalized, queryable copy of
-- the same fact buried in the telemetry JSON blob — mirrors swarm_sessions.
CREATE TABLE IF NOT EXISTS swarm_starts (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    arguments           VARCHAR(512)    NULL,
    autonomy_filter     VARCHAR(16)     NULL,
    auto_start          TINYINT(1)      NOT NULL DEFAULT 0,
    session_count       INT             NOT NULL DEFAULT 0,
    ai_model            VARCHAR(16)     NOT NULL DEFAULT 'opus',
    effort              VARCHAR(16)     NOT NULL DEFAULT 'high',
    machine_fk          INT             NULL,          -- req #2943; which machine ran this start
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

CREATE TABLE IF NOT EXISTS swarm_start_sessions (
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

-- swarm_completes: one row per /swarm-complete or /primary-ai-swarm-complete
-- invocation (req #2497). The close-out counterpart to swarm_starts (migration
-- 046). Execution table — no closed flag, no sort_order (chronological by
-- completed_at), no category_fk, no title. Deviates from the launch side in six
-- fields: skill_name (which closeout ran), coordination_type (NULL for primary),
-- status (in_progress|ok|error), completed_at (finalize timestamp), and
-- complete_summary (mirrors swarm_sessions.complete_summary). Token / wall / turn
-- / summary / telemetry columns are NULL until the skill's finalize step writes
-- them via update_swarm_complete.
-- ai_model/effort (req #2949, migration 065): normalized, queryable copy of
-- the same fact buried in the telemetry JSON blob — mirrors swarm_starts.
CREATE TABLE IF NOT EXISTS swarm_completes (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    skill_name          VARCHAR(64)     NOT NULL,
    coordination_type   VARCHAR(16)     NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'in_progress',
    session_count       INT             NOT NULL DEFAULT 0,
    ai_model            VARCHAR(16)     NOT NULL DEFAULT 'opus',
    effort              VARCHAR(16)     NOT NULL DEFAULT 'high',
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

CREATE TABLE IF NOT EXISTS swarm_complete_sessions (
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

-- swarm_undos: one row per /swarm-undo invocation. Execution table — no
-- closed flag, no sort_order (chronological by undone_at), no category_fk
-- (inherits from the session/requirement being undone). Captures a mandatory
-- free-text reason from the user plus snapshot metadata so the record survives
-- the session-row deletion that /swarm-undo performs immediately afterwards.
CREATE TABLE IF NOT EXISTS swarm_undos (
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

-- ============================================================================
-- Dev server port coordination
-- ============================================================================

CREATE TABLE IF NOT EXISTS dev_servers (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    port            SMALLINT        NOT NULL,
    pid             INT             NOT NULL,
    terminal_number SMALLINT        NULL,
    workspace_path  VARCHAR(512)    NOT NULL,
    session_fk      INT             NULL,
    machine_fk      INT             NULL,          -- req #2943; which machine hosts this dev server
    creator_fk      VARCHAR(64)     NOT NULL,
    started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    -- req #2943: ports are machine-local; per-machine uniqueness replaces the
    -- old global uq_port so two machines don't falsely contend for 3000-3007.
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

-- ============================================================================
-- Priority card hand-sort order
-- ============================================================================

CREATE TABLE IF NOT EXISTS priority_card_order (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    domain_id       INT             NOT NULL,
    task_id         INT             NOT NULL,
    sort_order      SMALLINT        NOT NULL,
    UNIQUE KEY uq_domain_task (domain_id, task_id)
);

-- ============================================================================
-- Maps — Cyclemeter ride/hike data
-- ============================================================================

CREATE TABLE IF NOT EXISTS map_routes (
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

CREATE TABLE IF NOT EXISTS map_runs (
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

CREATE TABLE IF NOT EXISTS map_coordinates (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    map_run_fk      INT             NOT NULL,
    seq             INT             NOT NULL,
    latitude        DECIMAL(10,7)   NOT NULL,
    longitude       DECIMAL(10,7)   NOT NULL,
    altitude        DECIMAL(7,1)    NULL,
    FOREIGN KEY (map_run_fk)
        REFERENCES map_runs (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_map_coordinates_run (map_run_fk)
);

CREATE TABLE IF NOT EXISTS map_views (
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

CREATE TABLE IF NOT EXISTS map_partners (
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

CREATE TABLE IF NOT EXISTS map_run_partners (
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

-- ============================================================================
-- Third-party integrations (req — migration 036)
-- OAuth tokens for external services (e.g., Strava). DB-backed so tokens
-- persist across devices. Lambda-Rest auto-scopes via creator_fk.
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_integrations (
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

-- ============================================================================
-- Swarm Features & Test Cases registry (req #2380 — migrations 042/043/044)
-- Phase 1: features + test_cases + feature_test_cases
-- Phase 2: test_plans + test_plan_cases
-- Phase 3: test_runs + test_results
-- ============================================================================

CREATE TABLE IF NOT EXISTS features (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NOT NULL,
    feature_status  VARCHAR(16)     NOT NULL DEFAULT 'draft',   -- draft|active|deprecated
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_features_category
        FOREIGN KEY (category_fk) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_features_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS test_cases (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    preconditions   TEXT            NULL,
    steps           TEXT            NOT NULL,
    expected        TEXT            NOT NULL,
    test_type       VARCHAR(16)     NOT NULL DEFAULT 'manual',  -- manual|automated|hybrid
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

CREATE TABLE IF NOT EXISTS feature_test_cases (
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

CREATE TABLE IF NOT EXISTS test_plans (
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

CREATE TABLE IF NOT EXISTS test_plan_cases (
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

CREATE TABLE IF NOT EXISTS test_runs (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    test_plan_fk    INT             NOT NULL,
    run_status      VARCHAR(16)     NOT NULL DEFAULT 'in_progress', -- in_progress|completed|aborted
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

CREATE TABLE IF NOT EXISTS test_results (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    test_run_fk     INT             NOT NULL,
    test_case_fk    INT             NOT NULL,
    result_status   VARCHAR(16)     NOT NULL DEFAULT 'not_run',     -- passed|failed|blocked|skipped|not_run
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

-- Req #2604: customers — recipients of build releases (HP, NVIDIA, Cisco, …).
-- The Build Visualizer attaches `customer-release` branches to build dots to
-- visualize which customer received which sprint/end-release build.
CREATE TABLE IF NOT EXISTS customers (
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
-- Req #2606: Build Visualizer data model — projects, branches, builds,
-- customer-release events. Trunk = the branch a project's trunk_branch_fk
-- points at (no boolean flag on branches). Branch carries M.m; build carries
-- the COMPUTED-ONCE-AT-CREATION M.m.B.b values (no segments, no walk at
-- render). A branch originates from a Build via parent_build_fk; the parent
-- BRANCH is derivable via builds[parent_build_fk].branch_fk (no
-- parent_branch_fk). No soft-delete `closed` on any of these tables.
--
-- Two circular FKs (build_projects.trunk_branch_fk <-> branches; and
-- branches.parent_build_fk <-> builds) require deferred ALTERs to land. The
-- migration file uses that pattern; for the schema dump we disable FK checks
-- around the block so a fresh `mysql < schema.sql` install still succeeds.
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS build_projects (
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

CREATE TABLE IF NOT EXISTS branches (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    project_fk          INT             NOT NULL,
    branch_type         VARCHAR(32)     NOT NULL, -- release|sample-release|hotfix|bootleg|csr|development
    name                TEXT            NULL,     -- multi-line allowed (\n stacks vertically)
    major               INT             NOT NULL, -- M.m stored on the branch (compute-once on create)
    minor               INT             NOT NULL,
    parent_build_fk     INT             NULL,     -- FK -> builds(id) SET NULL; NULL on trunk only
    side                VARCHAR(16)     NULL,
    row_order           INT             NULL,
    label_end           VARCHAR(128)    NULL,
    sort_order          SMALLINT        NULL,
    external_id         VARCHAR(64)     NULL,     -- iframe slug ('main', 'release-1', 'dev-a') — req #2648 / migration 051
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

CREATE TABLE IF NOT EXISTS builds (
    id                      INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    branch_fk               INT             NOT NULL,
    position                SMALLINT        NOT NULL,    -- 0-indexed order within branch
    build_number            INT             NOT NULL,    -- B in M.m.B.b — computed once at creation
    branch_number           INT             NOT NULL DEFAULT 0, -- b in M.m.B.b — 0 for trunk
    major                   INT             NOT NULL DEFAULT 0, -- M in M.m.B.b — stamped at creation (req #2720)
    minor                   INT             NOT NULL DEFAULT 0, -- m in M.m.B.b — stamped at creation (req #2720)
    dot_color               VARCHAR(32)     NULL,        -- green|red|yellow|gray
    approved_for_release    TINYINT(1)      NOT NULL DEFAULT 0,
    external_id             VARCHAR(64)     NULL,        -- iframe slug ('m1', 'r1c', 'sr3') — req #2648 / migration 051
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

CREATE TABLE IF NOT EXISTS customer_releases (
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
-- (Req #2606 directive: `closed` soft-delete column removed from every new
-- build-feature table. Hard delete via FK CASCADE chain only.)

-- Req #2633: Acceptance Tests (AT). Catalog + branch junction. Follows the
-- build-viz CATALOG shape (mirrors `customers`: closed + sort_order, no
-- category_fk). branches.acceptance_test_status (added above) is the single
-- per-branch pass|fail. Migration 061. darwin_dev only.
CREATE TABLE IF NOT EXISTS acceptance_tests (
    id                      INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title                   VARCHAR(256)    NOT NULL,                 -- AT name, e.g. "Sprint AT"
    description             TEXT            NULL,
    acceptance_test_status  VARCHAR(16)     NOT NULL DEFAULT 'pass',  -- pass|fail (default pass)
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

CREATE TABLE IF NOT EXISTS branch_acceptance_tests (
    branch_fk           INT         NOT NULL,
    acceptance_test_fk  INT         NOT NULL,
    sort_order          SMALLINT    NULL,   -- per-branch AT label stacking order
    PRIMARY KEY (branch_fk, acceptance_test_fk),
    CONSTRAINT fk_bat_branch
        FOREIGN KEY (branch_fk) REFERENCES branches (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_bat_acceptance_test
        FOREIGN KEY (acceptance_test_fk) REFERENCES acceptance_tests (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================================================================
-- Agents registry (req #2997, migration 067)
-- Agent .md files are thin charter stubs; their durable knowledge lives here
-- and is read at boot via darwin://agents/<Agent Name>. The DB is canon —
-- scripts/swarm/reconcile-agent-stubs.sh mirrors overview/ai_model/effort into
-- stub frontmatter at session boundaries.
-- ============================================================================

CREATE TABLE IF NOT EXISTS agents (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(128) NOT NULL,                    -- human-readable, e.g. "AWS Architect"; MCP lookup key
    file_name   VARCHAR(128) NOT NULL,                    -- stub basename, e.g. "aws-architect.md"
    overview    TEXT         NULL,                        -- short delegation trigger; mirrored to stub `description`
    ai_model    VARCHAR(32)  NOT NULL DEFAULT 'opus[1m]', -- resolved model id, NOT the haiku|sonnet|opus|fable family enum
    effort      VARCHAR(16)  NOT NULL DEFAULT 'high',     -- low|medium|high|xhigh|ultracode
    location    VARCHAR(512) NULL,                        -- repo-relative stub path
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

CREATE TABLE IF NOT EXISTS instructions (
    id          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(256) NOT NULL,   -- UNIQUE; idempotent-seed key
    content     TEXT         NOT NULL,   -- binding text; one row can bind many agents
    closed      TINYINT(1)   NOT NULL DEFAULT 0,
    sort_order  SMALLINT     NULL,
    creator_fk  VARCHAR(64)  NOT NULL,
    create_ts   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts   TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_instructions_name (name),
    CONSTRAINT fk_instructions_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_instructions (
    agent_fk        INT      NOT NULL,
    instruction_fk  INT      NOT NULL,
    sort_order      SMALLINT NULL,       -- boot load order
    PRIMARY KEY (agent_fk, instruction_fk),
    CONSTRAINT fk_ai_agent
        FOREIGN KEY (agent_fk) REFERENCES agents (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ai_instruction
        FOREIGN KEY (instruction_fk) REFERENCES instructions (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS architecture_documents (
    id          INT           NOT NULL PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(256)  NOT NULL,  -- UNIQUE; idempotent-seed key
    doc_type    VARCHAR(16)   NOT NULL DEFAULT 'markdown',  -- markdown|html|text
    location    VARCHAR(512)  NULL,      -- repo-relative path the agent Reads
    url         VARCHAR(1024) NULL,      -- clickable link (GitHub blob / site path)
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

-- owned_document_fk: a VIRTUAL generated column that equals document_fk only on
-- an 'owned' row, NULL otherwise. The UNIQUE key over it enforces AT MOST ONE
-- 'owned' agent per document (MySQL has no partial index; NULLs are distinct in
-- a UNIQUE key, so non-owned links coexist freely).
CREATE TABLE IF NOT EXISTS agent_documents (
    agent_fk           INT          NOT NULL,
    document_fk        INT          NOT NULL,
    relationship       VARCHAR(24)  NOT NULL DEFAULT 'referenced',  -- owned|groomed|referenced|design_language|guardian
    notes              VARCHAR(512) NULL,
    sort_order         SMALLINT     NULL,
    owned_document_fk  INT          AS (IF(relationship = 'owned', document_fk, NULL)) VIRTUAL,
    PRIMARY KEY (agent_fk, document_fk),
    UNIQUE KEY uq_agent_documents_owner (owned_document_fk),
    CONSTRAINT fk_ad_agent
        FOREIGN KEY (agent_fk) REFERENCES agents (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ad_document
        FOREIGN KEY (document_fk) REFERENCES architecture_documents (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------------
-- Agent Context Telemetry (req #3031, migration 069) — persisted actual-token
-- captures of the agents pattern. Run header + N per-agent rows (parent/child,
-- run is the container -> CASCADE). Token columns are ACTUAL tokens, nullable
-- where a phase is n/a (PrimaryAI has no boot/autoload; Code Reviewer bundles
-- its stub into CC base). Log/infra tables: no title/status/closed/category_fk.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_telemetry_runs (
    id               INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    captured_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    label            VARCHAR(256) NOT NULL,
    agent_count      INT          NOT NULL DEFAULT 0,
    harness_version  VARCHAR(64)  NULL,
    source_note      TEXT         NULL,
    creator_fk       VARCHAR(64)  NOT NULL,
    create_ts        TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts        TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_agent_telemetry_runs_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_agent_telemetry_runs_captured_at ON agent_telemetry_runs (captured_at);

CREATE TABLE IF NOT EXISTS agent_telemetry_rows (
    id                          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    run_fk                      INT          NOT NULL,
    agent_name                  VARCHAR(128) NOT NULL,
    role                        VARCHAR(16)  NOT NULL DEFAULT 'architect',   -- architect|reviewer|primary
    session_kind                VARCHAR(16)  NOT NULL DEFAULT 'subagent',    -- subagent|top_level
    boot_time_ms                INT          NULL,
    cc_base_tokens              INT          NULL,
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
