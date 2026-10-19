-- 20261019100448_plan_layer_checkpoint_and_locked_flags.sql
--
-- Req #3649: the plan layer gains two stored facts — a step is a CHECKPOINT
-- (default on), and a pipeline / epic / step can be LOCKED.
--
-- PROBLEM.  Whether a step holds its downstream until it is done was IMPLIED
--           by link shape (a step with no work requirement was the only
--           checkpoint, req #3597 amendment). The user's rule (2026-10-19) is
--           that every step is a checkpoint unless somebody turns it off, so
--           the fact must be a column, not an inference. And nothing could
--           freeze a finished plan: any writer could still add, delete or
--           move steps and epics under a plan meant to stand as a record.
--
-- SHAPE.    Four TINYINT(1) NOT NULL flags with DEFAULTs — a flag with a
--           default is the one shape MySQL's non-strict sql_mode cannot
--           turn blank (req #3432: '' coerces to 0, a real member).
--           `pipeline_steps.checkpoint DEFAULT 1` — ADD COLUMN fills every
--           existing row with 1, which IS the user's chosen backfill: every
--           live step becomes a checkpoint the moment this applies.
--           `locked DEFAULT 0` on pipelines, epics and pipeline_steps —
--           the lock CASCADES by derivation (a locked pipeline freezes its
--           epics and steps), so there is one column per layer and no copy
--           of the ancestor's state. Enforcement is Lambda-Rest's
--           plan_lock.py, the single DB gateway, because the browser writes
--           these tables directly. Idempotent on re-apply is NOT claimed:
--           ADD COLUMN of an existing column errors (1060), which is the
--           honest answer to applying it twice.
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
--               DarwinSQL/migrations/20261019100448_plan_layer_checkpoint_and_locked_flags.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261019100448_plan_layer_checkpoint_and_locked_flags.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261019100448` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261019100448 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.


ALTER TABLE pipeline_steps
    ADD COLUMN checkpoint TINYINT(1) NOT NULL DEFAULT 1
        COMMENT 'req #3649: 1 = holds every downstream step until done; 0 = launch priority only'
        AFTER run,
    ADD COLUMN locked TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'req #3649: 1 = frozen; structure and authoring fields refused at the gateway'
        AFTER checkpoint;

ALTER TABLE epics
    ADD COLUMN locked TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'req #3649: 1 = frozen, together with every step it contains'
        AFTER epic_status;

ALTER TABLE pipelines
    ADD COLUMN locked TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'req #3649: 1 = a relic in time; the plan, its epics and steps are frozen'
        AFTER execution_mode;
