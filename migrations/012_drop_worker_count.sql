-- Migration 012: Drop worker_count from swarm_sessions
-- The worker_count column was set once at session creation but never used for logic.
ALTER TABLE swarm_sessions DROP COLUMN worker_count;
