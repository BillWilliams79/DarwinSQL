-- Darwin Database Schema — Current State
-- This file reflects the final state of all 53 tables after all migrations.
-- It can be run against a fresh MySQL instance to create the complete schema.
-- Table order respects FK dependencies.
--
-- THE TARGET DATABASE IS THE CALLER'S (req #3196). This file used to open with
-- `CREATE DATABASE IF NOT EXISTS darwin; USE darwin;`, which re-pointed the
-- session to PRODUCTION no matter which database the caller had connected to —
-- the file outranked the operator, silently, and on 2026-08-01 it wrote three
-- rows to production from a probe aimed at a scratch database. Name the target
-- on the connection instead:
--
--     python3 DarwinSQL/scripts/load_sql.py DarwinSQL/schema.sql <database>
--
-- Creating the database is likewise the caller's: `seed_darwin_dev.py` does it
-- for darwin_dev, and production already exists. A file that cannot be aimed
-- cannot be aimed at the wrong thing.

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
    max_live_sessions SMALLINT NOT NULL DEFAULT 20, -- swarm concurrency ceiling (req #3390);
                                                    -- 0 is meaningful (drain); DEFAULT applies
                                                    -- only to future auto-registered machines
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

-- ============================================================================
-- Agile hierarchy: Epic > Feature > Story(requirement)  (req #3111, migration 076)
-- ============================================================================
-- `epics` and `features` are defined HERE, above `requirements`, so that
-- requirements.feature_fk resolves on a fresh end-to-end run of this file — the
-- same reason `machines` sits above the execution tables. The rest of the
-- validation family (test_cases, test_plans, test_runs, test_results and their
-- junctions) stays in the "Swarm Features & Test Cases registry" section below.
--
-- Labels attach at the REQUIREMENT level, never at a pipeline step (req #3080
-- design rule 10): a launch unit may legitimately span epics, and a step derives
-- its dominant label at render time instead of storing a wrong one.

CREATE TABLE IF NOT EXISTS epics (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(256) NOT NULL,
    description  TEXT         NULL,
    epic_status  VARCHAR(16)  NOT NULL DEFAULT 'active',  -- active|paused (req #3223,
                                            -- migration 20260801125029). SUPPRESSION, not
                                            -- lifecycle: `closed` still says an epic is
                                            -- finished, this says whether its work may be
                                            -- swarm-started. `paused` stops the Pipeline
                                            -- Engine announcing launches for the epic's
                                            -- steps under ANY orchestrator — an epic-scoped
                                            -- one and a whole-plan one alike — and nothing
                                            -- else: orchestration, running sessions and a
                                            -- directly user-initiated /swarm-start are all
                                            -- unaffected. Read for free by
                                            -- darwin://pipeline/{id}.
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

CREATE TABLE IF NOT EXISTS features (
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
    feature_fk      INT             NULL DEFAULT NULL,
                                            -- parent feature (req #3111, migration 076); NULL = unfiled.
                                            -- The story tier of Epic > Feature > Story; SET NULL so deleting a
                                            -- feature demotes its requirements instead of destroying history.
    tracking        TINYINT(1)      NOT NULL DEFAULT 0,
                                            -- CONTAINER, not work (req #3123, migration 20260731124830).
                                            -- 1 = this requirement HOLDS a plan (or an epic/feature) rather than
                                            -- being work performed inside it, so it stays `development` for that
                                            -- plan's whole life. A pipeline step EXCLUDES tracking requirements
                                            -- from its gating set (design rule 1) and from its /swarm-start
                                            -- argument list (rule 8); a step whose links are ALL tracking derives
                                            -- from its own completed_at, exactly as a link-less step does.
                                            -- Orthogonal to requirement_status — a container has a lifecycle too
                                            -- — which is why this is a flag and not a status value.
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

-- ============================================================================
-- Swarm session management
-- ============================================================================

-- FK checks are disabled across this one CREATE because `swarm_sessions`
-- forward-references `pipelines`, which the Swarm Orchestration block declares
-- much further down (req #3186). Same pattern, and same reason, as the
-- build-visualizer block below: the constraint must stay INLINE — the
-- conformance tests that derive `CREATOR_TABLE_REFERENCES` and the junction
-- registry from this file parse CREATE TABLE bodies and never see a trailing
-- ALTER — so a fresh `mysql < schema.sql` needs the check relaxed instead.
SET FOREIGN_KEY_CHECKS = 0;

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
    -- Orchestration attribution (req #3186, migration 20260801020944). WHICH
    -- PIPELINE / WHICH EPIC this session was advancing — stamped ONCE by
    -- darwin-mcp's link_requirement_session and never overwritten, because the
    -- links a derivation would walk (requirements.feature_fk, features.epic_fk,
    -- pipeline_step_requirements) are all mutable and would rewrite a finished
    -- session's history. NULL = no plan/epic context, or pre-#3186 and not
    -- derivable at backfill time. ON DELETE SET NULL: session history must never
    -- block deleting a pipeline or an epic.
    pipeline_fk     INT             NULL DEFAULT NULL,
    epic_fk         INT             NULL DEFAULT NULL,
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
    -- Cost ROLLUP (req #3117, migration 077). Flat sums of the two blocks above,
    -- stamped server-side by darwin-mcp on every genuine swarm_status change.
    -- They exist because list reads DROP phase_tokens (req #3078) — a rollup the
    -- render path cannot read is no rollup at all (req #3080 design rule 5).
    -- NULL = not yet computed (pre-backfill); 0 = computed and genuinely zero.
    wall_secs_total INT             NULL,   -- sum of the 8 *_secs buckets
    output_tokens_total INT         NULL,   -- sum of phase_tokens[*].output
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
    -- req #3166: composite, and it REPLACES the old single-column
    -- idx_map_coordinates_run. `map_run_fk` is the leftmost prefix, so this
    -- still satisfies the foreign key, and `seq` removes the filesort from the
    -- one read shape the whole product uses:
    --   WHERE map_run_fk = ? ORDER BY seq ASC
    INDEX idx_map_coordinates_run_seq (map_run_fk, seq)
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
-- NOTE: `features` itself is defined ABOVE, in the "Agile hierarchy" section
-- next to `epics` — requirements.feature_fk (req #3111, migration 076) forced it
-- above `requirements` so a fresh end-to-end run of this file resolves. Only the
-- rest of the validation family lives here.

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
-- and is read at boot via darwin://agents/<Agent Name>. The DB is canon;
-- ai_model/effort are also kept in the stub frontmatter by hand (no reconciler).
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
    name        VARCHAR(256) NOT NULL,   -- UNIQUE; an English title (req #3068)
    content     TEXT         NOT NULL,   -- binding text; one row can bind many agents
    closed      TINYINT(1)   NOT NULL DEFAULT 0,
    -- NO sort_order (migration 072). Browse order is chosen in the UI; the only
    -- ordering that means anything is `agent_instructions.sort_order` below, the
    -- per-(agent, instruction) BOOT LOAD ORDER.
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
    -- req #3075, migration 073: one agent may not load two instructions at the
    -- same NUMBERED slot. NULL claims no slot, and MySQL UNIQUE permits many
    -- NULLs — that is the intended scope, not a gap. Deliberately NOT mirrored
    -- on `agent_documents`, which sorts by relationship rank first and so has
    -- legitimate same-slot pairs across rank groups.
    UNIQUE KEY uq_agent_instructions_slot (agent_fk, sort_order),
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

-- relationship (req #3012): a SET of INDEPENDENT roles — a link may carry several
-- at once (e.g. 'owned,autoload'). `autoload` is a STORED role, not derived.
-- owned_document_fk: a VIRTUAL generated column that equals document_fk only when
-- the relationship SET contains 'owned', NULL otherwise. The UNIQUE key over it
-- enforces AT MOST ONE 'owned' agent per document (MySQL has no partial index;
-- NULLs are distinct in a UNIQUE key, so non-owned links coexist freely).
CREATE TABLE IF NOT EXISTS agent_documents (
    agent_fk           INT          NOT NULL,
    document_fk        INT          NOT NULL,
    relationship       SET('principles','owned','curated','autoload','referenced') NOT NULL DEFAULT 'referenced',
    notes              VARCHAR(512) NULL,
    sort_order         SMALLINT     NULL,
    owned_document_fk  INT          AS (IF(FIND_IN_SET('owned', relationship) > 0, document_fk, NULL)) VIRTUAL,
    -- req #3129: the MIRROR IMAGE of the owner rule -- one 'owned' link per
    -- DOCUMENT, one 'principles' link per AGENT. Note the key column differs:
    -- document_fk above, agent_fk here. Swapping them inverts both rules.
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
    ai_model         VARCHAR(16)  NOT NULL DEFAULT 'opus',
                                            -- req #3098, migration 075; fixed default for both backfill and future rows (capture-log row, not an editable setting)
    effort           VARCHAR(16)  NOT NULL DEFAULT 'high',
                                            -- req #3098, migration 075; see ai_model comment
    machine_fk       INT          NULL,
                                            -- req #3098, migration 075; which machine ran the capture (NULL = unknown)
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

CREATE TABLE IF NOT EXISTS agent_telemetry_rows (
    id                          INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    run_fk                      INT          NOT NULL,
    agent_name                  VARCHAR(128) NOT NULL,
    role                        VARCHAR(16)  NOT NULL DEFAULT 'architect',   -- architect|reviewer|primary
    session_kind                VARCHAR(16)  NOT NULL DEFAULT 'subagent',    -- subagent|top_level
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

-- Req #3096, migration 074 — per-document actual-token breakdown, one level deeper
-- than agent_telemetry_rows -> agent_telemetry_runs. row_fk CASCADEs (the row is
-- the container for its own documents); no redundant run_fk (single immediate-
-- parent FK, matching the builds -> branches precedent) and no FK to
-- architecture_documents (doc_path is plain text, matching agent_name on the
-- parent row — a historical snapshot table, not a live reference).
CREATE TABLE IF NOT EXISTS agent_telemetry_row_docs (
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
-- A pipeline is a durable multi-requirement execution plan: data in MySQL,
-- rendered live, interpreted by a judgment-capable Primary Claude. Req #3080
-- rejected a coded DAG because the 2026-07-25 Substrate Rebuild plan mutated ~12
-- times under contact with reality; what survives mutation is the artifact.
--
-- What is ABSENT from pipeline_steps is as much of the design as what is present:
--   * no state/status column — a step's state is DERIVED from its linked
--     requirements (design rule 1). The POC's step 13 launched five sessions
--     while the plan still read "Scheduled"; a column that can disagree with
--     reality is the bug, so the column does not exist.
--   * no seq/sort_order — display order is computed at render: topological, then
--     state bands (Complete > Running > Scheduled), then streams (design rule 3).
--   * no epic/feature — labels attach at the requirement (design rule 10).
--   * no gate_expr prose — dependencies are rows (design rule 4).
--
-- Defined at the end of the file: pipelines -> machines, pipeline_step_deps ->
-- pipeline_steps, pipeline_step_requirements -> requirements, all above.

CREATE TABLE IF NOT EXISTS pipelines (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256) NOT NULL,
    description     TEXT         NULL,                     -- the goal
    pipeline_status VARCHAR(16)  NOT NULL DEFAULT 'draft', -- draft|active|paused|completed|aborted
    execution_mode  ENUM('parallel', 'serial')
                              NOT NULL DEFAULT 'parallel', -- req #3388: parallel = every epic at
                                                           -- once; serial = one at a time, live
                                                           -- epic DERIVED
    machine_fk      INT          NULL DEFAULT NULL,        -- NULL = any machine
    creator_fk      VARCHAR(64)  NOT NULL,
    started_at      TIMESTAMP    NULL,                     -- set on draft -> active (NULL-able: a
                                                           -- pipeline is born `draft`, not running)
    completed_at    TIMESTAMP    NULL,                     -- set on -> completed|aborted
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP    NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pipelines_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pipelines_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id           INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,  -- STABLE: never renumbered/reused
    pipeline_fk  INT          NOT NULL,
    title        VARCHAR(256) NOT NULL,                             -- the step summary
    run          VARCHAR(8)   NOT NULL DEFAULT 'auto',              -- auto|manual
    notes        TEXT         NULL,                                 -- evidence / findings / dispositions
    completed_at TIMESTAMP    NULL,                                 -- manual stamp ONLY for zero-requirement
                                                                    -- steps; requirement-backed steps derive
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

-- Asymmetric on purpose: step_fk CASCADE (the links are the step's own data),
-- requirement_fk RESTRICT (a requirement that appears in a plan cannot be
-- deleted). This deviates from the junction default of CASCADE on both sides.
CREATE TABLE IF NOT EXISTS pipeline_step_requirements (
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

-- One row = one condition on one step. Convention (application-enforced):
-- exactly one of dep_step_fk / time_at per row. A dual-condition gate is simply
-- two rows on one step. dep_step_fk is RESTRICT — design rule 4's teeth: a step
-- something else gates on cannot be deleted or merged away.
CREATE TABLE IF NOT EXISTS pipeline_step_deps (
    id          INT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    step_fk     INT       NOT NULL,
    dep_step_fk INT       NULL,          -- gate on another step
    time_at     TIMESTAMP NULL,          -- gate on wall clock (plan's T:<ISO8601>)
    UNIQUE KEY uq_pipeline_step_deps (step_fk, dep_step_fk),
    CONSTRAINT fk_psd_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_psd_dep_step
        FOREIGN KEY (dep_step_fk) REFERENCES pipeline_steps (id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX ix_psd_dep_step_fk ON pipeline_step_deps (dep_step_fk);

-- ---------------------------------------------------------------------------
-- Orchestration reservations (req #3224, migration 20260801150404)
-- ---------------------------------------------------------------------------
-- ONE row per RESERVED SCOPE. The single-orchestrator guarantee, made durable
-- and shared so it crosses a machine boundary — the machine-local registry
-- under /tmp cannot, and `kill(pid, 0)` is only answerable on the machine that
-- owns the pid. The CONFLICT RULE is unchanged: a whole-plan scope owns every
-- step in its plan and conflicts with any scope on it; two epic scopes conflict
-- only when they are the same epic (design rule 10 makes step -> orchestrator a
-- function).
--
-- `pipeline_fk` + `epic_fk` ARE the scope; there is no `scope` string, because
-- `pipeline:2` / `epic:7@2` is a RENDERING of those ids (design rule 1).
-- `epic_key` carries the UNIQUE key because MySQL treats NULLs in a UNIQUE index
-- as DISTINCT — over `epic_fk` directly, two whole-plan claims would both
-- insert, which is the collision the constraint exists to stop. Same device as
-- agent_documents.owned_document_fk.
--
-- LIVENESS IS HEARTBEAT AGE ON A DB-STAMPED CLOCK (`update_ts`, falling back to
-- `claimed_at` before the first heartbeat), never `engine_pid` — that column is
-- there so a HUMAN can find the process, and reading a remote pid as liveness is
-- the mistake this table corrects. `polls` is the heartbeat's payload because
-- ON UPDATE CURRENT_TIMESTAMP only fires when a value actually CHANGES.
-- Staleness (600 s = ten default engine cycles) is enforced in
-- darwin-mcp/services/orchestration_claims.py; a schema cannot express it.
--
-- DISTINCT FROM PAUSE (req #3223) and deliberately not merged with it: a
-- reservation is a live claim reclaimed on staleness, a pause is a user
-- intention that must never be.
CREATE TABLE IF NOT EXISTS orchestration_claims (
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
