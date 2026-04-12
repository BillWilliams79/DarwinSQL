-- Overhaul requirement_status values and add coordination_type column.
--
-- requirement_status changes:
--   idle        → authoring    (new default — requirement being authored)
--   idle+sched  → swarm_ready  (was scheduled — now status captures this)
--   in_progress → development  (active swarm work in progress)
--   completed   → met          (requirement fulfilled)
--   deferred    → deferred     (retained unchanged)
--   NEW: approved              (description complete, ready to schedule)
--   NEW: swarm_ready           (scheduled for swarm-start pickup)
--
-- New column: coordination_type VARCHAR(16) NULL DEFAULT NULL
--   Values: 'planned' | 'implemented' | 'deployed'
--   Controls how much autonomy a swarm worker receives.
--
-- scheduled → coordination_type mapping (historical data preservation):
--   scheduled=1 (manual)     → coordination_type='planned'
--   scheduled=2 (auto-start) → coordination_type='planned'
-- Both map to 'planned' because pre-overhaul, 'auto-start' was still just
-- kicking off the planning phase. Features going forward use the richer
-- coordination values (planned/implemented/deployed).
--
-- swarm_sessions.swarm_status: adds 'review' as a valid value.
--   swarm_status is VARCHAR(16) — no DDL needed; validated in application code.

-- Step 1: Add coordination_type column (default 'implemented' for new requirements)
ALTER TABLE requirements ADD COLUMN coordination_type VARCHAR(16) NULL DEFAULT 'implemented' AFTER scheduled;

-- Step 2: Map scheduled rows BEFORE status remap (while they still have 'idle' status)
-- scheduled=1 and scheduled=2 both map to swarm_ready + planned (historical preservation)
UPDATE requirements SET requirement_status = 'swarm_ready', coordination_type = 'planned'
    WHERE requirement_status = 'idle' AND scheduled >= 1;

-- Step 3: Remap remaining status values (idle with scheduled=0, plus in_progress and completed)
UPDATE requirements SET requirement_status = 'authoring'   WHERE requirement_status = 'idle';
UPDATE requirements SET requirement_status = 'development' WHERE requirement_status = 'in_progress';
UPDATE requirements SET requirement_status = 'met'         WHERE requirement_status = 'completed';
-- 'deferred' stays as-is
-- Orphaned 'open' rows (from stale E2E test fixtures — project-p1.spec.ts used 'open'
-- which was never a valid status value). Remap to 'authoring' to bring them into the
-- valid set; the E2E cleanup sweep will drop them next run.
UPDATE requirements SET requirement_status = 'authoring'   WHERE requirement_status = 'open';

-- Step 4: Change column default from 'idle' to 'authoring'
ALTER TABLE requirements ALTER COLUMN requirement_status SET DEFAULT 'authoring';
