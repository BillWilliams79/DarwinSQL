-- 053_add_swarm_undos.sql
--
-- Req #2719: define a swarm-undo data type so every /swarm-undo invocation
-- emits a durable record of what was undone and why. Parallels swarm_starts
-- (migration 046) — one row per /swarm-undo invocation, capturing a free-form
-- reason from the user plus enough snapshot metadata to survive the cascade
-- delete of the underlying swarm_sessions row.
--
-- session_fk is NULLABLE and ON DELETE SET NULL because /swarm-undo deletes the
-- session row immediately after recording the undo. The snapshot columns
-- (req_id_at_undo, task_name, branch, coordination_type, swarm_start_fk_at_undo)
-- preserve the linkage history once the session row is gone.
--
-- Captured columns:
--   session_fk             - live FK while the session exists; NULL after delete.
--   swarm_start_fk_at_undo - snapshot of the swarm_start that launched this
--                            session; enables visualizer matching (circle ->
--                            tombstone) even after session_fk goes to NULL.
--   req_id_at_undo         - snapshot of the requirement the session worked on.
--   task_name              - snapshot kebab-case session label.
--   branch                 - snapshot feature/<reqId>-<taskName> branch.
--   coordination_type      - snapshot of planned|implemented|deployed.
--   reason                 - mandatory free-text "why" supplied by the user
--                            at undo time. Future hardening may convert this
--                            to an enum/choice; today the column is the
--                            authoritative record.

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
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_swarm_undos_swarm_start_fk_at_undo
    ON swarm_undos (swarm_start_fk_at_undo);

CREATE INDEX ix_swarm_undos_undone_at
    ON swarm_undos (undone_at);
