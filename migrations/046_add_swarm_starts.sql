-- 046_add_swarm_starts.sql
--
-- Req #2422: define a swarm-start data type. Each /swarm-start invocation
-- creates one swarm_starts row capturing the launch metadata + finalize-time
-- summary, then links every swarm_session it creates via the
-- swarm_start_sessions junction.
--
-- swarm_starts          - execution table per memory/new-data-type-pattern.md.
--                         No closed flag (instantaneous event), no sort_order
--                         (chronological by started_at), no category_fk (a
--                         single launch can span categories), no title (the
--                         arguments string serves as the label).
-- swarm_start_sessions  - junction table. Composite PK on the two FKs.
--                         CASCADE on both sides. Mirrors requirement_sessions.
--
-- Captured columns:
--   arguments       - raw $ARGUMENTS the user typed; "" stored as NULL.
--   autonomy_filter - planned|implemented|deployed when used (req #2339); NULL otherwise.
--   auto_start      - 1 when A3 confirmation was bypassed (req #2415).
--   session_count   - # swarm_sessions created by this invocation.
--
-- Finalize-time columns (NULL until skill-finalize writes them):
--   tokens_input        - skill_total.input from telemetry JSON
--   tokens_cache_write  - skill_total.cache_write
--   tokens_cache_read   - skill_total.cache_read
--   tokens_output       - skill_total.output
--   wall_seconds        - skill_total.wall_seconds (native value, no transform)
--   turn_count          - skill_total.turn_count
--   start_summary       - markdown summary block emitted by the skill at end-of-run
--   telemetry           - full telemetry text (iterm + per-phase TOKEN_TELEMETRY JSON)

CREATE TABLE swarm_starts (
    id                INT             NOT NULL PRIMARY KEY AUTO_INCREMENT,
    arguments         VARCHAR(512)    NULL,
    autonomy_filter   VARCHAR(16)     NULL,
    auto_start        TINYINT(1)      NOT NULL DEFAULT 0,
    session_count     INT             NOT NULL DEFAULT 0,
    -- Finalize-time token totals (skill_total from telemetry JSON)
    tokens_input        INT           NULL,
    tokens_cache_write  INT           NULL,
    tokens_cache_read   INT           NULL,
    tokens_output       INT           NULL,
    wall_seconds        INT           NULL,
    turn_count          INT           NULL,
    -- Finalize-time summary and full telemetry blob
    start_summary       TEXT          NULL,
    telemetry           TEXT          NULL,
    started_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creator_fk        VARCHAR(64)     NOT NULL,
    create_ts         TIMESTAMP       NULL DEFAULT CURRENT_TIMESTAMP,
    update_ts         TIMESTAMP       NULL ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_swarm_starts_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
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
