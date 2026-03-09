-- Migration 016: Create roadmap tables + fix untracked domain sort_order
-- These tables support the Darwin priority/project tracking system (darwin-mcp).
-- Previously created directly on production without tracked migrations.
-- Also adds sort_order to domains (was added ad-hoc, never tracked in migrations).
-- CREATE TABLE IF NOT EXISTS for idempotency (tables already exist in production).
-- Order: FK dependencies (projects first, then categories, swarm_sessions, priorities, priority_sessions).

-- Add sort_order to domains (idempotent via INFORMATION_SCHEMA check)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'domains' AND COLUMN_NAME = 'sort_order');

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE domains ADD COLUMN sort_order SMALLINT NULL',
    'SELECT 1');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS projects (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    project_name    VARCHAR(128)    NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    sort_order      SMALLINT        NULL,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk) REFERENCES profiles (id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS categories (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    category_name   VARCHAR(128)    NOT NULL,
    project_fk      INT             NOT NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    sort_order      SMALLINT        NULL,
    sort_mode       VARCHAR(8)      NOT NULL DEFAULT 'priority',
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_fk) REFERENCES projects (id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (creator_fk) REFERENCES profiles (id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS swarm_sessions (
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
    creator_fk      VARCHAR(64)     NOT NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_fk) REFERENCES profiles (id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS priorities (
    id              INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(256)    NOT NULL,
    description     TEXT            NULL,
    in_progress     TINYINT(1)      NOT NULL DEFAULT 0,
    closed          TINYINT(1)      NOT NULL DEFAULT 0,
    started_at      TIMESTAMP       NULL,
    completed_at    TIMESTAMP       NULL,
    project_fk      INT             NULL,
    category_fk     INT             NULL,
    creator_fk      VARCHAR(64)     NOT NULL,
    sort_order      SMALLINT        NULL,
    create_ts       TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts       TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    scheduled       TINYINT         NOT NULL DEFAULT 0,
    FOREIGN KEY (project_fk) REFERENCES projects (id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (category_fk) REFERENCES categories (id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (creator_fk) REFERENCES profiles (id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS priority_sessions (
    priority_fk     INT             NOT NULL,
    session_fk      INT             NOT NULL,
    PRIMARY KEY (priority_fk, session_fk),
    FOREIGN KEY (priority_fk) REFERENCES priorities (id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (session_fk) REFERENCES swarm_sessions (id) ON UPDATE CASCADE ON DELETE CASCADE
);
