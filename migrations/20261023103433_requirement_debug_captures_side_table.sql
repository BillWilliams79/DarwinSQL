-- 20261023103433_requirement_debug_captures_side_table.sql
--
-- Req #3815: a home for the Requirement Filer Bug button's debug capture.
--
-- PROBLEM.  The Bug button (Darwin/src/RequirementFiler) captures the page's
--           console, errors, network trace, query/store state and environment
--           — 7.5-44.4 KB measured on real pages, ~254 K characters at the
--           caps (≈762 KB of UTF-8 at the extreme). requirements.description
--           is TEXT (65,535 bytes) and rides, uncompressed and unprojected,
--           into every MCP live-work read (`darwin://requirements/open` and
--           friends); a new column on `requirements` would ride the same way.
--
-- SHAPE.    One side table, one row per requirement (`uq_..._req`), read one
--           row at a time by requirement id (darwin://requirement-debug/{id}).
--           `bundle` is the capture JSON UNCOMPRESSED so any reader can read
--           it; `bundle_bytes` its length. Deleting the requirement deletes
--           its capture. Design and measurements:
--           memory/action-popup-requirement-filer.md § Storage (req #3814).
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
--               DarwinSQL/migrations/20261023103433_requirement_debug_captures_side_table.sql darwin_dev
--
--             python3 DarwinSQL/scripts/load_sql.py \
--               DarwinSQL/migrations/20261023103433_requirement_debug_captures_side_table.sql darwin --production
--
--           Production is named TWICE — by name and by intent. The loader
--           refuses `darwin` without --production, and refuses --production on
--           any other database (req #3196). The production command also
--           requires `bash scripts/db/rds-snapshot.sh 20261023103433` to report
--           status=ok first. See memory/database.md § Schema Migration Workflow.
--
-- Migration id 20261023103433 is a UTC timestamp allocated by
-- DarwinSQL/scripts/new-migration.sh (req #3121). Do not renumber it.

CREATE TABLE requirement_debug_captures (
    id              INT          NOT NULL PRIMARY KEY AUTO_INCREMENT,
    requirement_fk  INT          NOT NULL,               -- the requirement the Bug button filed
    bundle          MEDIUMTEXT   NOT NULL,               -- the capture JSON, uncompressed
    bundle_bytes    INT          NOT NULL DEFAULT 0,     -- its length, as the browser serialized it
    creator_fk      VARCHAR(64)  NOT NULL,
    create_ts       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_requirement_debug_captures_req (requirement_fk),
    CONSTRAINT fk_rdc_requirement
        FOREIGN KEY (requirement_fk) REFERENCES requirements (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_rdc_creator
        FOREIGN KEY (creator_fk) REFERENCES profiles (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
