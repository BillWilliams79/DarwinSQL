-- 20261022073056_engine_2_data_contract_tables.sql
--
-- Req #3756: the rows Orchestration Engine 2 publishes and the UI reads — the
-- one interface the visualizer, the supervisor and the executor all build on.
--
-- PROBLEM.  Everything the engine knows lives in its own process memory and in
--           /tmp files on the machine it runs on: its decisions, its debounce,
--           its health, whether it should be running at all. Nothing another
--           machine, the UI or a later replay can read (memory/engine-rules.md
--           rules R2, R4, R5, R6, R7, R8, R12).
--
-- SHAPE.    Five tables. Each is written by exactly one party, and that is why
--           there are five and not two:
--
--           engine_states            one row per scope (plan, epic) per machine.
--                                    desired_state on/off is what the UI writes
--                                    (R6); actual_state is what the supervisor
--                                    reports back.
--           engine_heartbeats        one row per engine_state, written ONLY by the
--                                    engine: where it is (R7) and its health (R4).
--                                    `beat_at` is ON UPDATE CURRENT_TIMESTAMP, so
--                                    the STAMP is the database's (a reader's own
--                                    clock still sets the age it computes — the
--                                    bound orchestration_claims lives with). It is a
--                                    separate table because ON UPDATE fires on ANY
--                                    changed column: on a shared row a UI flip of
--                                    desired_state would stamp a fresh heartbeat
--                                    for a dead engine.
--           engine_decision_records  one row per cycle per scope (R2): the record
--                                    JSON plus the columns a list read filters on,
--                                    and the five decide() input hashes (R12).
--           engine_outcomes          one row per admitted item: the executor's
--                                    pending / landed / failed (R5, I6). Its own
--                                    table because a record is content-addressed —
--                                    its id is the hash of its body — so writing
--                                    an outcome INTO the record would change its
--                                    id and break its replay.
--           engine_inputs            decide() inputs stored ONCE by content hash
--                                    (R12): an unchanged plan payload is one row,
--                                    not one per 60-second cycle.
--
--           Retention is the service's (darwin-mcp services/engine2.py
--           `retention_plan`): the last N cycles per scope, every cycle that
--           admitted something within D days, and the prior of each kept record;
--           inputs no kept record names are deleted. N and D are constants in
--           scripts/swarm/engine2/contracts/storage.json.

-- TARGET.   NEVER write `USE <db>;` or `CREATE DATABASE` into this file. A
--           `USE` is a statement, not a declaration: it re-points the session
--           the moment it executes and overrides whatever database the caller
--           named — which on 2026-08-01 sent a dev-aimed apply to production.
--           load_sql.py REFUSES a file that names its own database, and
--           DarwinSQL/tests/test_sql_targets.py fails the build (req #3196).
--           If this migration may only be applied to ONE database, say so as a
--           constraint instead: `-- darwin:targets = darwin`.
--
-- APPLY.    darwin_dev FIRST, production SECOND. Two separate commands:
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261022073056_engine_2_data_contract_tables.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261022073056_engine_2_data_contract_tables.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261022073056` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261022073056 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.




CREATE TABLE engine_states (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    pipeline_fk     INT          NOT NULL,                -- scope: the plan
    epic_fk         INT          NULL DEFAULT NULL,       -- scope: NULL = whole plan
    epic_key        INT          AS (COALESCE(epic_fk, 0)) VIRTUAL, -- carries uq_engine_states_scope
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
    UNIQUE KEY uq_engine_states_scope (pipeline_fk, epic_key, machine_fk),
    CONSTRAINT fk_es_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_es_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_es_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_es_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_engine_states_epic_fk ON engine_states (epic_fk);

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
    epic_fk            INT          NULL DEFAULT NULL,    -- location.scope.epic_id
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
    KEY ix_engine_decision_records_scope (pipeline_fk, epic_fk, machine_fk, id),
    CONSTRAINT fk_edr_pipeline
        FOREIGN KEY (pipeline_fk) REFERENCES pipelines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_edr_epic
        FOREIGN KEY (epic_fk) REFERENCES epics (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_edr_machine
        FOREIGN KEY (machine_fk) REFERENCES machines (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_edr_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX ix_engine_decision_records_epic_fk ON engine_decision_records (epic_fk);
CREATE INDEX ix_engine_decision_records_machine_fk ON engine_decision_records (machine_fk);

CREATE TABLE engine_outcomes (
    id              INT           NOT NULL PRIMARY KEY AUTO_INCREMENT,
    record_fk       INT           NOT NULL,               -- the record that ADMITTED it
    requirement_fk  INT           NOT NULL,
    step_fk         INT           NULL DEFAULT NULL,
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
    CONSTRAINT fk_eo_step
        FOREIGN KEY (step_fk) REFERENCES pipeline_steps (id)
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
