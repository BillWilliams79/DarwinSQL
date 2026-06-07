-- 058_add_swarm_completes.sql
--
-- Req #2497: define a swarm-complete data type. Each /swarm-complete (and
-- /primary-ai-swarm-complete) invocation creates one swarm_completes row
-- capturing the closeout metadata + finalize-time summary, then links every
-- swarm_session it closed via the swarm_complete_sessions junction.
--
-- Parallels req #2422's swarm_starts table — same execution-table shape per
-- memory/new-data-type-pattern.md (no closed flag, no sort_order, no title,
-- no category_fk). The closeout side deviates from the launch side in
-- exactly six fields (see CLAUDE.md / memory/swarm-completes.md):
--   skill_name        which closeout skill ran (swarm-start has only one)
--   coordination_type discuss|planned|implemented|deployed (NULL for primary-ai)
--   status            in_progress|ok|error (closeout can fail mid-flight)
--   completed_at      finalize timestamp (launch is instantaneous)
--   complete_summary  mirrors the swarm_sessions.complete_summary column
--   no auto_start     closeout has no A3-style confirmation gate
--
-- swarm_completes          execution table.
-- swarm_complete_sessions  junction table. Composite PK on the two FKs.
--                          CASCADE on both sides. Mirrors swarm_start_sessions.
--
-- Captured at create time (when swarm-complete-record.sh fires):
--   skill_name         swarm-complete | primary-ai-swarm-complete
--   coordination_type  from the worker manifest (planned|implemented|deployed);
--                      NULL for /primary-ai-swarm-complete (primary has no manifest)
--   status             defaults to 'in_progress'; finalize writes 'ok' or 'error'
--   session_count      # swarm_sessions being closed (1 in the typical case)
--
-- Finalize-time columns (NULL at create; populated by the skill's finalize step):
--   tokens_input        skill_total.input from telemetry JSON
--   tokens_cache_write  skill_total.cache_write
--   tokens_cache_read   skill_total.cache_read
--   tokens_output       skill_total.output
--   wall_seconds        skill_total.wall_seconds (native value, no transform)
--   turn_count          skill_total.turn_count
--   complete_summary    markdown summary block emitted by the skill at end-of-run
--   telemetry           full telemetry text (iterm + per-phase TOKEN_TELEMETRY JSON)
--   completed_at        ISO timestamp when finalize wrote (server-side NOW())

CREATE TABLE swarm_completes (
    id                  INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    skill_name          VARCHAR(64)     NOT NULL,
    coordination_type   VARCHAR(16)     NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'in_progress',
    session_count       INT             NOT NULL DEFAULT 0,
    -- Finalize-time token totals (skill_total from telemetry JSON)
    tokens_input        INT             NULL,
    tokens_cache_write  INT             NULL,
    tokens_cache_read   INT             NULL,
    tokens_output       INT             NULL,
    wall_seconds        INT             NULL,
    turn_count          INT             NULL,
    -- Finalize-time summary and full telemetry blob
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
