-- 056_coordination_type_not_null.sql
--
-- Req #2745: autonomy (coordination_type) is now MANDATORY on requirements.
-- The new 'discuss' coordination type replaces the old "no setting" (NULL)
-- behavior with an explicit, intentional waiting state, so an empty autonomy
-- is no longer a meaningful state — every requirement must carry one of
-- discuss | planned | implemented | deployed.
--
-- This migration enforces that at the database level so neither the UI, the
-- MCP layer, nor raw SQL can reintroduce a NULL.
--
-- Step 1 backfills any remaining NULLs to 'discuss' (the value chosen for
-- previously-unset requirements during the req #2745 backfill — anything left
-- unset was intentionally left for discussion). In production the backfill was
-- already applied via MCP; this UPDATE is a no-op there and a safety net for
-- darwin_dev / any clone with stragglers.
--
-- Step 2 makes the column NOT NULL while preserving the existing
-- DEFAULT 'implemented' so omitted-column INSERTs continue to get a valid value.
--
-- Affects the `requirements` table only. swarm_undos.coordination_type and
-- swarm_completes.coordination_type remain NULLABLE — they are snapshot/log
-- columns that legitimately record the absence of a prior coordination value.

-- Step 1: backfill stragglers
UPDATE requirements SET coordination_type = 'discuss' WHERE coordination_type IS NULL;

-- Step 2: enforce NOT NULL (default unchanged)
ALTER TABLE requirements
    MODIFY coordination_type VARCHAR(16) NOT NULL DEFAULT 'implemented';
