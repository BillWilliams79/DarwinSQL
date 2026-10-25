-- 20261024230223_pipelines_closed_and_sort_order.sql
--
-- Req #3804: a pipeline can be CLOSED (hidden, and parked from orchestration)
-- and the Pipelines cards hold a HAND-SORTED order.
--
-- PROBLEM.  A plan that is over, abandoned or parked has nowhere to go: the
--           Pipelines page shows it forever, and an engine started on it still
--           launches its work. And the cards could only be shown `id:desc` —
--           there is no stored position, so a reader's own order cannot hold.
--
-- SHAPE.    Two columns on `pipelines`, the same two `initiatives` already has:
--             closed      TINYINT(1) NOT NULL DEFAULT 0 — 1 = closed. Hidden by
--                         default on the Pipelines page, and every epic of the
--                         plan is launch-suppressed by the derivation
--                         (`suppressed_by: ['closed']`, engine code CLOSED).
--                         A flag, not a `pipeline_status` value: lifecycle
--                         status keeps its own meaning (and its timestamp side
--                         effects), and closing a plan must not erase whether it
--                         was paused or completed.
--             sort_order  INT NULL — the card's position, ascending. A new plan
--                         is written BELOW the current minimum (inserted at the
--                         front); NULL sorts after every positioned plan.
--           Backfill: every existing plan gets a position, newest first per
--           creator — the order the page showed (`id:desc`) until now.
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
--               DarwinSQL/migrations/20261024230223_pipelines_closed_and_sort_order.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261024230223_pipelines_closed_and_sort_order.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261024230223` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261024230223 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.



ALTER TABLE pipelines
    ADD COLUMN closed     TINYINT(1) NOT NULL DEFAULT 0 AFTER locked,
    ADD COLUMN sort_order INT        NULL     DEFAULT NULL AFTER closed;

UPDATE pipelines p
JOIN (SELECT id,
             ROW_NUMBER() OVER (PARTITION BY creator_fk ORDER BY id DESC) - 1 AS pos
        FROM pipelines) ranked ON ranked.id = p.id
SET p.sort_order = ranked.pos;
