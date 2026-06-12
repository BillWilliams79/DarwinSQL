-- 059_add_session_phase_accumulators.sql
--
-- Req #2332: re-engineer session status values to track development phases and
-- encode transition times.
--
-- Adds per-phase time accumulators to swarm_sessions. On every swarm_status
-- change the MCP/db.py layer computes NOW() - last_transition_at and adds it to
-- the bucket for the phase being LEFT, then resets last_transition_at = NOW().
-- This yields a self-auditing breakdown of where each session's time went,
-- separating agentic (planning/implementing/completion), machine (starting),
-- and human (waiting/review/paused) time.
--
-- Status -> bucket map (enforced in db.py STATUS_BUCKET):
--   starting   -> starting_secs      (machine: setup)
--   waiting    -> waiting_secs       (human: discuss idle)
--   planning   -> planning_secs      (agentic: investigate + author plan)
--   active     -> implementing_secs  (agentic: build the change)
--   review     -> review_secs        (human: manual review)
--   paused     -> paused_secs        (human/idle)
--   completing -> completion_secs    (machine/agentic: close-out)
--   completed  -> (terminal, no bucket)
--
-- Self-audit invariant: SUM(all *_secs) ~= TIMESTAMPDIFF(SECOND, started_at, completed_at).
-- Any residual = a missed transition (detectable, not a silent NULL).
--
-- The two new status VALUES ('waiting', 'planning') need no DDL — swarm_status
-- is VARCHAR(16) validated at the app layer; this migration only adds columns.
--
-- ---------------------------------------------------------------------------
-- Step 1: add accumulator columns (additive, all defaulted — existing INSERTs
--         that omit them keep working; new rows are fully instrumented).
-- ---------------------------------------------------------------------------
ALTER TABLE swarm_sessions
    ADD COLUMN last_transition_at TIMESTAMP    NULL                AFTER completed_at,
    ADD COLUMN starting_secs      INT          NOT NULL DEFAULT 0  AFTER last_transition_at,
    ADD COLUMN waiting_secs       INT          NOT NULL DEFAULT 0  AFTER starting_secs,
    ADD COLUMN planning_secs      INT          NOT NULL DEFAULT 0  AFTER waiting_secs,
    ADD COLUMN implementing_secs  INT          NOT NULL DEFAULT 0  AFTER planning_secs,
    ADD COLUMN review_secs        INT          NOT NULL DEFAULT 0  AFTER implementing_secs,
    ADD COLUMN completion_secs    INT          NOT NULL DEFAULT 0  AFTER review_secs,
    ADD COLUMN paused_secs        INT          NOT NULL DEFAULT 0  AFTER completion_secs,
    ADD COLUMN legacy_secs        INT          NOT NULL DEFAULT 0  AFTER paused_secs,
    ADD COLUMN instrumented       TINYINT      NOT NULL DEFAULT 1  AFTER legacy_secs,
    -- pre_pause_status: the status a session was in when it entered 'paused'.
    -- Set by the engine on entering paused, cleared on leaving paused / on completed.
    -- /swarm-resume reads it to restore the correct phase instead of always 'active'.
    ADD COLUMN pre_pause_status   VARCHAR(16)  NULL                AFTER instrumented;

-- ---------------------------------------------------------------------------
-- Step 2: backfill existing rows. We never recorded intermediate transitions
--         for pre-migration sessions, so we DO NOT fabricate a phase split —
--         the entire known total goes into legacy_secs and the row is flagged
--         instrumented=0. Downstream stats/visualizer filter on instrumented=1
--         and render legacy_secs as a single neutral "unclassified" segment.
--
--   completed rows  -> legacy lump = started_at..completed_at; last_transition_at NULL (terminal)
--   in-flight rows  -> legacy lump = started_at..NOW(); last_transition_at = NOW() (accrue forward)
-- ---------------------------------------------------------------------------
UPDATE swarm_sessions
SET instrumented = 0,
    -- COALESCE(..., 0) on the OUTSIDE guards the theoretical case where both
    -- started_at and create_ts are NULL (GREATEST(0, NULL) -> NULL would violate
    -- the NOT NULL column under strict mode). create_ts defaults to CURRENT_TIMESTAMP
    -- so this cannot happen in practice, but the column is NOT NULL — stay safe.
    legacy_secs = COALESCE(GREATEST(0, TIMESTAMPDIFF(
        SECOND,
        COALESCE(started_at, create_ts),
        COALESCE(completed_at, NOW())
    )), 0),
    last_transition_at = CASE WHEN completed_at IS NULL THEN NOW() ELSE NULL END;
