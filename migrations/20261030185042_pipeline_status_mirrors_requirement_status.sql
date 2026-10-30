-- 20261030185042_pipeline_status_mirrors_requirement_status.sql
--
-- Req #3965: a pipeline's status uses the requirement vocabulary, and the
--            pipelines `closed` flag is removed.
--
-- PROBLEM.  `pipeline_status` (draft|active|paused|completed) did not say what
--           a plan was doing: nothing ever wrote `completed`, it held back no
--           launches, and the `closed` flag (req #3804) did the "finished" job
--           beside it. Plan-level pause lived in the same column.
--
-- SHAPE.    `pipeline_status` takes the requirement vocabulary (user ruling
--           2026-10-30): authoring | authorized | orchestration_ready |
--           orchestrating | met | wontfix | deferred, born `authoring`. Only
--           `orchestrating` launches; plan pause is gone (initiative pause is
--           unchanged); met/wontfix/deferred are what the Pipelines page hides,
--           so the `closed` flag leaves every reader and writer with this
--           requirement. The COLUMN is NOT dropped here: this file applies
--           BEFORE the closeout deploys Lambda-Rest and Darwin, and the code live
--           until then selects `pipelines.closed` by name (a 400/500 on every
--           plan read for that window — measured against darwin_dev). The drop
--           is its own follow-on migration, applied after this deploy, the way
--           req #3752 dropped `epics.completed_at` behind req #3750.
--           VARCHAR(16) -> VARCHAR(24): `orchestration_ready` is 19 characters.
--           Mapping of the old values: draft->authoring, active->orchestrating,
--           paused->orchestration_ready, completed->met. Production's per-plan
--           backfill (which plans are running, which finished) is a data step
--           after the deploy, not part of this file.
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
--               DarwinSQL/migrations/20261030185042_pipeline_status_mirrors_requirement_status.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261030185042_pipeline_status_mirrors_requirement_status.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261030185042` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261030185042 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.



ALTER TABLE pipelines
    MODIFY COLUMN pipeline_status VARCHAR(24) NOT NULL DEFAULT 'authoring';

UPDATE pipelines SET pipeline_status = CASE pipeline_status
        WHEN 'draft'     THEN 'authoring'
        WHEN 'active'    THEN 'orchestrating'
        WHEN 'paused'    THEN 'orchestration_ready'
        WHEN 'completed' THEN 'met'
        ELSE pipeline_status END
 WHERE pipeline_status IN ('draft', 'active', 'paused', 'completed');
