-- Migration 029: Normalize priority status into a single column
--
-- Replaces 3 independent boolean flags (in_progress, closed, deferred) with a single
-- priority_status VARCHAR(16) column. Valid values: idle, in_progress, deferred, completed.
--
-- Data preservation: CASE mapping handles all 8 possible boolean combinations.
-- Priority order when multiple flags are set (invalid state): closed > deferred > in_progress > idle.
-- Timestamps (started_at, completed_at, deferred_at) are preserved as-is.

-- Part A: Add column and populate (non-destructive — safe to run anytime)

ALTER TABLE priorities
  ADD COLUMN priority_status VARCHAR(16) NOT NULL DEFAULT 'idle' AFTER deferred;

UPDATE priorities SET priority_status = CASE
    WHEN closed = 1 THEN 'completed'
    WHEN deferred = 1 THEN 'deferred'
    WHEN in_progress = 1 THEN 'in_progress'
    ELSE 'idle'
END;

-- Verification query — run manually to confirm data integrity:
--
-- SELECT priority_status,
--        COUNT(*) as count,
--        SUM(closed) as were_closed,
--        SUM(deferred) as were_deferred,
--        SUM(in_progress) as were_in_progress
-- FROM priorities GROUP BY priority_status;
--
-- Expected: completed_count = closed_count,
--           deferred_count = (deferred=1 AND closed=0) count,
--           in_progress_count = (in_progress=1 AND closed=0 AND deferred=0) count,
--           idle_count = (all three = 0) count

-- Part B: Drop old boolean columns (run AFTER all code is deployed and verified)

ALTER TABLE priorities
  DROP COLUMN in_progress,
  DROP COLUMN closed,
  DROP COLUMN deferred;
