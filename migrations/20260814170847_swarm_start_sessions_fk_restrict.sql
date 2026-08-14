-- 20260814170847_swarm_start_sessions_fk_restrict.sql
--
-- Req #3382: swarm_start_sessions has no DB-level delete guard against a
-- swarm_starts row being deleted out from under it.
--
-- PROBLEM.  `swarm_start_sessions.swarm_start_fk` is ON DELETE CASCADE.
--           delete_swarm_start (darwin-mcp) refuses to delete a swarm_start
--           with linked sessions, and the Swarm UI's delete dialog mirrors
--           that guard client-side — but the browser's DELETE goes straight
--           through Lambda-Rest's generic `rest_delete.py`, which has no
--           linked-session check at all. A crafted request (or any other
--           client of Lambda-Rest) can delete a swarm_start with linked
--           sessions and silently cascade away the swarm_start_sessions
--           junction rows, with nothing recording what was lost. The MCP
--           tool's own check-then-delete is also non-atomic (TOCTOU): the
--           module-level lock is in-process only, so a race between the
--           junction check and the DELETE can slip through today.
--
-- SHAPE.    Flip `fk_sss_swarm_start` from ON DELETE CASCADE to ON DELETE
--           RESTRICT. This is the same pattern already used for other
--           parent/child pairs where the child is real history that must
--           not disappear silently (e.g. `fk_test_runs_plan`). It closes
--           the TOCTOU gap for free: a raced delete now fails loudly with a
--           1451 (translated to a friendly ValueError by
--           darwin-mcp/services/swarm_starts.py) instead of silently
--           succeeding. `fk_sss_session` (the other half of the composite
--           PK) is left as CASCADE — deleting a swarm_session legitimately
--           takes its swarm_start links with it; only the swarm_starts side
--           needed a backstop. darwin-mcp/tests/conftest.py's CLEANUP_ORDER
--           relied on the CASCADE to clean up swarm_start_sessions when
--           swarm_starts is deleted in test teardown; that is fixed
--           alongside this migration (a `_clear_swarm_start_sessions` sweep
--           now runs before the swarm_starts delete, scoped through
--           swarm_starts.creator_fk), so the swap has no test-infra
--           fallout.
--
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
--               DarwinSQL/migrations/20260814170847_swarm_start_sessions_fk_restrict.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20260814170847_swarm_start_sessions_fk_restrict.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20260814170847` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20260814170847 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

ALTER TABLE swarm_start_sessions
    DROP FOREIGN KEY fk_sss_swarm_start;

ALTER TABLE swarm_start_sessions
    ADD CONSTRAINT fk_sss_swarm_start
        FOREIGN KEY (swarm_start_fk) REFERENCES swarm_starts (id)
        ON UPDATE CASCADE ON DELETE RESTRICT;

