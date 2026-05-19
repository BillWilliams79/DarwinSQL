-- 048_add_agents.sql
--
-- Req #2496 Agents 2.0 — Phase 1: add the `agents` table.
--
-- The .md file in `.claude/agents/<name>.md` (within each git worktree) is the
-- single source of truth. This table stores metadata + a cached body so the
-- Darwin UI can browse, search, and edit agents without filesystem access.
--
-- Worktree-aware discovery: the sync script reads agent files from the CWD's
-- .claude/agents/ directory and upserts here, so the same DB row tracks the
-- same agent across worktrees (uniqueness is per (creator_fk, name)).
--
-- `darwin_id` is a durable identifier embedded in the agent .md file's YAML
-- frontmatter (e.g. `darwin_id: 3005`). It survives renames and lets us link
-- the row back to the file unambiguously even if a swarm worker renames the
-- agent or moves the file.
--
-- `frontmatter_json` round-trips the parsed YAML frontmatter so the sync
-- script can reconstruct the file body without losing keys we don't model
-- as columns yet.
--
-- FK policy:
--   creator_fk  → profiles(id)    ON DELETE CASCADE
-- No category_fk — agents are a SYSTEM concept (like dev_servers), not a
-- Swarm-categorized one. They're shared infrastructure across the whole UI.

CREATE TABLE agents (
    id                SMALLINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
    darwin_id         INT             NOT NULL,
    name              VARCHAR(64)     NOT NULL,
    description       VARCHAR(2048)   NULL,
    model             VARCHAR(64)     NULL,
    tools_csv         VARCHAR(512)    NULL,
    file_path         VARCHAR(512)    NOT NULL,
    body_markdown     MEDIUMTEXT      NULL,
    frontmatter_json  JSON            NULL,
    creator_fk        VARCHAR(64)     NOT NULL,
    closed            TINYINT(1)      NOT NULL DEFAULT 0,
    sort_order        SMALLINT        NULL,
    create_ts         TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts         TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_agents_creator_darwin_id (creator_fk, darwin_id),
    UNIQUE KEY uk_agents_creator_name      (creator_fk, name),
    KEY ix_agents_creator_closed (creator_fk, closed),
    CONSTRAINT fk_agents_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
