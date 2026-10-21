-- 20261021060108_step_requirement_seat_cascades_on_requirement_delete.sql
--
-- Req #3706: a requirement seated on a pipeline step cannot be deleted.
--
-- PROBLEM.  `pipeline_step_requirements.fk_psr_requirement` is ON DELETE
--           RESTRICT, so `DELETE FROM requirements` fails with 1451 for any
--           requirement seated on a step — the gateway answers 409 and every
--           delete surface (the requirements card, the swarm-start card, the
--           requirement detail page, darwin-mcp `delete_requirement`) reports
--           "Unable to delete requirement". The user's ruling: deleting the
--           requirement is the intent, the seat goes with it.
--
-- SHAPE.    The requirement side now CASCADEs, like the step side always has.
--           Deleting a requirement removes its seat exactly as
--           `unlink_step_requirement` would; the step itself survives (a step
--           left with no gating requirement derives from its own
--           `completed_at`, the same as after an unlink). A LOCKED plan is
--           still protected — the gateway refuses (423) deleting a requirement
--           seated on an effectively locked step before the statement runs
--           (Lambda-Rest `plan_lock.py`), because the cascade would otherwise
--           rewrite a relic. Two statements rather than one ALTER: the
--           constraint keeps its name, and MySQL refuses to drop and re-add
--           one name inside a single ALTER TABLE.
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
--               DarwinSQL/migrations/20261021060108_step_requirement_seat_cascades_on_requirement_delete.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261021060108_step_requirement_seat_cascades_on_requirement_delete.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261021060108` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261021060108 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

ALTER TABLE pipeline_step_requirements
    DROP FOREIGN KEY fk_psr_requirement;

ALTER TABLE pipeline_step_requirements
    ADD CONSTRAINT fk_psr_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE;
