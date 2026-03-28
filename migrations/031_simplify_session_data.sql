-- Migration 031: Replace 9 session data columns with 2 TEXT summary fields
--
-- Drops the over-engineered columns from 030 and replaces with simple text:
-- start_summary:    free-form text written by swarm-start at session activation
-- complete_summary: free-form text written by swarm-complete at session completion

ALTER TABLE swarm_sessions
    DROP COLUMN summary,
    DROP COLUMN repos_affected,
    DROP COLUMN repos_symlinked,
    DROP COLUMN test_local,
    DROP COLUMN test_production,
    DROP COLUMN deploy_targets,
    DROP COLUMN start_duration_seconds,
    DROP COLUMN complete_duration_seconds,
    DROP COLUMN session_data,
    ADD COLUMN start_summary    TEXT NULL AFTER completed_at,
    ADD COLUMN complete_summary TEXT NULL AFTER start_summary;
