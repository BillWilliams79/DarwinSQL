-- Migration 030: Add summary and session data columns to swarm_sessions
--
-- summary:                  human-readable completion narrative (written by swarm-complete)
-- repos_affected:           JSON array of affected repo objects (written by swarm-start)
-- repos_symlinked:          JSON array of symlinked repo names (written by swarm-start)
-- test_local:               local test results "X/Y" (written by swarm-complete)
-- test_production:          production test results "X/Y" (written by swarm-complete)
-- deploy_targets:           comma-separated deploy targets (written by swarm-complete)
-- start_duration_seconds:   wall clock of swarm-start skill execution (written by swarm-start)
-- complete_duration_seconds: wall clock of swarm-complete skill execution (written by swarm-complete)
-- session_data:             flexible JSON for ad-hoc telemetry/debugging (written by either skill)

ALTER TABLE swarm_sessions
    ADD COLUMN summary                  TEXT            NULL AFTER completed_at,
    ADD COLUMN repos_affected           JSON            NULL AFTER summary,
    ADD COLUMN repos_symlinked          JSON            NULL AFTER repos_affected,
    ADD COLUMN test_local               VARCHAR(32)     NULL AFTER repos_symlinked,
    ADD COLUMN test_production          VARCHAR(32)     NULL AFTER test_local,
    ADD COLUMN deploy_targets           VARCHAR(256)    NULL AFTER test_production,
    ADD COLUMN start_duration_seconds   INT             NULL AFTER deploy_targets,
    ADD COLUMN complete_duration_seconds INT            NULL AFTER start_duration_seconds,
    ADD COLUMN session_data             JSON            NULL AFTER complete_duration_seconds;
