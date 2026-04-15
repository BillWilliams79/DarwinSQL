-- Drop the requirements.scheduled column.
--
-- The `scheduled` column (TINYINT 0/1/2) is superseded by two newer fields:
--   - requirement_status = 'swarm_ready'  → signals "queued for swarm-start pickup"
--   - coordination_type (planned/implemented/deployed/NULL) → determines worker autonomy
--
-- Historical mapping was applied in migration 039:
--   - scheduled=1/2 rows with status='idle' were promoted to
--     requirement_status='swarm_ready' + coordination_type='planned'
--
-- After this migration:
--   - /swarm-start discovers by requirement_status='swarm_ready'
--   - Manual vs autonomous start is determined by coordination_type IS NULL / NOT NULL
--   - No second field is needed and the --clear-scheduled flag in session-init.sh is removed

ALTER TABLE requirements DROP COLUMN scheduled;
