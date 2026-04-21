-- Recreate darwin_dev test/dev tables from scratch
-- Uses production-identical table names (same DDL as schema.sql)
-- Idempotent: safe to run repeatedly to reset darwin_dev to canonical state
-- All 25 tables in FK-dependency order

USE darwin_dev;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS test_results, test_runs, test_plan_cases, test_plans,
    feature_test_cases, test_cases, features,
    map_run_partners, map_partners,
    map_views, map_coordinates, map_runs, map_routes,
    priority_card_order, dev_servers, requirement_sessions,
    requirements, swarm_sessions, categories, projects,
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

CREATE TABLE requirements (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    in_progress     TINYINT(1)      NOT NULL DEFAULT 0,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    started_at      TIMESTAMP       NULL,
    completed_at    TIMESTAMP       NULL,
    project_fk      INT             NULL,
    category_fk     INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_fk)
        REFERENCES projects (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_requirements_category
        FOREIGN KEY (category_fk)
        REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Swarm session management

CREATE TABLE swarm_sessions (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    branch          VARCHAR(128)    NULL,
    task_name       VARCHAR(128)    NULL,
    source_type     VARCHAR(16)     NULL,
    source_ref      VARCHAR(64)     NULL,
    title           VARCHAR(256)    NULL,
    pr_url          VARCHAR(512)    NULL,
    swarm_status    VARCHAR(16)     NOT NULL DEFAULT 'starting',
    worktree_path   VARCHAR(512)    NULL,
    started_at      TIMESTAMP       NULL,
    completed_at    TIMESTAMP       NULL,
    start_summary   TEXT            NULL,
    complete_summary TEXT           NULL,
    telemetry       TEXT            NULL,
    plan            TEXT            NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

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

-- Dev server port coordination

CREATE TABLE dev_servers (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    port            SMALLINT        NOT NULL,
    pid             INT             NOT NULL,
    workspace_path  VARCHAR(512)    NOT NULL,
    session_fk      INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    started_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_port (port),
    FOREIGN KEY (creator_fk)
        REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (session_fk)
        REFERENCES swarm_sessions (id)
        ON UPDATE CASCADE ON DELETE SET NULL
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
    INDEX idx_map_coordinates_run (map_run_fk)
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

-- Swarm Features & Test Cases registry (req #2380)

CREATE TABLE features (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NOT NULL,
    feature_status  VARCHAR(16)     NOT NULL DEFAULT 'draft',
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
